"""Add transcript_error to videos

Revision ID: c004_add_transcript_error
Revises: c003_add_transcript_method
Create Date: 2025-01-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c004_add_transcript_error'
down_revision: Union[str, None] = 'c003_add_transcript_method'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('videos', sa.Column('transcript_error', sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column('videos', 'transcript_error')
