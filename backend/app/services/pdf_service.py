"""PDF validation, text extraction and cleaning (PyMuPDF).

Validation never trusts the extension alone: a file must also present the
PDF magic bytes (``%PDF-``). Extraction is page-aware so later citation
rendering can point at a real page number.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from pathlib import Path

from app.core.config import settings
from app.core.errors import ApiError

# Browser/frontend may send either value; both are accepted as PDF.
ALLOWED_PDF_MIME_TYPES = frozenset({"application/pdf", "application/x-pdf"})
# Unknown uploads (octet-stream) are still accepted but must pass the magic
# byte check below.
UNKNOWN_MIME_TYPES = frozenset({"application/octet-stream"})

_PDF_MAGIC = b"%PDF-"
_MAX_HEADER_SCAN = 1024


@dataclass(frozen=True)
class ExtractedPage:
    """Clean, page-scoped text extracted from a PDF."""

    page_number: int  # 1-based
    text: str


@dataclass(frozen=True)
class PdfMetadata:
    """Optional metadata read from the PDF itself (values that exist only)."""

    title: str | None = None
    author: str | None = None
    subject: str | None = None
    creation_date: str | None = None

    def as_dict(self) -> dict[str, str]:
        return {k: v for k, v in self.__dict__.items() if v}


def sanitize_filename(filename: str | None) -> str:
    """Return a display-safe filename (no path components or control chars)."""
    if not filename or not filename.strip():
        raise ApiError("INVALID_DOCUMENT_TYPE", "Only PDF documents are supported.")
    name = Path(filename).name
    name = "".join(ch for ch in name if ch >= " " or ch in "\t")  # drop control chars
    name = name.strip()
    if not name:
        raise ApiError("INVALID_DOCUMENT_TYPE", "Only PDF documents are supported.")
    return name[:1024]


def validate_upload(*, filename: str | None, content: bytes) -> str:
    """Validate an uploaded PDF and return the sanitized filename.

    Raises structured ``ApiError`` for non-PDF, empty, or oversized files.
    """
    safe_name = sanitize_filename(filename)

    if not safe_name.lower().endswith(".pdf"):
        raise ApiError(
            "INVALID_DOCUMENT_TYPE",
            "Only PDF documents are supported.",
        )

    if not content:
        raise ApiError("EMPTY_DOCUMENT", "The uploaded file is empty.")

    if len(content) > settings.MAX_UPLOAD_SIZE_BYTES:
        raise ApiError(
            "DOCUMENT_TOO_LARGE",
            f"The uploaded file exceeds the maximum allowed size "
            f"({settings.MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)} MiB).",
        )

    if _PDF_MAGIC not in content[:_MAX_HEADER_SCAN]:
        raise ApiError(
            "INVALID_DOCUMENT_TYPE",
            "The file is not a valid PDF document.",
        )

    return safe_name


def check_mime_type(mime_type: str | None) -> None:
    if mime_type and mime_type not in ALLOWED_PDF_MIME_TYPES | UNKNOWN_MIME_TYPES:
        raise ApiError("INVALID_DOCUMENT_TYPE", "Only PDF documents are supported.")


def clean_text(text: str) -> str:
    """Deterministic normalization of extracted page text.

    Conservative by design: whitespace is normalized and obvious page-number
    noise removed, but meaningful structure (headings, lists, numbering) is
    preserved. This is not a summarizer.
    """
    if not text:
        return ""

    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\x0c", "\n")  # form feed → newline
    # Replace every horizontal control character with a space.
    text = "".join("\n" if ch in "\r\n" else (" " if ord(ch) < 32 else ch) for ch in text)

    lines = []
    for raw_line in text.split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        # Drop pure page-number lines (short all-digit lines).
        if line.isdigit() and len(line) <= 6:
            continue
        # Collapse internal whitespace runs but keep the single line intact.
        line = " ".join(line.split())
        lines.append(line)

    return "\n".join(lines)


def extract_pages(content: bytes) -> list[ExtractedPage]:
    """Extract cleaned text page-by-page from raw PDF bytes.

    Returns one entry per non-empty page, 1-based. Raises
    ``PdfExtractionError`` (an internal error caught by the ingestion service,
    never surfaced to clients) when the PDF cannot be parsed.
    """
    try:
        import fitz  # PyMuPDF
    except ImportError as exc:  # pragma: no cover - dependency is required
        raise RuntimeError("PyMuPDF is not installed.") from exc

    try:
        with fitz.open(stream=content, filetype="pdf") as doc:
            pages: list[ExtractedPage] = []
            for index in range(doc.page_count):
                page_text = clean_text(doc[index].get_text("text"))
                if page_text:
                    pages.append(ExtractedPage(page_number=index + 1, text=page_text))
            return pages
    except Exception as exc:
        raise PdfExtractionError(str(exc)) from exc


def extract_pdf_metadata(content: bytes) -> PdfMetadata:
    """Read present-only metadata from the PDF (title, author, subject, date)."""
    try:
        import fitz
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("PyMuPDF is not installed.") from exc

    try:
        with fitz.open(stream=content, filetype="pdf") as doc:
            meta = doc.metadata or {}
    except Exception as exc:
        raise PdfExtractionError(str(exc)) from exc

    def _clean(value: str | None) -> str | None:
        if not value:
            return None
        value = value.strip()
        return value or None

    return PdfMetadata(
        title=_clean(meta.get("title")),
        author=_clean(meta.get("author")),
        subject=_clean(meta.get("subject")),
        creation_date=_clean(meta.get("creationDate")),
    )


class PdfExtractionError(Exception):
    """Internal signal that a PDF could not be parsed."""
