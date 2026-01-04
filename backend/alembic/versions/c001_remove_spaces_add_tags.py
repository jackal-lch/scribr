"""Remove spaces, add user_id and tags to channels

Revision ID: c001_remove_spaces
Revises: be3131327d29
Create Date: 2025-01-04

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'c001_remove_spaces'
down_revision: Union[str, None] = 'be3131327d29'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add user_id column to channels (nullable for now)
    op.add_column('channels', sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True))

    # 2. Add tags column
    op.add_column('channels', sa.Column('tags', postgresql.ARRAY(sa.String()), server_default='{}', nullable=False))

    # 3. Migrate data: copy user_id from spaces to channels
    op.execute("""
        UPDATE channels
        SET user_id = spaces.user_id
        FROM spaces
        WHERE channels.space_id = spaces.id
    """)

    # 4. Make user_id NOT NULL
    op.alter_column('channels', 'user_id', nullable=False)

    # 5. Add foreign key for user_id
    op.create_foreign_key('fk_channels_user_id', 'channels', 'users', ['user_id'], ['id'], ondelete='CASCADE')

    # 6. Drop old unique constraint
    op.drop_constraint('uq_space_channel', 'channels', type_='unique')

    # 7. Drop foreign key to spaces
    op.drop_constraint('channels_space_id_fkey', 'channels', type_='foreignkey')

    # 8. Drop space_id column
    op.drop_column('channels', 'space_id')

    # 9. Add new unique constraint (user_id + youtube_channel_id)
    op.create_unique_constraint('uq_user_channel', 'channels', ['user_id', 'youtube_channel_id'])

    # 10. Drop spaces table
    op.drop_table('spaces')


def downgrade() -> None:
    # Recreate spaces table
    op.create_table('spaces',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    )

    # Add space_id back to channels
    op.add_column('channels', sa.Column('space_id', postgresql.UUID(as_uuid=True), nullable=True))

    # Drop new unique constraint
    op.drop_constraint('uq_user_channel', 'channels', type_='unique')

    # Drop user_id foreign key
    op.drop_constraint('fk_channels_user_id', 'channels', type_='foreignkey')

    # Drop tags and user_id columns
    op.drop_column('channels', 'tags')
    op.drop_column('channels', 'user_id')

    # Note: Data migration back would require recreating spaces - not implemented
