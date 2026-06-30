"""initial_schema

Revision ID: 001
Revises:
Create Date: 2025-06-27

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all initial tables."""

    # Create enum types
    op.execute("CREATE TYPE user_status AS ENUM ('Approved', 'Pending', 'Blocked')")
    op.execute("CREATE TYPE action_type AS ENUM ('Buy', 'Sell', 'Snapshot')")
    op.execute("CREATE TYPE transfer_type AS ENUM ('In', 'Out')")
    op.execute("CREATE TYPE alert_type AS ENUM ('Above', 'Below')")
    op.execute("CREATE TYPE sentiment_type AS ENUM ('Bear', 'Bull')")
    op.execute("CREATE TYPE risk_level AS ENUM ('Low', 'Medium', 'High')")
    op.execute(
        "CREATE TYPE idea_status AS ENUM ('Researching', 'Watching', 'Bought', 'Passed', 'Closed')"
    )
    op.execute("CREATE TYPE term_type AS ENUM ('Short-term', 'Long-term')")
    op.execute("CREATE TYPE target_type AS ENUM ('Symbol', 'Sector')")

    # Users table
    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("profile_picture_url", sa.String(length=1024), nullable=True),
        sa.Column("oauth_provider", sa.String(length=50), nullable=False),
        sa.Column("oauth_provider_id", sa.String(length=255), nullable=False),
        sa.Column(
            "status",
            sa.Enum("Approved", "Pending", "Blocked", name="user_status", create_type=False),
            nullable=False,
            server_default="Pending",
        ),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "registered_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        comment="User accounts with OAuth authentication",
    )

    # Transactions table
    op.create_table(
        "transactions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("stock_symbol", sa.String(length=20), nullable=False),
        sa.Column(
            "action",
            sa.Enum("Buy", "Sell", "Snapshot", name="action_type", create_type=False),
            nullable=False,
        ),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("price_per_share", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("gross_value", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column(
            "brokerage_fee",
            sa.Numeric(precision=10, scale=2),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "vat", sa.Numeric(precision=10, scale=2), nullable=False, server_default="0"
        ),
        sa.Column("net_capital_flow", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("broker", sa.String(length=100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        comment="Stock buy/sell/snapshot transactions",
    )
    op.create_index("ix_transactions_user_id", "transactions", ["user_id"])
    op.create_index("ix_transactions_user_date", "transactions", ["user_id", "date"])
    op.create_index(
        "ix_transactions_user_symbol", "transactions", ["user_id", "stock_symbol"]
    )
    op.create_index(
        "ix_transactions_user_broker", "transactions", ["user_id", "broker"]
    )

    # Transaction notes table
    op.create_table(
        "transaction_notes",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("transaction_id", sa.UUID(), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["transaction_id"], ["transactions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("transaction_id"),
    )

    # Tags table
    op.create_table(
        "tags",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "name", name="uq_tag_user_name"),
        comment="User-defined tags for categorization",
    )
    op.create_index("ix_tags_user_id", "tags", ["user_id"])

    # Transaction tags (association table)
    op.create_table(
        "transaction_tags",
        sa.Column("transaction_id", sa.UUID(), nullable=False),
        sa.Column("tag_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["transaction_id"], ["transactions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("transaction_id", "tag_id"),
    )

    # Stock tag assignments table
    op.create_table(
        "stock_tag_assignments",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("stock_symbol", sa.String(length=20), nullable=False),
        sa.Column("tag_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "stock_symbol", "tag_id", name="uq_stock_tag_assignment"
        ),
        comment="Assigns tags to stock symbols for categorization",
    )
    op.create_index("ix_stock_tag_assignments_user_id", "stock_tag_assignments", ["user_id"])
    op.create_index("ix_stock_tag_assignments_tag_id", "stock_tag_assignments", ["tag_id"])

    # Transfers table
    op.create_table(
        "transfers",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("broker", sa.String(length=100), nullable=False),
        sa.Column(
            "transfer_type",
            sa.Enum("In", "Out", name="transfer_type", create_type=False),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        comment="Money transfer records (deposits and withdrawals)",
    )
    op.create_index("ix_transfers_user_id", "transfers", ["user_id"])
    op.create_index("ix_transfers_user_date", "transfers", ["user_id", "date"])
    op.create_index("ix_transfers_user_broker", "transfers", ["user_id", "broker"])

    # Performance snapshots table
    op.create_table(
        "performance_snapshots",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column(
            "total_portfolio_value", sa.Numeric(precision=14, scale=2), nullable=False
        ),
        sa.Column("total_cost", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        comment="Portfolio performance snapshots over time",
    )
    op.create_index(
        "ix_performance_snapshots_user_id", "performance_snapshots", ["user_id"]
    )
    op.create_index(
        "ix_performance_snapshots_user_date",
        "performance_snapshots",
        ["user_id", "date"],
    )

    # Price alerts table
    op.create_table(
        "price_alerts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("stock_symbol", sa.String(length=20), nullable=False),
        sa.Column(
            "alert_type",
            sa.Enum("Above", "Below", name="alert_type", create_type=False),
            nullable=False,
        ),
        sa.Column("target_price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column("triggered", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        comment="Price alert configurations",
    )
    op.create_index("ix_price_alerts_user_id", "price_alerts", ["user_id"])
    op.create_index(
        "ix_price_alerts_user_symbol", "price_alerts", ["user_id", "stock_symbol"]
    )

    # Dividend records table
    op.create_table(
        "dividend_records",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("stock_symbol", sa.String(length=20), nullable=False),
        sa.Column(
            "amount_per_share", sa.Numeric(precision=10, scale=4), nullable=False
        ),
        sa.Column("shares_held", sa.Integer(), nullable=False),
        sa.Column("total_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        comment="Dividend payment records",
    )
    op.create_index("ix_dividend_records_user_id", "dividend_records", ["user_id"])
    op.create_index(
        "ix_dividend_records_user_symbol",
        "dividend_records",
        ["user_id", "stock_symbol"],
    )
    op.create_index(
        "ix_dividend_records_user_date", "dividend_records", ["user_id", "date"]
    )

    # Realized P/L table
    op.create_table(
        "realized_pl",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("stock_symbol", sa.String(length=20), nullable=False),
        sa.Column("sell_quantity", sa.Integer(), nullable=False),
        sa.Column("sell_price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column(
            "avg_cost_at_sale", sa.Numeric(precision=12, scale=2), nullable=False
        ),
        sa.Column("realized_pl", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("hold_duration_days", sa.Integer(), nullable=False),
        sa.Column(
            "term_type",
            sa.Enum("Short-term", "Long-term", name="term_type", create_type=False),
            nullable=False,
        ),
        sa.Column("transaction_id", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["transaction_id"], ["transactions.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        comment="Realized profit/loss records from sell transactions",
    )
    op.create_index("ix_realized_pl_user_id", "realized_pl", ["user_id"])
    op.create_index("ix_realized_pl_user_date", "realized_pl", ["user_id", "date"])
    op.create_index(
        "ix_realized_pl_user_symbol", "realized_pl", ["user_id", "stock_symbol"]
    )

    # Watchlist items table
    op.create_table(
        "watchlist_items",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("stock_symbol", sa.String(length=20), nullable=False),
        sa.Column(
            "interested_at_price", sa.Numeric(precision=12, scale=2), nullable=True
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        comment="Watchlist items for monitoring stocks",
    )
    op.create_index("ix_watchlist_items_user_id", "watchlist_items", ["user_id"])
    op.create_index(
        "ix_watchlist_items_user_symbol",
        "watchlist_items",
        ["user_id", "stock_symbol"],
    )

    # Investment ideas table
    op.create_table(
        "investment_ideas",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("stock_symbol", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("thesis", sa.Text(), nullable=True),
        sa.Column(
            "target_entry_price", sa.Numeric(precision=12, scale=2), nullable=True
        ),
        sa.Column(
            "risk_level",
            sa.Enum("Low", "Medium", "High", name="risk_level", create_type=False),
            nullable=False,
        ),
        sa.Column("source_link", sa.String(length=1024), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "Researching",
                "Watching",
                "Bought",
                "Passed",
                "Closed",
                name="idea_status",
                create_type=False,
            ),
            nullable=False,
            server_default="Researching",
        ),
        sa.Column("linked_transaction_id", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["linked_transaction_id"], ["transactions.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        comment="Investment thesis and idea tracking",
    )
    op.create_index("ix_investment_ideas_user_id", "investment_ideas", ["user_id"])
    op.create_index(
        "ix_investment_ideas_user_status", "investment_ideas", ["user_id", "status"]
    )
    op.create_index(
        "ix_investment_ideas_user_symbol",
        "investment_ideas",
        ["user_id", "stock_symbol"],
    )

    # Stock sentiments table
    op.create_table(
        "stock_sentiments",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("stock_symbol", sa.String(length=20), nullable=False),
        sa.Column(
            "sentiment",
            sa.Enum("Bear", "Bull", name="sentiment_type", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "stock_symbol", name="uq_stock_sentiment_user_symbol"
        ),
        comment="User sentiment on stocks (Bear/Bull)",
    )
    op.create_index("ix_stock_sentiments_user_id", "stock_sentiments", ["user_id"])

    # Target allocations table
    op.create_table(
        "target_allocations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("target_key", sa.String(length=50), nullable=False),
        sa.Column(
            "target_type",
            sa.Enum("Symbol", "Sector", name="target_type", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "target_percentage", sa.Numeric(precision=5, scale=2), nullable=False
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "target_key", "target_type", name="uq_target_allocation"
        ),
        comment="Target portfolio allocations for rebalancing",
    )
    op.create_index(
        "ix_target_allocations_user_id", "target_allocations", ["user_id"]
    )

    # Screener presets table
    op.create_table(
        "screener_presets",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("filter_criteria", postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        comment="Saved stock screener filter presets",
    )
    op.create_index("ix_screener_presets_user_id", "screener_presets", ["user_id"])

    # Sessions table
    op.create_table(
        "sessions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("token_hash", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
        comment="User authentication sessions",
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])
    op.create_index("ix_sessions_token_hash", "sessions", ["token_hash"])
    op.create_index("ix_sessions_expires_at", "sessions", ["expires_at"])


def downgrade() -> None:
    """Drop all tables and enum types."""

    op.drop_table("sessions")
    op.drop_table("screener_presets")
    op.drop_table("target_allocations")
    op.drop_table("stock_sentiments")
    op.drop_table("investment_ideas")
    op.drop_table("watchlist_items")
    op.drop_table("realized_pl")
    op.drop_table("dividend_records")
    op.drop_table("price_alerts")
    op.drop_table("performance_snapshots")
    op.drop_table("transfers")
    op.drop_table("stock_tag_assignments")
    op.drop_table("transaction_tags")
    op.drop_table("tags")
    op.drop_table("transaction_notes")
    op.drop_table("transactions")
    op.drop_table("users")

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS target_type")
    op.execute("DROP TYPE IF EXISTS term_type")
    op.execute("DROP TYPE IF EXISTS idea_status")
    op.execute("DROP TYPE IF EXISTS risk_level")
    op.execute("DROP TYPE IF EXISTS sentiment_type")
    op.execute("DROP TYPE IF EXISTS alert_type")
    op.execute("DROP TYPE IF EXISTS transfer_type")
    op.execute("DROP TYPE IF EXISTS action_type")
    op.execute("DROP TYPE IF EXISTS user_status")
