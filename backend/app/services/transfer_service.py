"""Transfer service - Business logic for money transfer operations."""

import uuid
from datetime import datetime
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transfer import Transfer
from app.schemas.enums import Currency
from app.schemas.transfers import TransferCreate, TransferFilters, TransferUpdate


class TransferService:
    """Service for managing money transfer records (deposits/withdrawals)."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_transfer(self, user_id: uuid.UUID, data: TransferCreate) -> Transfer:
        """Create a new money transfer record with FX conversion support.

        FX logic:
        - USD transfers: converted_usd_amount = original_amount (or amount), fx_rate = 1.0
        - Non-USD transfers: converted_usd_amount = original_amount / fx_rate
        - The 'amount' field is always set to the USD equivalent for backward compatibility.

        Validation is handled by the Pydantic schema (TransferCreate).
        This method persists the validated data and returns the created record.
        """
        now = datetime.utcnow()

        # Determine original currency (default to USD if not specified)
        original_currency = data.original_currency or Currency.USD

        if original_currency == Currency.USD:
            # USD transfer: use amount directly
            original_amount = data.original_amount if data.original_amount is not None else data.amount
            fx_rate = Decimal("1.0")
            converted_usd_amount = original_amount
        else:
            # Non-USD transfer (e.g. THB): calculate conversion
            # Schema validation ensures original_amount and fx_rate are present for non-USD
            original_amount = data.original_amount  # type: ignore[assignment]
            fx_rate = data.fx_rate  # type: ignore[assignment]
            converted_usd_amount = original_amount / fx_rate

        # Round to 2 decimal places for USD amount
        converted_usd_amount = converted_usd_amount.quantize(Decimal("0.01"))

        transfer = Transfer(
            id=uuid.uuid4(),
            user_id=user_id,
            date=data.date,
            broker=data.broker,
            transfer_type=data.transfer_type.value,
            # 'amount' field set to USD equivalent for backward compatibility
            amount=converted_usd_amount,
            # FX fields
            original_currency=original_currency.value,
            original_amount=original_amount,
            fx_rate=fx_rate,
            converted_usd_amount=converted_usd_amount,
            fx_fee=data.fx_fee if data.fx_fee is not None else Decimal("0"),
            note=data.note,
            # Audit fields
            fx_provider="manual",
            fx_source_timestamp=None,
            fx_fetch_timestamp=now,
            created_at=now,
            updated_at=now,
        )
        self.db.add(transfer)
        await self.db.flush()
        await self.db.refresh(transfer)
        return transfer

    async def edit_transfer(
        self, user_id: uuid.UUID, transfer_id: uuid.UUID, data: TransferUpdate
    ) -> Transfer:
        """Edit an existing money transfer record.

        When FX fields change, recalculates converted_usd_amount.
        Preserves audit history via updated_at timestamp.
        Raises HTTPException(404) if the record does not exist or does not belong to the user.
        """
        transfer = await self._get_transfer_or_404(user_id, transfer_id)

        update_data = data.model_dump(exclude_unset=True)

        # Apply basic field updates
        for field, value in update_data.items():
            if value is not None:
                if field == "transfer_type":
                    setattr(transfer, field, value.value)
                elif field == "original_currency":
                    setattr(transfer, field, value.value)
                elif field in ("original_amount", "fx_rate", "fx_fee", "note", "date", "broker", "amount"):
                    setattr(transfer, field, value)

        # Recalculate converted_usd_amount if FX-related fields were updated
        fx_fields_changed = any(
            f in update_data for f in ("original_currency", "original_amount", "fx_rate")
        )

        if fx_fields_changed:
            # Determine the current state of FX fields after updates
            current_currency = transfer.original_currency or "USD"
            if current_currency == "USD":
                # USD transfer: converted amount equals original amount
                original_amount = transfer.original_amount if transfer.original_amount is not None else transfer.amount
                transfer.fx_rate = Decimal("1.0")
                transfer.converted_usd_amount = original_amount
                transfer.amount = original_amount
            else:
                # Non-USD: require fx_rate for recalculation
                if transfer.fx_rate is None or transfer.fx_rate <= 0:
                    raise HTTPException(
                        status_code=422,
                        detail="fx_rate is required when original_currency is not USD",
                    )
                if transfer.original_amount is None or transfer.original_amount <= 0:
                    raise HTTPException(
                        status_code=422,
                        detail="original_amount is required when original_currency is not USD",
                    )
                converted = (transfer.original_amount / transfer.fx_rate).quantize(Decimal("0.01"))
                transfer.converted_usd_amount = converted
                transfer.amount = converted

            # Update audit timestamp for FX change
            transfer.fx_fetch_timestamp = datetime.utcnow()

        transfer.updated_at = datetime.utcnow()
        await self.db.flush()
        await self.db.refresh(transfer)
        return transfer

    async def delete_transfer(self, user_id: uuid.UUID, transfer_id: uuid.UUID) -> None:
        """Delete a money transfer record.

        Raises HTTPException(404) if the record does not exist or does not belong to the user.
        """
        transfer = await self._get_transfer_or_404(user_id, transfer_id)
        await self.db.delete(transfer)
        await self.db.flush()

    async def list_transfers(
        self, user_id: uuid.UUID, filters: TransferFilters
    ) -> list[Transfer]:
        """List money transfer records sorted by date descending.

        Supports optional broker filter (case-insensitive exact match).
        Returns an empty list if no records match.
        """
        stmt = select(Transfer).where(Transfer.user_id == user_id)

        if filters.broker is not None:
            stmt = stmt.where(Transfer.broker.ilike(filters.broker))

        if filters.date_from is not None:
            stmt = stmt.where(Transfer.date >= filters.date_from)

        if filters.date_to is not None:
            stmt = stmt.where(Transfer.date <= filters.date_to)

        stmt = stmt.order_by(Transfer.date.desc(), Transfer.created_at.desc())

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def _get_transfer_or_404(
        self, user_id: uuid.UUID, transfer_id: uuid.UUID
    ) -> Transfer:
        """Fetch a transfer by ID, ensuring it belongs to the given user.

        Raises HTTPException(404) if not found.
        """
        stmt = select(Transfer).where(
            Transfer.id == transfer_id,
            Transfer.user_id == user_id,
        )
        result = await self.db.execute(stmt)
        transfer = result.scalar_one_or_none()
        if transfer is None:
            raise HTTPException(
                status_code=404,
                detail="Transfer record not found",
            )
        return transfer
