"""Phase 7 evaluation runner.

Run the version-controlled dataset against the real CampusRAG pipeline on an
isolated evaluation database (``campusrag_eval``), then serialize raw per-
question results to JSON.

Usage (from ``backend``):

    python -m evaluation.run_evaluation --mode baseline
    python -m evaluation.run_evaluation --mode phase5
    python -m evaluation.run_evaluation --compare

Flags:
    --mode              baseline | phase5 (default phase5)
    --compare           load results/baseline.json + results/phase5.json and
                        write comparison.json + report.md
    --limit N           evaluate only the first N questions
    --category NAME     evaluate only questions of one category
    --output PATH       override the results JSON path
    --skip-generation   retrieval metrics only (no LLM calls)
    --llm-provider      local | gemini (default gemini; local is deterministic
                        and offline but cannot answer "unanswerable" items)
    --rerank-top-k      phase5 rerank window (default 10 = EVAL_TOP_K)

The runner reuses the production ingestion/retrieval/generation services and
records its own metadata; it never writes to the development database.
"""

from __future__ import annotations

import argparse
import json
import logging
import platform
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.enums import Role
from app.core.security import hash_password
from app.db.database import Base
from app.db.models import User
from app.rag.confidence import is_confident
from app.services import citation_service, context_service
from app.services.citation_service import Citation
from app.services.retrieval_types import RetrievalCandidate

from evaluation.analyze import classify_failure
from evaluation.answers import answer_is_correct, faithfulness_score, is_fallback
from evaluation.citations import analyze_citations
from evaluation.confidence import confusion_matrix
from evaluation.dataset import DATASET_PATH, chunk_is_relevant, load_dataset
from evaluation.metrics import (
    aggregate_mrr,
    aggregate_recall,
    document_recall_at_k,
    first_relevant_rank,
    mrr,
    recall_at_k,
)
from evaluation.modes import BaselineRetriever, Phase5Retriever, EVAL_TOP_K

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("evaluation")

RESULTS_DIR = Path(__file__).resolve().parent / "results"
STORAGE_DIR = Path(__file__).resolve().parent / "storage"
EVAL_DB_NAME = "campusrag_eval"

# Throttle + retry for paid/rate-limited LLM providers. Gemini free tier allows
# ~5 requests/minute; the runner enforces a minimum interval and retries
# transient 429/503 responses with backoff so quota errors are not misreported
# as genuine "could not find the answer" refusals.
_LLM_MIN_INTERVAL_SECONDS = 0.0
_LLM_MAX_ATTEMPTS = 3
_last_llm_call: float = 0.0


def configure_llm_throttle(min_interval_seconds: float, max_attempts: int = 3) -> None:
    global _LLM_MIN_INTERVAL_SECONDS, _LLM_MAX_ATTEMPTS
    _LLM_MIN_INTERVAL_SECONDS = min_interval_seconds
    _LLM_MAX_ATTEMPTS = max_attempts


def _is_retriable(exc: Exception) -> bool:
    message = str(exc)
    return "429" in message or "503" in message or "RESOURCE_EXHAUSTED" in message


def _call_llm(provider, system_prompt: str, question: str) -> tuple[str | None, str | None]:
    """Throttled, retrying LLM call. Returns (answer_text, error_message)."""
    import time as _time

    global _last_llm_call
    now = _time.perf_counter()
    wait = _LLM_MIN_INTERVAL_SECONDS - (now - _last_llm_call)
    if wait > 0:
        _time.sleep(wait)

    for attempt in range(1, _LLM_MAX_ATTEMPTS + 1):
        try:
            answer = provider.answer(system_prompt=system_prompt, question=question)
            _last_llm_call = _time.perf_counter()
            return answer, None
        except Exception as exc:
            if not _is_retriable(exc) or attempt == _LLM_MAX_ATTEMPTS:
                _last_llm_call = _time.perf_counter()
                return None, str(exc)[:300]
            _time.sleep(20.0 * attempt)  # backoff for transient quota/availability
    return None, "unreachable"


