"""Import/Export service — CSV import and JSON backup/restore."""

import csv
import io
import json
import uuid
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transaction import Transaction
from app.models.transfer import Transfer


class ImportExportService:
    """Handles CSV import, JSON backup, and restore operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def validate_csv_transactions(
        self, user_id: uuid.UUID, csv_content: str
    ) -> dict:
        """Validate a CSV file for transaction import (dry-run).

        Returns: {valid: bool, row_count: int, errors: [{row, field, message}], preview: [...]}
        """
        errors = []
        preview = []
        reader = csv.DictReader(io.StringIO(csv_content))

        required_fields = {"date", "stock_symbol", "action", "quantity", "price_per_share", "broker"}
        if reader.fieldnames:
            missing = required_fields - set(f.lower().strip() for f in reader.fieldnames)
            if missing:
                return {
                    "valid": False,
                    "row_count": 0,
                    "errors": [{"row": 0, "field": None, "message": f"Missing columns: {', '.join(missing)}"}],
                    "preview": [],
                }

        for i, row in enumerate(reader, start=1):
            row_errors = self._validate_transaction_row(row, i)
            errors.extend(row_errors)
            if not row_errors and len(preview) < 10:
                preview.append(row)

        return {
            "valid": len(errors) == 0,
            "row_count": i if reader.fieldnames else 0,
            "errors": errors,
            "preview": preview,
        }

    async def import_csv_transactions(
        self, user_id: uuid.UUID, csv_content: str
    ) -> dict:
        """Import transactions from validated CSV (atomic — all or nothing).

        Returns: {imported_count: int, errors: [...]}
        """
        validation = await self.validate_csv_transactions(user_id, csv_content)
        if not validation["valid"]:
            return {"imported_count": 0, "errors": validation["errors"]}

        reader = csv.DictReader(io.StringIO(csv_content))
        imported = 0

        for row in reader:
            qty = int(row["quantity"])
            price = Decimal(row["price_per_share"])
            fee = Decimal(row.get("brokerage_fee", "0") or "0")
            vat = Decimal(row.get("vat", "0") or "0")
            gross = qty * price
            action = row["action"].strip().capitalize()

            if action == "Buy":
                net = gross + fee + vat
            elif action == "Sell":
                net = gross - fee - vat
            else:
                net = gross

            tx = Transaction(
                user_id=user_id,
                date=date.fromisoformat(row["date"].strip()),
                stock_symbol=row["stock_symbol"].strip().upper(),
                action=action,
                quantity=qty,
                price_per_share=price,
                gross_value=gross,
                brokerage_fee=fee,
                vat=vat,
                net_capital_flow=net,
                broker=row["broker"].strip(),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            self.db.add(tx)
            imported += 1

        await self.db.flush()
        return {"imported_count": imported, "errors": []}

    async def export_transactions_csv(self, user_id: uuid.UUID) -> str:
        """Export all transactions for user as CSV string."""
        result = await self.db.execute(
            select(Transaction)
            .where(Transaction.user_id == user_id)
            .order_by(Transaction.date.desc())
        )
        transactions = result.scalars().all()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "date", "stock_symbol", "action", "quantity", "price_per_share",
            "gross_value", "brokerage_fee", "vat", "net_capital_flow", "broker",
        ])

        for tx in transactions:
            writer.writerow([
                tx.date.isoformat(), tx.stock_symbol, tx.action,
                tx.quantity, str(tx.price_per_share), str(tx.gross_value),
                str(tx.brokerage_fee), str(tx.vat), str(tx.net_capital_flow),
                tx.broker,
            ])

        return output.getvalue()

    async def export_full_backup(self, user_id: uuid.UUID) -> str:
        """Export full account data as JSON backup."""
        # Transactions
        result = await self.db.execute(
            select(Transaction).where(Transaction.user_id == user_id)
        )
        transactions = result.scalars().all()

        # Transfers
        result = await self.db.execute(
            select(Transfer).where(Transfer.user_id == user_id)
        )
        transfers = result.scalars().all()

        backup = {
            "version": "2.0",
            "exported_at": datetime.utcnow().isoformat(),
            "user_id": str(user_id),
            "transactions": [
                {
                    "date": tx.date.isoformat(),
                    "stock_symbol": tx.stock_symbol,
                    "action": tx.action,
                    "quantity": tx.quantity,
                    "price_per_share": str(tx.price_per_share),
                    "brokerage_fee": str(tx.brokerage_fee),
                    "vat": str(tx.vat),
                    "broker": tx.broker,
                }
                for tx in transactions
            ],
            "transfers": [
                {
                    "date": t.date.isoformat(),
                    "broker": t.broker,
                    "transfer_type": t.transfer_type,
                    "amount": str(t.amount),
                    "original_currency": t.original_currency,
                    "fx_rate": str(t.fx_rate) if t.fx_rate else None,
                }
                for t in transfers
            ],
        }

        return json.dumps(backup, indent=2)

    def _validate_transaction_row(self, row: dict, row_num: int) -> list[dict]:
        """Validate a single CSV row, return list of errors."""
        errors = []

        # Date validation
        date_val = row.get("date", "").strip()
        if not date_val:
            errors.append({"row": row_num, "field": "date", "message": "Date is required"})
        else:
            try:
                d = date.fromisoformat(date_val)
                if d > date.today():
                    errors.append({"row": row_num, "field": "date", "message": "Date cannot be in the future"})
            except ValueError:
                errors.append({"row": row_num, "field": "date", "message": "Invalid date format (use YYYY-MM-DD)"})

        # Symbol
        symbol = row.get("stock_symbol", "").strip()
        if not symbol:
            errors.append({"row": row_num, "field": "stock_symbol", "message": "Symbol is required"})

        # Action
        action = row.get("action", "").strip().capitalize()
        if action not in ("Buy", "Sell", "Snapshot"):
            errors.append({"row": row_num, "field": "action", "message": "Action must be Buy, Sell, or Snapshot"})

        # Quantity
        try:
            qty = int(row.get("quantity", "0"))
            if qty <= 0:
                errors.append({"row": row_num, "field": "quantity", "message": "Quantity must be positive"})
        except (ValueError, TypeError):
            errors.append({"row": row_num, "field": "quantity", "message": "Quantity must be a number"})

        # Price
        try:
            price = Decimal(row.get("price_per_share", "0"))
            if price <= 0:
                errors.append({"row": row_num, "field": "price_per_share", "message": "Price must be positive"})
        except (InvalidOperation, TypeError):
            errors.append({"row": row_num, "field": "price_per_share", "message": "Price must be a number"})

        # Broker
        broker = row.get("broker", "").strip()
        if not broker:
            errors.append({"row": row_num, "field": "broker", "message": "Broker is required"})

        return errors
