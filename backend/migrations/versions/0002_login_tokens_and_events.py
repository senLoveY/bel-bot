"""Одноразовые токены входа в базе и события для аналитики.

Revision ID: 0002
Revises: 0001
"""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "used_login_tokens",
        sa.Column("nonce", sa.String(length=64), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("nonce"),
    )
    op.create_index("ix_used_login_tokens_used_at", "used_login_tokens", ["used_at"])
    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("card_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_events_created_at", "events", ["created_at"])
    op.create_index("ix_events_kind", "events", ["kind"])
    op.create_index("ix_events_user_id", "events", ["user_id"])


def downgrade() -> None:
    op.drop_table("events")
    op.drop_table("used_login_tokens")