def _ensure_eval_database() -> str:
    """Create the evaluation database if needed; return its URL."""
    base_url = settings.DATABASE_URL.rsplit("/", 1)[0] + "/postgres"
    admin = create_engine(base_url, isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": EVAL_DB_NAME}
            ).scalar()
            if not exists:
                conn.execute(text(f'CREATE DATABASE {EVAL_DB_NAME}'))
                logger.info("Created evaluation database %s", EVAL_DB_NAME)
    finally:
        admin.dispose()
    return settings.DATABASE_URL.rsplit("/", 1)[0] + f"/{EVAL_DB_NAME}"


def _ensure_schema(engine) -> None:
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    Base.metadata.create_all(engine)


def _ensure_eval_user(Session) -> User:
    session = Session()
    try:
        user = session.query(User).filter(User.email == "eval-runner@campusrag.local").first()
        if user is None:
            user = User(
                name="Eval Runner",
                email="eval-runner@campusrag.local",
                password_hash=hash_password("eval-password"),
                role=Role.ADMIN,
            )
            session.add(user)
            session.commit()
            session.refresh(user)
        return user
    finally:
        session.close()


def _ingest_corpus(Session, user: User, dataset) -> list[dict]:
    """Ingest every corpus PDF (real pipeline) when no ACTIVE chunked version exists."""
    from evaluation.dataset import CORPUS_DIR
    from app.services.document_service import create_document
    from app.services.ingestion_service import process_document
    from app.services.storage_service import save_document_file
    from app.core.enums import DocumentStatus

    session = Session()
    ingested: list[dict] = []
    try:
        from sqlalchemy import func, select
        from app.db.models import Document, DocumentChunk

        rows = session.execute(
            select(Document.title, func.count(DocumentChunk.id))
            .outerjoin(DocumentChunk, DocumentChunk.document_id == Document.id)
            .where(Document.status == DocumentStatus.ACTIVE)
            .group_by(Document.title)
        ).all()
        active = {title: count for title, count in rows}
    finally:
        session.close()

    for corpus in dataset.corpus:
        title = corpus["document_title"]
        if active.get(title, 0) > 0:
            logger.info("Corpus document %r already ACTIVE (%s chunks)", title, active[title])
            ingested.append({"title": title, "chunks": active[title], "reused": True})
            continue

        path = CORPUS_DIR / corpus["filename"]
        if not path.is_file():
            raise FileNotFoundError(f"Corpus file missing for {title}: {path}")

        session = Session()
        try:
            content = path.read_bytes()
            file_path = save_document_file(uuid.uuid4(), content)
            document = create_document(
                session,
                document_id=uuid.uuid4(),
                uploader=user,
                original_filename=path.name,
                mime_type="application/pdf",
                file_size=len(content),
                file_path=file_path,
                title=title,
                access_level="PUBLIC",
            )
            processed = process_document(session, document.id, user)
            chunks = _count_chunks(session, processed.id)
            logger.info("Ingested %s -> %s chunks", title, chunks)
            ingested.append({"title": title, "chunks": chunks, "reused": False})
        finally:
            session.close()
    return ingested


def _count_chunks(session, document_id) -> int:
    from sqlalchemy import func, select
    from app.db.models import DocumentChunk

    return (
        session.scalar(
            select(func.count(DocumentChunk.id)).where(
                DocumentChunk.document_id == document_id
            )
        )
        or 0
    )


def _corpus_chunk_texts(Session) -> list[str]:
    """Return every ACTIVE corpus chunk's text from the evaluation database.

    Used to verify (independently of retrieval) whether a question's ground-truth
    supporting evidence actually exists in the indexed evaluation corpus.
    """
    from app.core.enums import DocumentStatus
    from app.db.models import Document, DocumentChunk
    from sqlalchemy import select

    session = Session()
    try:
        return list(
            session.execute(
                select(DocumentChunk.content)
                .join(Document, Document.id == DocumentChunk.document_id)
                .where(Document.status == DocumentStatus.ACTIVE)
            ).scalars()
        )
    finally:
        session.close()


def _select_questions(dataset, limit: int | None, category: str | None):
    questions = list(dataset.questions)
    if category:
        questions = [q for q in questions if q.category == category]
    if limit:
        questions = questions[:limit]
    return questions


