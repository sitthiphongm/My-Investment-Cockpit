"""v2_premium_cockpit — Add FX support, tax lots, cash adjustments, thesis break conditions,
alert history, and user settings for the Premium Investment Cockpit upgrade.

Revision ID: 002
Revises: 001
Create Date: 2026-06-28

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add v2 tables and columns for Premium Investment Cockpit."""

    # ─── New enum types ───────────────────────────────────────────────────
    op.execute("CREATE TYPE tax_lot_status AS ENUM ('Open', 'Closed', 'Partial')")
    op.execute("CREATE TYPE condition_type AS ENUM ('price_below', 'drawdown_pct', 'time_elapsed', 'custom')")
    op.execute(
        "CREATE TYPE alert_event_type AS ENUM "
        "('Created', 'Triggered', 'Snoozed', 'Resolved', 'EmailSent', 'EmailFailed')"
    )
    op.execute("CREATE TYPE fx_staleness AS ENUM ('Fresh', 'Stale', 'Manual')")
    op.execute("CREATE TYPE theme_mode AS ENUM ('Dark', 'Light')")
    op.execute(
        "CREATE TYPE cost_basis_method AS ENUM ('FIFO', 'LIFO', 'AvgCost', 'SpecificLot')"
    )
    op.execute(
        "CREATE TYPE ai_mode AS ENUM ('Disabled', 'RuleBased', 'LocalLLM', 'HostedLLM')"
    )

    # ─── Add FX columns to transfers table ────────────────────────────────
    op.add_column("transfers", sa.Column("original_currency", sa.String(3), nullable=True, server_default="USD"))
    op.add_column("transfers", sa.Column("original_amount", sa.Numeric(14, 2), nullable=True))
    op.add_column("transfers", sa.Column("fx_rate", sa.Numeric(12, 6), nullable=True))
    op.add_column("transfers", sa.Column("converted_usd_amount", sa.Numeric(14, 2), nullable=True))
    op.add_column("transfers", sa.Column("fx_fee", sa.Numeric(10, 2), nullable=True, server_default="0"))
    op.add_column("transfers", sa.Column("fx_provider", sa.String(50), nullable=True))
    op.add_column("transfers", sa.Column("fx_source_timestamp", sa.DateTime(timezone=True), nullable=True))
    op.add_column("transfers", sa.Column("fx_fetch_timestamp", sa.DateTime(timezone=True), nullable=True))
    op.add_column("transfers", sa.Column("note", sa.Text(), nullable=True))

    # ─── Add broker column to dividend_records ────────────────────────────
    op.add_column("dividend_records", sa.Column("broker", sa.String(100), nullable=True))
    op.add_column("dividend_records", sa.Column("currency", sa.String(3), nullable=True, server_default="USD"))
    op.add_column("dividend_records", sa.Column("tax_withheld", sa.Numeric(10, 2), nullable=True, server_default="0"))
    op.add_column("dividend_records", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")))

    # ─── Tax Lots table ───────────────────────────────────────────────────
    op.create_table(
        "tax_lots",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("stock_symbol", sa.String(20), nullable=False),
        sa.Column("buy_transaction_id", sa.UUID(), nullable=False),
        sa.Column("acquisition_date", sa.Date(), nullable=False),
        sa.Column("original_quantity", sa.Integer(), nullable=False),
        sa.Column("remaining_quantity", sa.Integer(), nullable=False),
        sa.Column("cost_per_share", sa.Numeric(12, 4), nullable=False),
        sa.Column("broker", sa.String(100), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("fx_rate_at_purchase", sa.Numeric(12, 6), nullable=True),
        sa.Column(
            "status",
            sa.Enum("Open", "Closed", "Partial", name="tax_lot_status", create_type=False),
            nullable=False,
            server_default="Open",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["buy_transaction_id"], ["transactions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        comment="Tax lot tracking for cost basis methods (FIFO/LIFO/AvgCost/SpecificLot)",
    )
    op.create_index("ix_tax_lots_user_symbol", "tax_lots", ["user_id", "stock_symbol"])
    op.create_index("ix_tax_lots_user_status", "tax_lots", ["user_id", "status"])

    # ─── Cash Adjustments table ───────────────────────────────────────────
    op.create_table(
        "cash_adjustments",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("broker", sa.String(100), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("reason", sa.String(200), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        comment="Manual cash adjustments for ledger reconciliation",
    )
    op.create_index("ix_cash_adjustments_user_broker", "cash_adjustments", ["user_id", "broker"])

    # ─── FX Rate Entries table ────────────────────────────────────────────
    op.create_table(
        "fx_rate_entries",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("base_currency", sa.String(3), nullable=False),
        sa.Column("quote_currency", sa.String(3), nullable=False),
        sa.Column("rate_date", sa.Date(), nullable=False),
        sa.Column("rate", sa.Numeric(12, 6), nullable=False),
        sa.Column("provider_name", sa.String(50), nullable=True),
        sa.Column("source_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fetch_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_manual", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "staleness",
            sa.Enum("Fresh", "Stale", "Manual", name="fx_staleness", create_type=False),
            nullable=False,
            server_default="Fresh",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        comment="FX rate cache entries with audit metadata",
    )
    op.create_index(
        "ix_fx_rates_user_pair_date", "fx_rate_entries",
        ["user_id", "base_currency", "quote_currency", "rate_date"],
    )

    # ─── Thesis Break Conditions table ────────────────────────────────────
    op.create_table(
        "thesis_break_conditions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("idea_id", sa.UUID(), nullable=False),
        sa.Column(
            "condition_type",
            sa.Enum("price_below", "drawdown_pct", "time_elapsed", "custom", name="condition_type", create_type=False),
            nullable=False,
        ),
        sa.Column("threshold_value", sa.Numeric(12, 4), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("is_triggered", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["idea_id"], ["investment_ideas.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        comment="Thesis break conditions that invalidate investment ideas",
    )

    # ─── Alert History table ──────────────────────────────────────────────
    op.create_table(
        "alert_history",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("alert_id", sa.UUID(), nullable=False),
        sa.Column(
            "event",
            sa.Enum(
                "Created", "Triggered", "Snoozed", "Resolved", "EmailSent", "EmailFailed",
                name="alert_event_type", create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["alert_id"], ["price_alerts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        comment="Alert lifecycle event history",
    )

    # ─── User Settings table ──────────────────────────────────────────────
    op.create_table(
        "user_settings",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column(
            "theme",
            sa.Enum("Dark", "Light", name="theme_mode", create_type=False),
            nullable=False,
            server_default="Dark",
        ),
        sa.Column(
            "default_cost_basis_method",
            sa.Enum("FIFO", "LIFO", "AvgCost", "SpecificLot", name="cost_basis_method", create_type=False),
            nullable=False,
            server_default="FIFO",
        ),
        sa.Column(
            "ai_mode",
            sa.Enum("Disabled", "RuleBased", "LocalLLM", "HostedLLM", name="ai_mode", create_type=False),
            nullable=False,
            server_default="Disabled",
        ),
        sa.Column("email_weekly_memo", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("email_alerts_enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("email_alert_categories", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("default_broker", sa.String(100), nullable=True),
        sa.Column("default_currency", sa.String(3), nullable=True, server_default="USD"),
        sa.Column("benchmark_selections", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_user_settings_user_id"),
        comment="User preferences and configuration",
    )

    # ─── Add cash/notes fields to performance_snapshots ───────────────────
    op.add_column("performance_snapshots", sa.Column("cash_balance", sa.Numeric(14, 2), nullable=True))
    op.add_column("performance_snapshots", sa.Column("net_invested", sa.Numeric(14, 2), nullable=True))
    op.add_column("performance_snapshots", sa.Column("fx_rate_snapshot", sa.Numeric(12, 6), nullable=True))
    op.add_column("performance_snapshots", sa.Column("notes", sa.Text(), nullable=True))


def downgrade() -> None:
    """Remove v2 tables and columns."""

    # Drop columns from performance_snapshots
    op.drop_column("performance_snapshots", "notes")
    op.drop_column("performance_snapshots", "fx_rate_snapshot")
    op.drop_column("performance_snapshots", "net_invested")
    op.drop_column("performance_snapshots", "cash_balance")

    # Drop new tables
    op.drop_table("user_settings")
    op.drop_table("alert_history")
    op.drop_table("thesis_break_conditions")
    op.drop_table("fx_rate_entries")
    op.drop_table("cash_adjustments")
    op.drop_table("tax_lots")

    # Drop columns from dividend_records
    op.drop_column("dividend_records", "updated_at")
    op.drop_column("dividend_records", "tax_withheld")
    op.drop_column("dividend_records", "currency")
    op.drop_column("dividend_records", "broker")

    # Drop columns from transfers
    op.drop_column("transfers", "note")
    op.drop_column("transfers", "fx_fetch_timestamp")
    op.drop_column("transfers", "fx_source_timestamp")
    op.drop_column("transfers", "fx_provider")
    op.drop_column("transfers", "fx_fee")
    op.drop_column("transfers", "converted_usd_amount")
    op.drop_column("transfers", "fx_rate")
    op.drop_column("transfers", "original_amount")
    op.drop_column("transfers", "original_currency")

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS ai_mode")
    op.execute("DROP TYPE IF EXISTS cost_basis_method")
    op.execute("DROP TYPE IF EXISTS theme_mode")
    op.execute("DROP TYPE IF EXISTS fx_staleness")
    op.execute("DROP TYPE IF EXISTS alert_event_type")
    op.execute("DROP TYPE IF EXISTS condition_type")
    op.execute("DROP TYPE IF EXISTS tax_lot_status")
