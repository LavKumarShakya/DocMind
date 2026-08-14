"""phase6 product features conversations feedback versions

Revision ID: fb6d0884a5e8
Revises: 9bf464844c80
Create Date: 2026-08-14 10:36:40.046560

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fb6d0884a5e8'
down_revision: Union[str, None] = '9bf464844c80'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'document_versions',
        sa.Column('document_id', sa.Uuid(), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('status', sa.Enum('UPLOADED', 'PROCESSING', 'ACTIVE', 'ARCHIVED', 'FAILED', name='document_status', native_enum=False, length=32), nullable=False),
        sa.Column('filename', sa.String(length=1024), nullable=False),
        sa.Column('storage_path', sa.String(length=1024), nullable=False),
        sa.Column('file_size', sa.BigInteger(), nullable=False),
        sa.Column('page_count', sa.Integer(), nullable=True),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('processing_error', sa.Text(), nullable=True),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_document_versions_document_id'), 'document_versions', ['document_id'], unique=False)
    op.create_index(op.f('ix_document_versions_status'), 'document_versions', ['status'], unique=False)
    op.create_index(op.f('ix_document_versions_version_number'), 'document_versions', ['version_number'], unique=False)

    # Citations now store document provenance so persisted citations survive
    # chunk/document deletion.
    op.add_column('citations', sa.Column('document_id', sa.Uuid(), nullable=True))
    op.add_column('citations', sa.Column('document_title', sa.String(length=500), nullable=True))
    op.add_column('citations', sa.Column('section', sa.String(length=500), nullable=True))
    op.create_index(op.f('ix_citations_document_id'), 'citations', ['document_id'], unique=False)
    op.create_foreign_key(
        'fk_citations_document_id_documents',
        'citations', 'documents', ['document_id'], ['id'], ondelete='SET NULL',
    )

    # Conversation list ordering (updated_at DESC) and message ordering.
    op.create_index('ix_conversations_updated_at', 'conversations', ['updated_at'], unique=False)
    op.create_index('ix_conversations_user_id_updated_at', 'conversations', ['user_id', 'updated_at'], unique=False)

    # Point each document at its current version (the RAG-default version).
    op.add_column('documents', sa.Column('current_version_id', sa.Uuid(), nullable=True))
    op.create_index(op.f('ix_documents_current_version_id'), 'documents', ['current_version_id'], unique=False)
    op.create_foreign_key(
        'fk_documents_current_version_id_document_versions',
        'documents', 'document_versions', ['current_version_id'], ['id'], ondelete='SET NULL',
    )

    # One rating per assistant message per user. Dedupe any historical rows
    # first (keep the newest rating) so the unique constraint can be created.
    op.execute(
        """
        DELETE FROM feedback a USING feedback b
        WHERE a.user_id = b.user_id
          AND a.message_id = b.message_id
          AND a.created_at < b.created_at
        """
    )
    op.create_unique_constraint('uq_feedback_user_message', 'feedback', ['user_id', 'message_id'])

    # Deterministic per-conversation message ordering. Existing rows default to
    # position 0; new messages are assigned positions by conversation_service.
    op.add_column(
        'messages',
        sa.Column('position', sa.Integer(), nullable=False, server_default=sa.text('0')),
    )
    op.create_index('ix_messages_conversation_id_created_at', 'messages', ['conversation_id', 'created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_messages_conversation_id_created_at', table_name='messages')
    op.drop_column('messages', 'position')
    op.drop_constraint('uq_feedback_user_message', 'feedback', type_='unique')
    op.drop_constraint('fk_documents_current_version_id_document_versions', 'documents', type_='foreignkey')
    op.drop_index(op.f('ix_documents_current_version_id'), table_name='documents')
    op.drop_column('documents', 'current_version_id')
    op.drop_index('ix_conversations_user_id_updated_at', table_name='conversations')
    op.drop_index('ix_conversations_updated_at', table_name='conversations')
    op.drop_constraint('fk_citations_document_id_documents', 'citations', type_='foreignkey')
    op.drop_index(op.f('ix_citations_document_id'), table_name='citations')
    op.drop_column('citations', 'section')
    op.drop_column('citations', 'document_title')
    op.drop_column('citations', 'document_id')
    op.drop_index(op.f('ix_document_versions_version_number'), table_name='document_versions')
    op.drop_index(op.f('ix_document_versions_status'), table_name='document_versions')
    op.drop_index(op.f('ix_document_versions_document_id'), table_name='document_versions')
    op.drop_table('document_versions')