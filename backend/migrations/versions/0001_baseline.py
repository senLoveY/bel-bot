"""Базовая схема: таблицы, которые уже есть в рабочей базе до перехода на Alembic.

Существующую базу приложение не пересоздаёт, а помечает этой ревизией (stamp),
новую — создаёт с нуля.

Revision ID: 0001
Revises:
"""
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("first_name", sa.String(length=128), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=True),
        sa.Column("tz", sa.String(length=64), nullable=False),
        sa.Column("tz_set", sa.Boolean(), nullable=False),
        sa.Column("send_time", sa.String(length=5), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("explain_lang", sa.String(length=2), nullable=False),
        sa.Column("streak", sa.Integer(), nullable=False),
        sa.Column("longest_streak", sa.Integer(), nullable=False),
        sa.Column("last_seen_day", sa.String(length=10), nullable=True),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "cards",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("be", sa.String(length=256), nullable=False),
        sa.Column("accent", sa.String(length=256), nullable=True),
        sa.Column("ru", sa.String(length=512), nullable=False),
        sa.Column("pos", sa.String(length=64), nullable=True),
        sa.Column("example_be", sa.Text(), nullable=True),
        sa.Column("example_ru", sa.Text(), nullable=True),
        sa.Column("summary_be", sa.String(length=512), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("body_be", sa.Text(), nullable=True),
        sa.Column("month_day", sa.String(length=5), nullable=True),
        sa.Column("level", sa.String(length=4), nullable=False),
        sa.Column("topic", sa.String(length=64), nullable=True),
        sa.Column("published", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_cards_kind", "cards", ["kind"])
    op.create_index("ix_cards_month_day", "cards", ["month_day"])
    op.create_table(
        "deliveries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("card_id", sa.Integer(), nullable=False),
        sa.Column("local_date", sa.String(length=10), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(), nullable=False),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("error", sa.String(length=256), nullable=True),
        sa.ForeignKeyConstraint(["card_id"], ["cards.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "local_date", name="uq_delivery_user_date"),
    )
    op.create_index("ix_deliveries_next_attempt_at", "deliveries", ["next_attempt_at"])
    op.create_index("ix_deliveries_status", "deliveries", ["status"])
    op.create_index("ix_deliveries_user_id", "deliveries", ["user_id"])
    op.create_table(
        "saved_cards",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("card_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["card_id"], ["cards.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("user_id", "card_id"),
    )
    op.create_table(
        "schedule",
        sa.Column("day", sa.String(length=10), nullable=False),
        sa.Column("card_id", sa.Integer(), nullable=False),
        sa.Column("set_by", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(["card_id"], ["cards.id"]),
        sa.PrimaryKeyConstraint("day"),
    )
    op.create_table(
        "card_revisions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("card_id", sa.Integer(), nullable=True),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("author_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("reviewer_id", sa.BigInteger(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["card_id"], ["cards.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_card_revisions_status", "card_revisions", ["status"])


def downgrade() -> None:
    op.drop_table("card_revisions")
    op.drop_table("schedule")
    op.drop_table("saved_cards")
    op.drop_table("deliveries")
    op.drop_table("cards")
    op.drop_table("users")
