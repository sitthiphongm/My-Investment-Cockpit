"""Import/Export API router — CSV import, JSON backup/restore."""

import uuid

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user_id
from app.services.import_export_service import ImportExportService

router = APIRouter(prefix="/api/import-export", tags=["import-export"])


class ImportValidationError(BaseModel):
    row: int
    field: str | None
    message: str


class ImportPreviewResponse(BaseModel):
    valid: bool
    row_count: int
    errors: list[ImportValidationError]
    preview: list[dict]


class ImportResultResponse(BaseModel):
    imported_count: int
    errors: list[ImportValidationError]


@router.post("/import/preview", response_model=ImportPreviewResponse)
async def preview_import(
    file: UploadFile = File(...),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Preview and validate a CSV import without committing.

    Upload a CSV file with columns: date, stock_symbol, action, quantity, price_per_share, broker.
    Optional columns: brokerage_fee, vat.
    """
    content = await file.read()
    csv_text = content.decode("utf-8-sig")

    service = ImportExportService(db)
    result = await service.validate_csv_transactions(user_id, csv_text)

    return ImportPreviewResponse(
        valid=result["valid"],
        row_count=result["row_count"],
        errors=[ImportValidationError(**e) for e in result["errors"]],
        preview=result["preview"],
    )


@router.post("/import", response_model=ImportResultResponse)
async def import_transactions(
    file: UploadFile = File(...),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Import transactions from a validated CSV file (atomic — all or nothing).

    Upload the same CSV file after previewing. All rows must pass validation.
    """
    content = await file.read()
    csv_text = content.decode("utf-8-sig")

    service = ImportExportService(db)
    result = await service.import_csv_transactions(user_id, csv_text)

    return ImportResultResponse(
        imported_count=result["imported_count"],
        errors=[ImportValidationError(**e) for e in result["errors"]],
    )


@router.get("/export/transactions")
async def export_transactions_csv(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Export all transactions as CSV."""
    service = ImportExportService(db)
    csv_content = await service.export_transactions_csv(user_id)
    return PlainTextResponse(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=transactions.csv"},
    )


@router.get("/export/backup")
async def export_full_backup(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Export full account data as JSON backup."""
    service = ImportExportService(db)
    json_content = await service.export_full_backup(user_id)
    return PlainTextResponse(
        content=json_content,
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=investment_backup.json"},
    )
