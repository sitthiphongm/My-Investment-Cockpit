"""Price alerts API routes."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_active_user
from app.models.user import User
from app.schemas.alerts import AlertCreate, AlertListResponse, AlertResponse
from app.services.alert_service import AlertService

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.post("", response_model=AlertResponse, status_code=201)
async def create_alert(
    data: AlertCreate,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new price alert.

    Supports multiple alerts per symbol with Above/Below types.
    """
    service = AlertService(db)
    alert = await service.create_alert(user.id, data)
    return AlertResponse(
        id=str(alert.id),
        stock_symbol=alert.stock_symbol,
        alert_type=alert.alert_type,
        target_price=alert.target_price,
        note=alert.note,
        triggered=alert.triggered,
        created_at=alert.created_at,
    )


@router.get("", response_model=AlertListResponse)
async def list_alerts(
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """List active (non-triggered) alerts sorted by symbol."""
    service = AlertService(db)
    alerts = await service.list_active_alerts(user.id)
    return AlertListResponse(
        alerts=[
            AlertResponse(
                id=str(a.id),
                stock_symbol=a.stock_symbol,
                alert_type=a.alert_type,
                target_price=a.target_price,
                note=a.note,
                triggered=a.triggered,
                created_at=a.created_at,
            )
            for a in alerts
        ]
    )


@router.delete("/{alert_id}", status_code=204)
async def delete_alert(
    alert_id: uuid.UUID,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a price alert."""
    service = AlertService(db)
    await service.delete_alert(user.id, alert_id)
