"""Citation mapping tests: tag extraction and resolution against retrieved chunks."""

import uuid

from app.services import citation_service
from app.services.retrieval_service import RetrievedChunk


def _chunk(text: str = "evidence", title: str = "Title") -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        document_title=title,
        page_number=3,
        section=None,
        chunk_index=2,
        text=text,
        score=0.9,
    )


def test_extract_tags_in_order_and_deduplicated():
    answer = "See [1], also [2] and [1] again, plus [3]"
    assert citation_service.extract_tags(answer) == [1, 2, 3]


def test_extract_tags_ignores_bracketed_text_without_numbers():
    assert citation_service.extract_tags("look at [text] here") == []


def test_build_citations_maps_tags_to_results():
    chunks = [_chunk(title="A"), _chunk(title="B"), _chunk(title="C")]
    citations = citation_service.build_citations("Answer [2] and [1].", chunks)
    assert [c.document_title for c in citations] == ["B", "A"]
    assert citations[0].chunk_id == str(chunks[1].chunk_id)
    assert citations[0].document_id == str(chunks[1].document_id)
    assert citations[0].page_number == 3
    assert citations[0].chunk_index == 2
    assert citations[0].section is None  # never fabricated


def test_build_citations_ignores_unknown_tags():
    chunks = [_chunk(title="A")]
    citations = citation_service.build_citations("Answer [7] and [1].", chunks)
    assert len(citations) == 1
    assert citations[0].document_title == "A"


def test_build_citations_empty_for_unrelated_answer():
    chunks = [_chunk(title="A")]
    assert citation_service.build_citations("No sources used.", chunks) == []