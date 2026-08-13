"""Document chunking for the ingestion pipeline.

Chunks are produced per page — text is never merged across page boundaries —
so every chunk retains an unambiguous page number for future citations.
Character-based sizing with overlap keeps the implementation dependency-free
and easy to tune via ``CHUNK_SIZE`` / ``CHUNK_OVERLAP``.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.services.pdf_service import ExtractedPage


@dataclass(frozen=True)
class Chunk:
    """A single chunk ready for embedding and storage."""

    page_number: int
    chunk_index: int  # global, 0-based, across the whole document
    text: str
    token_count: int  # whitespace-token estimate


def _chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    if chunk_size < 1:
        raise ValueError("chunk_size must be >= 1")
    if overlap < 0 or overlap >= chunk_size:
        overlap = chunk_size - 1 if chunk_size > 1 else 0

    if len(text) <= chunk_size:
        return [text] if text.strip() else []

    chunks: list[str] = []
    start = 0
    length = len(text)
    while start < length:
        end = min(start + chunk_size, length)
        piece = text[start:end].strip()
        if piece:
            # Avoid a tiny orphan tail by folding it into the previous chunk.
            if end == length and chunks and len(piece) < chunk_size // 2:
                chunks[-1] = f"{chunks[-1]}\n{piece}"
            else:
                chunks.append(piece)
        if end == length:
            break
        start = end - overlap
    return chunks


def chunk_pages(
    pages: list[ExtractedPage],
    *,
    chunk_size: int,
    chunk_overlap: int,
) -> list[Chunk]:
    """Chunk extracted pages in document order, preserving page numbers."""
    chunks: list[Chunk] = []
    index = 0
    for page in pages:
        for piece in _chunk_text(page.text, chunk_size, chunk_overlap):
            chunks.append(
                Chunk(
                    page_number=page.page_number,
                    chunk_index=index,
                    text=piece,
                    token_count=len(piece.split()),
                )
            )
            index += 1
    return chunks
