"""Add additional video metadata fields

Revision ID: c002_add_video_metadata
Revises: c001_remove_spaces_add_tags
Create Date: 2024-01-04

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'c002_add_video_metadata'
down_revision: Union[str, None] = 'c001_remove_spaces'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new metadata columns to videos table
    op.add_column('videos', sa.Column('like_count', sa.BigInteger(), nullable=True))
    op.add_column('videos', sa.Column('comment_count', sa.BigInteger(), nullable=True))
    op.add_column('videos', sa.Column('tags', postgresql.ARRAY(sa.String()), server_default='{}', nullable=True))
    op.add_column('videos', sa.Column('category_id', sa.String(10), nullable=True))
    op.add_column('videos', sa.Column('definition', sa.String(10), nullable=True))  # hd, sd
    op.add_column('videos', sa.Column('caption', sa.Boolean(), nullable=True))  # has YouTube captions
    op.add_column('videos', sa.Column('default_language', sa.String(20), nullable=True))
    op.add_column('videos', sa.Column('default_audio_language', sa.String(20), nullable=True))

    # Change view_count to BigInteger (some videos have billions of views)
    op.alter_column('videos', 'view_count',
                    existing_type=sa.Integer(),
                    type_=sa.BigInteger(),
                    existing_nullable=True)


def downgrade() -> None:
    op.alter_column('videos', 'view_count',
                    existing_type=sa.BigInteger(),
                    type_=sa.Integer(),
                    existing_nullable=True)

    op.drop_column('videos', 'default_audio_language')
    op.drop_column('videos', 'default_language')
    op.drop_column('videos', 'caption')
    op.drop_column('videos', 'definition')
    op.drop_column('videos', 'category_id')
    op.drop_column('videos', 'tags')
    op.drop_column('videos', 'comment_count')
    op.drop_column('videos', 'like_count')