def _score_retrieval(question, candidates: list[RetrievalCandidate]) -> dict:
    relevant_chunks = [
        str(c.chunk_id) for c in candidates if chunk_is_relevant(c.text, question.supporting_text)
    ]
    relevant_docs = {
        c.document_title for c in candidates if c.document_title in question.relevant_documents
    }
    ranked_chunk_ids = [str(c.chunk_id) for c in candidates]
    ranked_docs = [c.document_title for c in candidates]

    if not question.answerable:
        return {
            "recall@1": 0.0,
            "recall@3": 0.0,
            "recall@5": 0.0,
            "recall@10": 0.0,
            "mrr": 0.0,
            "doc_recall@1": 0.0,
            "doc_recall@5": 0.0,
            "doc_recall@10": 0.0,
            "relevant_chunks_retrieved": 0,
            "retrieved_any": len(candidates) > 0,
        }

    return {
        "recall@1": recall_at_k(relevant_chunks, ranked_chunk_ids, 1),
        "recall@3": recall_at_k(relevant_chunks, ranked_chunk_ids, 3),
        "recall@5": recall_at_k(relevant_chunks, ranked_chunk_ids, 5),
        "recall@10": recall_at_k(relevant_chunks, ranked_chunk_ids, 10),
        "mrr": mrr(relevant_chunks, ranked_chunk_ids),
        "doc_recall@1": document_recall_at_k(relevant_docs, ranked_docs, 1),
        "doc_recall@5": document_recall_at_k(relevant_docs, ranked_docs, 5),
        "doc_recall@10": document_recall_at_k(relevant_docs, ranked_docs, 10),
        "relevant_chunks_retrieved": len(relevant_chunks),
        "first_relevant_rank": first_relevant_rank(relevant_chunks, ranked_chunk_ids),
        "retrieved_any": len(candidates) > 0,
    }


def _retrieve(mode_retriever, db, question, user) -> tuple[list[RetrievalCandidate], dict]:
    outcome = mode_retriever.retrieve(db, query=question.question, user=user)
    return outcome.candidates, outcome.times


def _generate(
    *,
    db,
    question,
    candidates: list[RetrievalCandidate],
    apply_gate: bool,
    llm_provider,
) -> dict:
    """Mirror production answer_question; returns {answer, citations, confident, llm_skipped, llm_time}."""
    if apply_gate:
        confident = is_confident(candidates) if candidates else False
    else:
        confident = None

    if not candidates or (apply_gate and not confident):
        return {
            "answer": "I couldn't find sufficient information in the available university documents.",
            "citations": [],
            "confident": bool(confident),
            "llm_skipped": True,
            "llm_time": None,
        }

    context = context_service.build_context(candidates)
    system_prompt = build_system_prompt(context)

    start = time.perf_counter()
    answer, error = _call_llm(llm_provider, system_prompt, question.question)
    if error is not None:
        logger.warning("LLM provider failed for %s: %s", question.id, error)
        return {
            "answer": "I couldn't find sufficient information in the available university documents.",
            "citations": [],
            "confident": bool(confident),
            "llm_skipped": False,
            "llm_time": time.perf_counter() - start,
            "llm_error": error,
        }
    llm_time = time.perf_counter() - start

    answer = answer.strip()
    citations = citation_service.build_citations(answer, candidates)
    return {
        "answer": answer,
        "citations": citations,
        "confident": bool(confident),
        "llm_skipped": False,
        "llm_time": llm_time,
    }


def build_system_prompt(context: str) -> str:
    from app.rag.prompts import build_system_prompt as _build

    return _build(context)


def _citation_summary(citations: list[Citation]) -> dict:
    return {
        "count": len(citations),
        "documents": sorted({c.document_title for c in citations}),
        "pages": sorted({c.page_number for c in citations if c.page_number is not None}),
    }


def _build_provider(name: str):
    if name == "local":
        from app.services.llm_service import LocalExtractiveProvider

        return LocalExtractiveProvider()
    from app.services.llm_service import GeminiProvider

    return GeminiProvider()


