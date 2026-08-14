"""Unit tests for the evaluation dataset loader/validator (no DB, no LLM)."""

from pathlib import Path

import pytest

from evaluation.dataset import (
    DATASET_PATH,
    chunk_is_relevant,
    load_dataset,
    normalize,
    validate,
)


def test_real_dataset_loads_and_validates():
    ds = load_dataset(DATASET_PATH)
    assert ds.dataset_version
    assert ds.questions
    ids = [q.id for q in ds.questions]
    assert len(ids) == len(set(ids)), "question ids must be unique"
    for q in ds.questions:
        assert q.question.strip()
        if q.answerable:
            assert q.expected_answer_terms, f"{q.id} answerable needs terms"
            assert q.relevant_documents, f"{q.id} answerable needs documents"
            assert q.supporting_text, f"{q.id} answerable needs supporting_text"
        else:
            assert q.expected_answer is None, f"{q.id} must have null expected_answer"


def test_real_dataset_has_both_corpus_documents():
    ds = load_dataset(DATASET_PATH)
    titles = {c["document_title"] for c in ds.corpus}
    assert {"academic_regulations", "RAG_Test_Document_Edge_Cases"} <= titles


def test_validate_rejects_duplicate_ids():
    raw = {
        "questions": [
            {"id": "Q1", "question": "a", "answerable": True,
             "relevant_documents": ["d"], "supporting_text": "x", "expected_answer_terms": ["x"]},
            {"id": "Q1", "question": "b", "answerable": False},
        ]
    }
    with pytest.raises(ValueError, match="duplicate"):
        validate(raw)


def test_validate_rejects_answerable_without_ground_truth():
    raw = {"questions": [{"id": "Q1", "question": "a", "answerable": True}]}
    with pytest.raises(ValueError, match="relevant_documents"):
        validate(raw)


def test_validate_rejects_unanswerable_with_expected_answer():
    raw = {
        "questions": [
            {"id": "Q1", "question": "a", "answerable": False, "expected_answer": "nope"}
        ]
    }
    with pytest.raises(ValueError, match="expected_answer"):
        validate(raw)


def test_normalize_folds_case_punctuation_and_whitespace():
    assert normalize("  A+  (10)  ") == "a 10"
    assert normalize("Re-examination") == "re examination"
    assert normalize(None) == ""
    assert normalize("75% of total classes") == "75 of total classes"


def test_chunk_is_relevant_matches_supporting_fragment():
    chunk = "A minimum attendance of 75% of total classes is required."
    assert chunk_is_relevant(chunk, ["75% of total classes"])
    assert not chunk_is_relevant(chunk, ["grading scale"])
    assert not chunk_is_relevant(chunk, None)
    assert chunk_is_relevant("Library open 8am to midnight.", ["8am to midnight"])


def test_dataset_path_resolution_from_test_file():
    backend = Path(__file__).resolve().parents[2]
    assert (backend / "evaluation" / "dataset.json").is_file()
