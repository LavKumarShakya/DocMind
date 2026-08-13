"""Context assembly tests: tagging, whole-chunk truncation, max_chars."""

from app.services.context_service import build_context, included_indexes
from app.services.retrieval_service import RetrievedChunk


def _chunk(text: str) -> RetrievedChunk:
    import uuid

    return RetrievedChunk(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        document_title="Title",
        page_number=1,
        section=None,
        chunk_index=0,
        text=text,
        score=0.95,
    )


def test_build_context_labels_chunks_in_order():
    context = build_context([_chunk("alpha"), _chunk("beta")], max_chars=1000)
    assert context.startswith("[1] alpha")
    assert "[2] beta" in context
    assert included_indexes(context) == [1, 2]


def test_build_context_truncates_whole_chunks():
    chunks = [_chunk("A" * 100), _chunk("B" * 100), _chunk("C" * 100)]
    context = build_context(chunks, max_chars=230)
    # [1] A.. (102 chars) + separator + [2] B.. (102 chars) = 205; C must be dropped.
    assert "[1]" in context
    assert "[2]" in context
    assert "[3]" not in context
    assert "CCC" not in context
    assert included_indexes(context) == [1, 2]


def test_build_context_empty_results():
    assert build_context([], max_chars=1000) == ""


def test_build_context_respects_custom_max_chars():
    context = build_context([_chunk("hello world")], max_chars=10)
    assert context == ""  # chunk + tag exceeds the limit, dropped whole
    assert included_indexes(context) == []