def _run_mode(args) -> dict:
    dataset = load_dataset()
    questions = _select_questions(dataset, args.limit, args.category)

    eval_url = _ensure_eval_database()
    engine = create_engine(eval_url)
    _ensure_schema(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    db = Session()

    try:
        settings.STORAGE_DIR = str(STORAGE_DIR.resolve())
        STORAGE_DIR.mkdir(parents=True, exist_ok=True)

        user = _ensure_eval_user(Session)
        corpus_state = _ingest_corpus(Session, user, dataset)
        corpus_chunk_texts = _corpus_chunk_texts(Session)

        mode_retriever = (
            BaselineRetriever() if args.mode == "baseline" else Phase5Retriever()
        )
        apply_gate = args.mode == "phase5"

        # Warm up models (embedder, reranker) so per-query latency reflects
        # steady state rather than first-call model loading.
        mode_retriever.retrieve(db, query="warm-up attendance regulations", user=user)

        llm_provider = None
        if not args.skip_generation:
            llm_provider = _build_provider(args.llm_provider)

        results = []
        for index, question in enumerate(questions, start=1):
            logger.info("[%s] (%d/%d) %s", args.mode, index, len(questions), question.id)
            t0 = time.perf_counter()
            candidates, stage_times = _retrieve(mode_retriever, db, question, user)
            retrieval_metrics = _score_retrieval(question, candidates)

            gen = None
            if not args.skip_generation:
                gen = _generate(
                    db=db,
                    question=question,
                    candidates=candidates,
                    apply_gate=apply_gate,
                    llm_provider=llm_provider,
                )

            e2e = time.perf_counter() - t0

            row = {
                "id": question.id,
                "question": question.question,
                "category": question.category,
                "difficulty": question.difficulty,
                "answerable": question.answerable,
                "expected_answer": question.expected_answer,
                "expected_answer_terms": question.expected_answer_terms,
                "relevant_documents": question.relevant_documents,
                "evidence_in_corpus": bool(question.supporting_text) and any(
                    chunk_is_relevant(text, question.supporting_text)
                    for text in corpus_chunk_texts
                ),
                "retrieval_metrics": retrieval_metrics,
                "stage_times": {k: round(v * 1000.0, 3) for k, v in stage_times.items()},
                "e2e_time_ms": round(e2e * 1000.0, 1),
            }

            if gen is not None:
                answer = gen["answer"]
                correct = answer_is_correct(question, answer)
                evidence = "\n\n".join(c.text for c in candidates)
                row.update(
                    {
                        "confident": gen["confident"],
                        "gate_applied": apply_gate,
                        "llm_skipped": gen["llm_skipped"],
                        "llm_time_ms": round(gen["llm_time"] * 1000.0, 1) if gen["llm_time"] is not None else None,
                        "answer": answer,
                        "is_fallback": is_fallback(answer),
                        "correct": correct,
                        "faithfulness": faithfulness_score(question, answer, evidence),
                        "llm_error": gen.get("llm_error"),
                        "citations": analyze_citations(answer, candidates, question),
                        "failure": classify_failure(
                            question=question,
                            answer=answer,
                            candidates=candidates,
                            confident=gen["confident"],
                            gate_applied=apply_gate,
                            llm_error=gen.get("llm_error"),
                        ),
                    }
                )

            row["retrieved"] = [
                {
                    "chunk_id": str(c.chunk_id),
                    "document_title": c.document_title,
                    "page_number": c.page_number,
                    "chunk_index": c.chunk_index,
                    "dense_score": c.dense_score,
                    "bm25_score": c.bm25_score,
                    "hybrid_score": c.hybrid_score,
                    "rerank_score": c.rerank_score,
                    "relevant": chunk_is_relevant(c.text, question.supporting_text),
                }
                for c in candidates
            ]
            results.append(row)

        metadata = {
            "dataset_version": dataset.dataset_version,
            "dataset_path": str(DATASET_PATH),
            "mode": args.mode,
            "questions_evaluated": len(results),
            "limit": args.limit,
            "category": args.category,
            "skip_generation": args.skip_generation,
            "llm_provider": None if args.skip_generation else args.llm_provider,
            "llm_model": (
                settings.LLM_MODEL
                if not args.skip_generation and args.llm_provider == "gemini"
                else None
            ),
            "embedding_model": settings.EMBEDDING_MODEL,
            "reranker_model": settings.RERANKER_MODEL if args.mode == "phase5" else None,
            "dense_candidate_k": settings.DENSE_CANDIDATE_K,
            "bm25_candidate_k": settings.BM25_CANDIDATE_K,
            "rerank_top_k": args.rerank_top_k,
            "eval_top_k": EVAL_TOP_K,
            "confidence_threshold": settings.CONFIDENCE_THRESHOLD,
            "retrieval_min_similarity": settings.RETRIEVAL_MIN_SIMILARITY,
            "corpus": corpus_state,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "python": platform.python_version(),
            "platform": platform.platform(),
        }

        output = {"meta": metadata, "questions": results}
        return output
    finally:
        db.close()
        engine.dispose()


def _latency_summary(questions: list[dict]) -> dict:
    """Per-stage + end-to-end latency statistics (mean/median/p95, in ms)."""
    import statistics

    def _summarize(values) -> dict:
        vals = [v for v in values if v is not None]
        if not vals:
            return {"count": 0, "mean_ms": None, "median_ms": None, "p95_ms": None}
        ordered = sorted(vals)
        p95 = ordered[min(len(ordered) - 1, int(round(0.95 * len(ordered))) - 1)]
        return {
            "count": len(vals),
            "mean_ms": round(sum(vals) / len(vals), 1),
            "median_ms": round(statistics.median(ordered), 1),
            "p95_ms": round(p95, 1),
        }

    summary: dict = {}
    for stage in ("dense", "bm25", "fuse", "rerank"):
        values = [q.get("stage_times", {}).get(stage) for q in questions]
        if any(v is not None for v in values):
            summary[stage] = _summarize(values)
    summary["e2e"] = _summarize([q.get("e2e_time_ms") for q in questions])
    llm_values = [q.get("llm_time_ms") for q in questions if q.get("llm_time_ms") is not None]
    if llm_values:
        summary["llm"] = _summarize(llm_values)
    return summary


def _aggregate(results: dict) -> dict:
    questions = results["questions"]
    answerable = [q for q in questions if q["answerable"]]

    def _retrieval_metric(name: str) -> float:
        values = [q["retrieval_metrics"][name] for q in answerable]
        return round(sum(values) / max(1, len(values)), 4)

    aggregates: dict = {
        "questions_total": len(questions),
        "questions_answerable": len(answerable),
        "recall@1": _retrieval_metric("recall@1"),
        "recall@3": _retrieval_metric("recall@3"),
        "recall@5": _retrieval_metric("recall@5"),
        "recall@10": _retrieval_metric("recall@10"),
        "mrr": _retrieval_metric("mrr"),
        "doc_recall@1": _retrieval_metric("doc_recall@1"),
        "doc_recall@5": _retrieval_metric("doc_recall@5"),
        "doc_recall@10": _retrieval_metric("doc_recall@10"),
    }

    aggregates["latency"] = _latency_summary(questions)

    if not results["meta"].get("skip_generation"):
        evaluated = [q for q in questions if "correct" in q]
        aggregates["answered"] = len(evaluated)
        aggregates["answer_accuracy"] = round(
            sum(1 for q in evaluated if q["correct"]) / max(1, len(evaluated)), 4
        )
        aggregates["fallback_rate"] = round(
            sum(1 for q in evaluated if q.get("is_fallback")) / max(1, len(evaluated)), 4
        )
        aggregates["faithfulness_0"] = round(
            sum(1 for q in evaluated if q.get("faithfulness") == 0) / max(1, len(evaluated)), 4
        )
        aggregates["faithfulness_2"] = round(
            sum(1 for q in evaluated if q.get("faithfulness") == 2) / max(1, len(evaluated)), 4
        )
        failures = [q.get("failure") for q in evaluated]
        aggregates["failure_rate"] = round(
            sum(1 for f in failures if f is not None) / max(1, len(evaluated)), 4
        )
        aggregates["failures"] = {}
        for label in sorted({f for f in failures if f is not None}):
            count = sum(1 for f in failures if f == label)
            aggregates["failures"][label] = count

        valid_ratios = [
            q["citations"]["valid_ratio"]
            for q in evaluated
            if q["citations"]["valid_ratio"] is not None
        ]
        aggregates["citation_validity_mean"] = (
            round(sum(valid_ratios) / len(valid_ratios), 4) if valid_ratios else None
        )
        aggregates["citation_questions_with_tags"] = len(valid_ratios)

        if results["meta"].get("mode") == "phase5":
            gate_rows = [
                {
                    "answerable": q["answerable"],
                    "confident": q["confident"],
                    "correct": q["correct"],
                    "evidence_in_corpus": q.get("evidence_in_corpus", False),
                }
                for q in evaluated
            ]
            aggregates["confidence"] = confusion_matrix(gate_rows)
            aggregates["abstention_rate"] = aggregates["confidence"]["abstention_rate"]

    # Category breakdown (retrieval recall@5 + accuracy when available).
    categories: dict = {}
    for q in questions:
        cat = categories.setdefault(
            q["category"],
            {"count": 0, "answerable": 0, "recall@5": [], "correct": [], "fallback": []},
        )
        cat["count"] += 1
        if q["answerable"]:
            cat["answerable"] += 1
            cat["recall@5"].append(q["retrieval_metrics"]["recall@5"])
        if "correct" in q:
            cat["correct"].append(1 if q["correct"] else 0)
            cat["fallback"].append(1 if q.get("is_fallback") else 0)
    aggregates["category_breakdown"] = {
        name: {
            "count": c["count"],
            "answerable": c["answerable"],
            "recall@5": round(sum(c["recall@5"]) / max(1, len(c["recall@5"])), 4),
            "accuracy": round(sum(c["correct"]) / max(1, len(c["correct"])), 4)
            if c["correct"]
            else None,
            "fallback_rate": round(sum(c["fallback"]) / max(1, len(c["fallback"])), 4)
            if c["fallback"]
            else None,
        }
        for name, c in sorted(categories.items())
    }
    return aggregates


def _write(results: dict, output_path: Path) -> None:
    results["aggregates"] = _aggregate(results)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    logger.info("Wrote %s", output_path)


def _compare(args) -> None:
    from evaluation.report import build_comparison

    baseline = json.loads((RESULTS_DIR / "baseline.json").read_text(encoding="utf-8"))
    phase5 = json.loads((RESULTS_DIR / "phase5.json").read_text(encoding="utf-8"))

    output = Path(args.output) if args.output else RESULTS_DIR / "comparison.json"
    comparison = build_comparison(baseline, phase5)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(comparison, indent=2), encoding="utf-8")
    logger.info("Wrote %s", output)

    report = RESULTS_DIR / "report.md"
    report.write_text(comparison["report_markdown"], encoding="utf-8")
    logger.info("Wrote %s", report)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CampusRAG Phase 7 evaluation runner")
    parser.add_argument("--mode", choices=["baseline", "phase5"], default="phase5")
    parser.add_argument("--compare", action="store_true", help="compare existing results")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--category", default=None)
    parser.add_argument("--output", default=None)
    parser.add_argument("--skip-generation", action="store_true")
    parser.add_argument("--llm-provider", choices=["local", "gemini"], default="gemini")
    parser.add_argument("--rerank-top-k", type=int, default=EVAL_TOP_K)
    parser.add_argument("--llm-min-interval", type=float, default=None,
                        help="minimum seconds between LLM calls (default: 12.5 for gemini, 0 for local)")
    args = parser.parse_args(argv)

    if args.compare:
        _compare(args)
        return 0

    if args.mode not in ("baseline", "phase5"):
        parser.error("--mode must be baseline or phase5")

    if not args.skip_generation:
        interval = (
            args.llm_min_interval
            if args.llm_min_interval is not None
            else (12.5 if args.llm_provider == "gemini" else 0.0)
        )
        configure_llm_throttle(interval)

    results = _run_mode(args)
    output = Path(args.output) if args.output else RESULTS_DIR / f"{args.mode}.json"
    _write(results, output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
