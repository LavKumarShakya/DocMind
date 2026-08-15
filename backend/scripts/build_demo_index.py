"""Build the pre-indexed public demo document (one-time, idempotent).

Run from the ``backend/`` directory:

    python -m scripts.build_demo_index

Reads the demo PDF (``DEMO_DOCUMENT_PATH``), extracts text, chunks it with the
project's existing chunking settings, embeds it with the configured embedding
model and stores the pgvector vectors in PostgreSQL — the same persistent
vector store used by normal ingestion. Re-running is safe (existing chunks for
the demo document are replaced, never duplicated) and re-running with no new
PDF content is effectively a no-op once the index exists.

Use ``--force`` to rebuild even when the index already exists.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings  # noqa: E402
from app.core.errors import ApiError  # noqa: E402
from app.db.database import SessionLocal  # noqa: E402
from app.services import demo_service  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Rebuild the demo index even when it already exists.",
    )
    args = parser.parse_args()

    with SessionLocal() as db:
        if not args.force and demo_service.demo_index_ready(db):
            print(
                "Demo index already exists and is ready. "
                "Use --force to rebuild it from the current PDF."
            )
            return 0

        if not settings.DEMO_MODE:
            print(
                "Note: DEMO_MODE is false. The demo document can still be built; "
                "set DEMO_MODE=true in the environment to expose the public demo."
            )
        print(f"Demo PDF: {demo_service.resolve_demo_document_path()}")
        print(
            f"Embedding model: {settings.EMBEDDING_MODEL} ({settings.EMBEDDING_DIM} dims)"
        )

        try:
            document = demo_service.build_demo_index(db)
        except ApiError as exc:
            print(f"ERROR [{exc.code}]: {exc.message}", file=sys.stderr)
            return 1
        except Exception as exc:  # pragma: no cover - unexpected build failure
            print(f"ERROR: demo index build failed: {exc}", file=sys.stderr)
            return 1

        print(
            f"Demo index ready: {document.title!r} "
            f"({document.page_count} pages, "
            f"{demo_service.demo_chunk_count(db)} chunks)."
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())