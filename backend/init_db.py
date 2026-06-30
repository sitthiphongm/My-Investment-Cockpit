"""Initialize database tables. Used for fresh deployments without Alembic migrations."""
import asyncio
from sqlalchemy import text
from app.database import engine, Base

# Import all models so they register with Base.metadata
import app.models  # noqa: F401


async def init():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Migrate quantity column from INTEGER to NUMERIC if needed
    async with engine.begin() as conn:
        try:
            await conn.execute(text(
                "ALTER TABLE transactions ALTER COLUMN quantity TYPE NUMERIC(14,6) USING quantity::NUMERIC(14,6)"
            ))
            print("Migrated transactions.quantity to NUMERIC(14,6)")
        except Exception:
            pass  # Column might already be the right type

    print("Database tables created successfully.")


if __name__ == "__main__":
    asyncio.run(init())
