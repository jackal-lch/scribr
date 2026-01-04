"""Add method column to transcripts table

Revision ID: c003_add_transcript_method
Revises: c002_add_video_metadata
Create Date: 2024-01-04

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c003_add_transcript_method'
down_revision: Union[str, None] = 'c002_add_video_metadata'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add method column to track extraction method (caption or ai)
    op.add_column('transcripts', sa.Column('method', sa.String(20), server_default='caption', nullable=True))


def downgrade() -> None:
    op.drop_column('transcripts', 'method')
