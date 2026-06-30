"""Cash Ledger API router — broker-level cash accounting."""

import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user_id
from app.services.cash_ledger_service import CashLedgerService

router = APIRouter(prefix="/api/cash-ledger", tags=["cash-ledger"])


class BrokerCashLedgerResponse(BaseModel):
    broker: str
    deposits: Decimal
    withdrawals: Decimal
    buy_outflows: Decimal
    sell_inflows: Decimal
    fees: Decimal
    dividends: Decimal
    fx_adjustments: Decimal
    manual_adjustments: Decimal
    ending_cash: Decimal
    is_negative: bool


class CashSummaryResponse(BaseModel):
    total_cash_available: Decimal
    brokers: list[BrokerCashLedgerResponse]


class CashAdjustmentCreate(BaseModel):
    date: date
    broker: str = Field(min_length=1, max_length=100)
    amount: Decimal
    reason: str = Field(min_length=1, max_length=200)
    note: str | None = None


@router.get("", response_model=CashSummaryResponse)
async def get_cash_ledger(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Get cash ledger for all brokers with total available cash."""
    service = CashLedgerService(db)
    ledgers = await service.get_ledger_by_broker(user_id)
    total = sum(l.ending_cash for l in ledgers)

    return CashSummaryResponse(
        total_cash_available=total,
        brokers=[
            BrokerCashLedgerResponse(
                broker=l.broker,
                deposits=l.deposits,
                withdrawals=l.withdrawals,
                buy_outflows=l.buy_outflows,
                sell_inflows=l.sell_inflows,
                fees=Decimal("0"),  # Fees are included in buy/sell net_capital_flow
                dividends=l.dividends,
                fx_adjustments=l.fx_adjustments,
                manual_adjustments=l.manual_adjustments,
                ending_cash=l.ending_cash,
                is_negative=l.is_negative,
            )
            for l in ledgers
        ],
    )


@router.get("/summary")
async def get_total_cash(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Get total cash available across all brokers."""
    service = CashLedgerService(db)
    total = await service.get_total_cash(user_id)
    return {"total_cash_available": total}


@router.post("/adjustments")
async def create_cash_adjustment(
    data: CashAdjustmentCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Create a manual cash adjustment entry."""
    from app.models.cash_adjustment import CashAdjustment

    adjustment = CashAdjustment(
        user_id=user_id,
        date=data.date,
        broker=data.broker,
        amount=data.amount,
        reason=data.reason,
        note=data.note,
    )
    db.add(adjustment)
    await db.flush()
    await db.refresh(adjustment)
    return {
        "id": str(adjustment.id),
        "date": adjustment.date.isoformat(),
        "broker": adjustment.broker,
        "amount": str(adjustment.amount),
        "reason": adjustment.reason,
        "note": adjustment.note,
    }
