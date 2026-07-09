import asyncio
import uuid
from decimal import Decimal
from app.database import async_session_factory
from app.models.transaction import Transaction
from app.services.portfolio_service import PortfolioService
from sqlalchemy import select

async def main():
    async with async_session_factory() as session:
        stmt = (
            select(Transaction)
            .where(Transaction.stock_symbol == 'JBL')
            .order_by(Transaction.date.asc(), Transaction.created_at.asc(), Transaction.id.asc())
        )
        rows = (await session.execute(stmt)).scalars().all()
        print('DB rows:')
        for r in rows:
            print(f"{r.id} | {r.date} | {r.action} | qty={r.quantity} | price={r.price_per_share} | gross={r.gross_value} | broker={r.broker}")

        stmt2 = (
            select(Transaction.action, Transaction.quantity, Transaction.price_per_share)
            .where(Transaction.stock_symbol == 'JBL')
            .order_by(Transaction.date.asc(), Transaction.created_at.asc(), Transaction.id.asc())
        )
        result = await session.execute(stmt2)
        rows2 = result.all()
        print('\nSelected rows:')
        for row in rows2:
            print(type(row[0]), row[0], type(row[1]), row[1], type(row[2]), row[2])

        service = PortfolioService(session)
        avg_cost = await service.calculate_avg_cost(uuid.uuid4(), 'JBL')
        print('\nCalculated avg cost:', avg_cost)

asyncio.run(main())
