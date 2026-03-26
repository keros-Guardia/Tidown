"""Initial schema + lastfm api keys per user

Revision ID: 0001
Revises:
Create Date: 2024-01-01
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create users table
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("username", sa.String, unique=True, nullable=False, index=True),
        sa.Column("email", sa.String, unique=True, nullable=False),
        sa.Column("hashed_password", sa.String, nullable=False),
        sa.Column("lastfm_username", sa.String, nullable=True),
        sa.Column("lastfm_api_key", sa.String, nullable=True),
        sa.Column("lastfm_api_secret", sa.String, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=True),
    )

    # Create followed_artists table
    op.create_table(
        "followed_artists",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("artist_mbid", sa.String, nullable=True),
        sa.Column("artist_name", sa.String, nullable=False),
        sa.Column("artist_lastfm_url", sa.String, nullable=True),
        sa.Column("artist_image", sa.String, nullable=True),
        sa.Column("followed_at", sa.DateTime, nullable=True),
        sa.UniqueConstraint("user_id", "artist_name", name="uq_user_artist"),
    )


def downgrade() -> None:
    op.drop_table("followed_artists")
    op.drop_table("users")
