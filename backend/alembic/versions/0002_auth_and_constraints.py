"""users, login attempts, audit actor and check constraints

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-21 10:00:00
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
    )
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=True)

    op.create_table(
        "login_attempts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("ip", sa.String(length=64), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_login_attempts")),
    )
    op.create_index("ix_login_attempts_username_created_at", "login_attempts", ["username", "created_at"])
    op.create_index("ix_login_attempts_ip_created_at", "login_attempts", ["ip", "created_at"])

    op.add_column("campaign_logs", sa.Column("user_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_campaign_logs_user_id"), "campaign_logs", ["user_id"])
    op.create_foreign_key(
        op.f("fk_campaign_logs_user_id_users"), "campaign_logs", "users", ["user_id"], ["id"], ondelete="SET NULL"
    )
    op.create_check_constraint(op.f("ck_campaign_logs_status"), "campaign_logs", "status IN ('success', 'error')")
    op.create_check_constraint(op.f("ck_campaigns_country_iso2"), "campaigns", "length(country) = 2")
    op.create_check_constraint(op.f("ck_campaigns_offer_id_positive"), "campaigns", "offer_id > 0")


def downgrade() -> None:
    op.drop_constraint(op.f("ck_campaigns_offer_id_positive"), "campaigns", type_="check")
    op.drop_constraint(op.f("ck_campaigns_country_iso2"), "campaigns", type_="check")
    op.drop_constraint(op.f("ck_campaign_logs_status"), "campaign_logs", type_="check")
    op.drop_constraint(op.f("fk_campaign_logs_user_id_users"), "campaign_logs", type_="foreignkey")
    op.drop_index(op.f("ix_campaign_logs_user_id"), table_name="campaign_logs")
    op.drop_column("campaign_logs", "user_id")
    op.drop_index("ix_login_attempts_ip_created_at", table_name="login_attempts")
    op.drop_index("ix_login_attempts_username_created_at", table_name="login_attempts")
    op.drop_table("login_attempts")
    op.drop_index(op.f("ix_users_username"), table_name="users")
    op.drop_table("users")
