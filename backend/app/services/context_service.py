"""Assemble retrieval evidence into a compact, tag-labelled context block.

Each retrieved chunk is prefixed with ``[n]`` so the LLM can cite evidence by
tag. The block is truncated to ``MAX_CONTEXT_CHARS`` — truncation always cuts
whole chunks from the tail so citation tags never point at half-included
evidence.
"""

from __future__ import annotations

from app.core.config import settings
from app.services.retrieval_service import RetrievedChunk

TAG = "[{index}] {text}"


def build_context(results: list[RetrievedChunk], *, max_chars: int | None = None) -> str:
    """Build a labelled context block from retrieved chunks, newest-score first.

    Returns the rendered context string. Chunks beyond ``max_chars`` are
    dropped whole from the tail; tags always stay consistent with the chunks
    actually included.
    """
    max_chars = max_chars if max_chars is not None else settings.MAX_CONTEXT_CHARS

    included: list[tuple[int, str]] = []
    used_chars = 0
    for index, chunk in enumerate(results, start=1):
        entry = TAG.format(index=index, text=chunk.text)
        if used_chars + len(entry) > max_chars:
            break
        included.append((index, entry))
        used_chars += len(entry)

    return "\n\n".join(entry for _, entry in included)


def included_indexes(context: str) -> list[int]:
    """Return the citation tags present in a rendered context block."""
    indexes: list[int] = []
    for line in context.split("\n"):
        stripped = line.strip()
        if stripped.startswith("[") and "] " in stripped:
            try:
                indexes.append(int(stripped.split("]")[0][1:]))
            except ValueError:
                continue
    return indexes