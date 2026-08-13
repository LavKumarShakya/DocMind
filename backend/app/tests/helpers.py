"""Shared helpers for tests."""

from app.core.enums import Role
from app.core.security import create_access_token


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def make_token(user_id, role: Role) -> str:
    return create_access_token(user_id, role)


def auth_headers(user) -> dict[str, str]:
    return auth_header(make_token(user.id, user.role))


def build_pdf(*pages: list[str]) -> bytes:
    """Build a real in-memory PDF from page line-lists using PyMuPDF."""
    import fitz

    doc = fitz.open()
    for lines in pages:
        page = doc.new_page()
        y = 72
        for line in lines:
            page.insert_text((72, y), line, fontsize=11)
            y += 16
    return doc.tobytes()


def multipart_file(content: bytes, filename: str, mime: str = "application/pdf"):
    return {"file": (filename, content, mime)}
