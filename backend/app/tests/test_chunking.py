"""chunk_pages unit tests."""

from app.rag.chunking import chunk_pages
from app.services.pdf_service import ExtractedPage


def page(number, text):
    return ExtractedPage(page_number=number, text=text)


def test_chunk_size_respected():
    text = "word " * 600  # ~3000 chars
    chunks = chunk_pages([page(1, text)], chunk_size=1000, chunk_overlap=150)
    assert len(chunks) > 1
    # Non-final chunks never exceed the size; the final chunk may grow by the
    # folded tail (up to half a chunk) to avoid orphan fragments.
    for c in chunks[:-1]:
        assert len(c.text) <= 1000
    assert len(chunks[-1].text) <= 1000 + 500


def test_chunk_overlap_shares_text():
    text = "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu " * 20
    chunks = chunk_pages([page(1, text)], chunk_size=200, chunk_overlap=50)
    assert len(chunks) > 1
    # Consecutive chunks share a boundary region.
    overlap_found = any(chunks[i].text  in chunks[i + 1].text or chunks[i + 1].text in chunks[i].text for i in range(len(chunks) - 1))
    assert overlap_found or len(chunks) == 1


def test_chunk_size_greater_than_text_single_chunk():
    chunks = chunk_pages([page(1, "short text")], chunk_size=1000, chunk_overlap=150)
    assert len(chunks) == 1
    assert chunks[0].text == "short text"
    assert chunks[0].token_count > 0


def test_empty_text_produces_no_chunks():
    assert chunk_pages([page(1, "")], chunk_size=500, chunk_overlap=50) == []
    assert chunk_pages([], chunk_size=500, chunk_overlap=50) == []


def test_page_metadata_and_global_order():
    pages = [page(1, "one two three " * 100), page(2, "four five six " * 100)]
    chunks = chunk_pages(pages, chunk_size=300, chunk_overlap=40)
    assert len(chunks) > 1
    indices = [c.chunk_index for c in chunks]
    assert indices == list(range(len(chunks)))
    assert all(c.page_number in (1, 2) for c in chunks)
    # text from page 1 never appears in a chunk whose page_number is 2
    for c in chunks:
        if c.page_number == 2:
            assert "one two three" not in c.text


def test_token_count_estimated():
    chunks = chunk_pages([page(1, "a b c d e")], chunk_size=1000, chunk_overlap=0)
    assert chunks[0].token_count == 5