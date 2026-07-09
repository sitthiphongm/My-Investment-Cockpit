"""Trading transaction API routes."""

import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user_id
from app.schemas.enums import ActionType
from app.schemas.transactions import (
    SnapshotCreate,
    TransactionCreate,
    TransactionFilters,
    TransactionResponse,
    TransactionUpdate,
)
from app.services.excel_service import ExcelExportService, ExcelImportService
from app.services.journal_service import JournalService
from app.services.trading_service import TradingService

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


@router.post("", response_model=TransactionResponse, status_code=201)
async def create_transaction(
    data: TransactionCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Create a new buy/sell transaction."""
    service = TradingService(db)
    transaction = await service.create_transaction(user_id, data)
    return _to_response(transaction)


@router.get("", response_model=list[TransactionResponse])
async def list_transactions(
    date_from: Optional[date] = Query(None, description="Filter: start date"),
    date_to: Optional[date] = Query(None, description="Filter: end date"),
    symbol: Optional[str] = Query(None, description="Filter: stock symbol"),
    stock_symbol: Optional[str] = Query(None, description="Filter: stock symbol alias"),
    broker: Optional[str] = Query(None, description="Filter: broker name"),
    action: Optional[ActionType] = Query(None, description="Filter: action type"),
    tag: Optional[str] = Query(None, description="Filter: tag name"),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """List transactions with optional filters, including tag filter."""
    effective_symbol = symbol or stock_symbol
    filters = TransactionFilters(
        date_from=date_from,
        date_to=date_to,
        stock_symbol=effective_symbol,
        broker=broker,
        action=action,
        tag=tag,
    )
    service = TradingService(db)
    transactions = await service.list_transactions(user_id, filters)
    return [_to_response(tx) for tx in transactions]


@router.put("/{transaction_id}", response_model=TransactionResponse)
async def edit_transaction(
    transaction_id: uuid.UUID,
    data: TransactionUpdate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Edit an existing transaction."""
    service = TradingService(db)
    transaction = await service.edit_transaction(user_id, transaction_id, data)
    return _to_response(transaction)


@router.delete("/{transaction_id}", status_code=204)
async def delete_transaction(
    transaction_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Delete a transaction."""
    service = TradingService(db)
    await service.delete_transaction(user_id, transaction_id)


@router.post("/snapshot", response_model=list[TransactionResponse], status_code=201)
async def import_snapshot(
    data: SnapshotCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Bulk import snapshot entries."""
    service = TradingService(db)
    transactions = await service.import_snapshot(user_id, data)
    return [_to_response(tx) for tx in transactions]


@router.get("/export-excel")
async def export_transactions_excel(
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    symbol: Optional[str] = Query(None),
    stock_symbol: Optional[str] = Query(None),
    broker: Optional[str] = Query(None),
    action: Optional[ActionType] = Query(None),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Export transactions as an Excel (.xlsx) file."""
    effective_symbol = symbol or stock_symbol
    filters = TransactionFilters(
        date_from=date_from,
        date_to=date_to,
        stock_symbol=effective_symbol,
        broker=broker,
        action=action,
    )
    trading_service = TradingService(db)
    transactions = await trading_service.list_transactions(user_id, filters)

    export_service = ExcelExportService(db)
    buffer = await export_service.export_transactions(user_id, transactions)

    filename = f"trading_log_{date.today().isoformat()}.xlsx"
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/import-excel/preview")
async def preview_import_excel(
    file: UploadFile = File(...),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Preview and validate an Excel file for import without committing."""
    if not file.filename or not file.filename.endswith(".xlsx"):
        return {"error": "File must be an .xlsx Excel file"}

    file_bytes = await file.read()
    import_service = ExcelImportService(db)
    result = await import_service.preview_import(user_id, file_bytes)
    return result


@router.post("/import-excel")
async def import_transactions_excel(
    file: UploadFile = File(...),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Import transactions from an Excel file. Atomic: all or nothing."""
    if not file.filename or not file.filename.endswith(".xlsx"):
        return {"error": "File must be an .xlsx Excel file"}

    file_bytes = await file.read()
    import_service = ExcelImportService(db)

    try:
        result = await import_service.import_transactions(user_id, file_bytes)
        await db.commit()
        return result
    except ValueError as e:
        await db.rollback()
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail=str(e))


def _to_response(transaction) -> TransactionResponse:
    """Convert a Transaction ORM model to the response schema."""
    tags = [tag.name for tag in transaction.tags] if transaction.tags else []
    note_text = transaction.note.note if transaction.note else None
    return TransactionResponse(
        id=str(transaction.id),
        date=transaction.date,
        stock_symbol=transaction.stock_symbol,
        action=ActionType(transaction.action),
        quantity=transaction.quantity,
        price_per_share=transaction.price_per_share,
        gross_value=transaction.gross_value,
        brokerage_fee=transaction.brokerage_fee,
        vat=transaction.vat,
        net_capital_flow=transaction.net_capital_flow,
        broker=transaction.broker,
        note=note_text,
        tags=tags,
        created_at=transaction.created_at,
        updated_at=transaction.updated_at,
    )
