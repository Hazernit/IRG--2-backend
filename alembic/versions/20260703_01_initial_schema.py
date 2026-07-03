"""Create obligations and payments tables.

Revision ID: 20260703_01
Revises:
Create Date: 2026-07-03
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260703_01"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


category_enum = postgresql.ENUM(
    "subscription", "warranty", "bill", "insurance", name="obligation_category"
)
recurrence_enum = postgresql.ENUM("monthly", "quarterly", "yearly", name="recurrence")
status_enum = postgresql.ENUM("active", "cancelled", "expired", name="obligation_status")
currency_enum = postgresql.ENUM("RUB", "USD", "EUR", name="currency")


def upgrade() -> None:
    bind = op.get_bind()
    category_enum.create(bind, checkfirst=True)
    recurrence_enum.create(bind, checkfirst=True)
    status_enum.create(bind, checkfirst=True)
    currency_enum.create(bind, checkfirst=True)

    op.create_table(
        "obligations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column(
            "currency",
            postgresql.ENUM(name="currency", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "category",
            postgresql.ENUM(name="obligation_category", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "recurrence",
            postgresql.ENUM(name="recurrence", create_type=False),
            nullable=True,
        ),
        sa.Column("next_payment_date", sa.Date(), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(name="obligation_status", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("amount > 0", name="positive_amount"),
        sa.PrimaryKeyConstraint("id", name="pk_obligations"),
    )
    op.create_index("ix_obligations_title", "obligations", ["title"])
    op.create_index(
        "ix_obligations_status_next_payment",
        "obligations",
        ["status", "next_payment_date"],
    )
    op.create_index(
        "ix_obligations_category_status", "obligations", ["category", "status"]
    )

    op.create_table(
        "payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("obligation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column(
            "currency",
            postgresql.ENUM(name="currency", create_type=False),
            nullable=False,
        ),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["obligation_id"],
            ["obligations.id"],
            name="fk_payments_obligation_id_obligations",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint("amount > 0", name="positive_amount"),
        sa.PrimaryKeyConstraint("id", name="pk_payments"),
    )
    op.create_index("ix_payments_obligation_id", "payments", ["obligation_id"])


def downgrade() -> None:
    op.drop_table("payments")
    op.drop_table("obligations")

    bind = op.get_bind()
    currency_enum.drop(bind, checkfirst=True)
    status_enum.drop(bind, checkfirst=True)
    recurrence_enum.drop(bind, checkfirst=True)
    category_enum.drop(bind, checkfirst=True)
