"""PDF validation, extraction and cleaning tests."""

import pytest

from app.core.errors import ApiError
from app.services import pdf_service
from app.services.pdf_service import (
    PdfExtractionError,
    clean_text,
    extract_pages,
    extract_pdf_metadata,
    validate_upload,
)
from app.tests.helpers import build_pdf


def test_validate_upload_accepts_real_pdf():
    name = validate_upload(filename="guide.pdf", content=build_pdf(["ok"]))
    assert name == "guide.pdf"


def test_validate_upload_rejects_by_extension():
    with pytest.raises(ApiError) as exc:
        validate_upload(filename="guide.txt", content=b"%PDF-1.4 x")
    assert exc.value.code == "INVALID_DOCUMENT_TYPE"


def test_validate_upload_rejects_by_magic_bytes():
    with pytest.raises(ApiError) as exc:
        validate_upload(filename="guide.pdf", content=b"not a real pdf")
    assert exc.value.code == "INVALID_DOCUMENT_TYPE"


def test_validate_upload_rejects_empty():
    with pytest.raises(ApiError) as exc:
        validate_upload(filename="empty.pdf", content=b"")
    assert exc.value.code == "EMPTY_DOCUMENT"


def test_sanitize_filename_strips_path_and_missing():
    assert pdf_service.sanitize_filename("../../etc/passwd.pdf") == "passwd.pdf"
    assert pdf_service.sanitize_filename("C:\\Users\\a\\doc.pdf") == "doc.pdf"
    with pytest.raises(ApiError):
        pdf_service.sanitize_filename("")


def test_extract_single_page():
    content = build_pdf(["Hello world"])
    pages = extract_pages(content)
    assert len(pages) == 1
    assert pages[0].page_number == 1
    assert "Hello world" in pages[0].text


def test_extract_multiple_pages():
    content = build_pdf(
        ["Page one content"],
        ["Page two content"],
        ["Page three content"],
    )
    pages = extract_pages(content)
    assert [p.page_number for p in pages] == [1, 2, 3]
    assert all(p.text for p in pages)


def test_extract_skips_empty_pages():
    import fitz

    text_doc = fitz.open()
    page = text_doc.new_page()
    page.insert_text((72, 72), "Only real text here")

    combined = fitz.open()
    combined.insert_pdf(text_doc)
    combined.new_page()  # empty page with no text
    content = combined.tobytes()

    pages = extract_pages(content)
    assert len(pages) == 1
    assert pages[0].page_number == 1


def test_extract_failure_on_corrupt_pdf():
    with pytest.raises(PdfExtractionError):
        extract_pages(b"%PDF-1.4 garbage not a valid xref")


def test_clean_text_normalizes_whitespace():
    raw = "Line1    spaces\n\n\n\n\nLine2\n\tLine3"
    cleaned = clean_text(raw)
    assert "\n\n" not in cleaned
    assert "Line1    spaces" not in cleaned  # internal runs collapsed
    assert "Line1 spaces" in cleaned


def test_clean_text_removes_page_number_noise():
    cleaned = clean_text("Header text\n42\nFooter text")
    assert "42" not in cleaned
    assert "Header text" in cleaned


def test_extract_pdf_metadata_only_present_values():
    content = build_pdf(["x"])
    meta = extract_pdf_metadata(content)
    assert meta.as_dict() is not None  # never fails; may be empty
    assert {"title", "author", "subject", "creation_date"} >= set(meta.as_dict().keys())