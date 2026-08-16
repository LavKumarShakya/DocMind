"""TEMP-DIAGNOSTIC: compare demo retrieval + confidence gate local vs Docker.

Usage (from backend/):  python -m scripts.diag_demo --question "..."

Prints environment config, chunk count, top-k TF-IDF evidence, the confidence
gate decision and whether the demo answer is the grounded refusal.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings  # noqa: E402
from app.db.database import SessionLocal  # noqa: E402
from app.rag.confidence import best_relevance_score, is_confident  # noqa: E402
from app.rag.prompts import DEMO_FALLBACK_ANSWER  # noqa: E402
from app.services import demo_service  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--question", default="What is DocMind designed to do?")
    parser.add_argument("--with-llm", action="store_true", help="Also call the LLM (Gemini)")
    args = parser.parse_args()

    print("=== ENV ===")
    print(f"DEMO_MODE={settings.DEMO_MODE}")
    print(f"DEMO_DOCUMENT_ID={settings.DEMO_DOCUMENT_ID}")
    print(f"DEMO_DOCUMENT_PATH={settings.DEMO_DOCUMENT_PATH}")
    print(f"DEMO_DOCUMENT_TITLE={settings.DEMO_DOCUMENT_TITLE}")
    print(f"DEMO_CONFIDENCE_THRESHOLD={settings.DEMO_CONFIDENCE_THRESHOLD}")
    print(f"CONFIDENCE_THRESHOLD={settings.CONFIDENCE_THRESHOLD}")
    print(f"DATABASE_URL={settings.DATABASE_URL}")
    print(f"LLM_PROVIDER={settings.LLM_PROVIDER} LLM_MODEL={settings.LLM_MODEL}")
    print(f"DEMO_SEED_PATH={demo_service._DEMO_SEED_PATH} exists={demo_service._DEMO_SEED_PATH.is_file()}")

    with SessionLocal() as db:
        doc = demo_service.get_demo_document(db)
        print("=== INDEX ===")
        print(f"document exists={doc is not None}")
        if doc is not None:
            print(
                f"title={doc.title!r} status={doc.status} access={doc.access_level} "
                f"page_count={doc.page_count} file_size={doc.file_size} "
                f"processed_at={doc.processed_at} created_at={doc.created_at}"
            )
        n_chunks = demo_service.demo_chunk_count(db)
        print(f"chunk_count={n_chunks}")
        print(f"demo_index_ready={demo_service.demo_index_ready(db)}")

        print("=== RETRIEVAL + GATE ===")
        print(f"query={args.question!r}")
        if n_chunks == 0:
            print("NO INDEX -> refusing (DEMO_INDEX_MISSING path)")
            return 0
        user = demo_service._demo_guest()
        results = demo_service.retrieve_demo_evidence(db, args.question, user, top_k=5)
        for i, r in enumerate(results):
            print(
                f"  top[{i}] chunk_index={r.chunk_index} page={r.page_number} "
                f"hybrid_score={r.hybrid_score:.6f} text={r.text[:60]!r}"
            )
        best = best_relevance_score(results)
        thresh = settings.DEMO_CONFIDENCE_THRESHOLD
        print(f"best_score={best:.6f} threshold={thresh} decision={'ACCEPT' if is_confident(results, threshold=thresh) else 'REFUSE'}")

        print("=== ANSWER ===")
        if args.with_llm:
            try:
                result = demo_service.answer_demo_question(db, question=args.question)
                is_fallback = result.answer == DEMO_FALLBACK_ANSWER
                print(f"answer_is_grounded_refusal={is_fallback}")
                print(f"answer={result.answer[:200]!r}")
                print(f"citations={[(c.page_number, round(c.relevance_score, 4)) for c in result.citations]}")
            except Exception as exc:  # noqa: BLE001 - diagnostic script
                print(f"answer_exception={type(exc).__name__}: {exc}")
        else:
            print("skipping LLM call (pass --with-llm)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())