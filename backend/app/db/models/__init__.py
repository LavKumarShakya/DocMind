"""Import all ORM models so Alembic can discover them.

Do not remove this module while the project uses Alembic autogeneration.
"""

from app.db.models.citation import Citation
from app.db.models.conversation import Conversation
from app.db.models.document import Document
from app.db.models.document_chunk import DocumentChunk
from app.db.models.document_version import DocumentVersion
from app.db.models.feedback import Feedback
from app.db.models.message import Message
from app.db.models.user import User

__all__ = [
    "User",
    "Document",
    "DocumentChunk",
    "DocumentVersion",
    "Conversation",
    "Message",
    "Citation",
    "Feedback",
]