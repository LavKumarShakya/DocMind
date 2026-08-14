"""Local filesystem storage for uploaded documents.

The rest of the application only talks to the functions here — it never
constructs filesystem paths itself. That keeps storage swappable: a later
phase can replace the body of these functions with S3 / Azure Blob / GCS
calls without touching routes or services.

Stored layout (relative paths are what the ``documents.file_path`` column
holds, so absolute server paths are never exposed to clients):

    <STORAGE_DIR>/
        documents/
            <document_id>/
                original.pdf
"""

from __future__ import annotations

import uuid
from pathlib import Path

from app.core.config import settings
from app.core.errors import ApiError

_DOCUMENTS_SUBDIR = "documents"
_STORED_FILENAME = "original.pdf"


def get_storage_root() -> Path:
    """Absolute path to the configured storage root."""
    root = Path(settings.STORAGE_DIR)
    if not root.is_absolute():
        root = Path.cwd() / root
    return root.resolve()


def _safe_resolve(relative_path: str) -> Path:
    """Resolve a DB-stored relative path, refusing to escape the storage root."""
    root = get_storage_root()
    resolved = (root / relative_path).resolve()
    if not resolved.is_relative_to(root):
        raise ApiError(
            "INVALID_STORAGE_PATH",
            "The stored file path is invalid.",
            status_code=500,
        )
    return resolved


def save_document_file(document_id: uuid.UUID, content: bytes) -> str:
    """Persist ``content`` under ``documents/<id>/original.pdf``.

    Returns the relative storage path (what goes into ``documents.file_path``).
    """
    directory = get_storage_root() / _DOCUMENTS_SUBDIR / str(document_id)
    directory.mkdir(parents=True, exist_ok=True)

    relative = Path(_DOCUMENTS_SUBDIR) / str(document_id) / _STORED_FILENAME
    path = directory / _STORED_FILENAME
    path.write_bytes(content)
    return relative.as_posix()


def save_document_version_file(
    document_id: uuid.UUID, version_number: int, content: bytes
) -> str:
    """Persist a new version's file under ``documents/<id>/versions/<n>/original.pdf``.

    Version files live in their own subdirectory so uploading a new version
    never overwrites a historical version's bytes.
    """
    relative = (
        Path(_DOCUMENTS_SUBDIR)
        / str(document_id)
        / "versions"
        / str(version_number)
        / _STORED_FILENAME
    )
    path = get_storage_root() / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return relative.as_posix()


def read_document_file(relative_path: str) -> bytes:
    """Read the stored bytes for a document."""
    path = _safe_resolve(relative_path)
    if not path.is_file():
        raise ApiError(
            "DOCUMENT_FILE_MISSING",
            "The stored document file is missing.",
            status_code=500,
        )
    return path.read_bytes()


def delete_document_file(relative_path: str) -> None:
    """Remove the stored file (and its document directory)."""
    path = _safe_resolve(relative_path)
    directory = path.parent
    try:
        path.unlink(missing_ok=True)
        # Remove the (now empty) per-document directory.
        while directory != get_storage_root():
            directory.rmdir()
            directory = directory.parent
    except OSError:
        # Non-empty directory is not an error; other files can be removed
        # by the caller in the same operation. Failures here must never
        # cascade into an API error.
        pass


def delete_document_files(relative_paths: list[str]) -> None:
    """Remove multiple stored files (current file + every version file).

    Cleanup is best-effort: leftover bytes must never fail a request that has
    already committed the database state.
    """
    for relative_path in relative_paths:
        try:
            delete_document_file(relative_path)
        except Exception:  # pragma: no cover - defensive cleanup
            pass
