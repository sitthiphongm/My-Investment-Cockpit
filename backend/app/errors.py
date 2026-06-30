"""Standardized error handling for the API.

Provides consistent error response format and reusable exception classes
per the design document's error handling specification.
"""

from typing import Any

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class ErrorDetail(BaseModel):
    """Field-level error detail."""

    field: str | None = None
    message: str


class ErrorResponse(BaseModel):
    """Standardized error response wrapper."""

    code: str
    message: str
    details: list[ErrorDetail] = []


class AppError(HTTPException):
    """Application-level error with structured response."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: list[dict[str, Any]] | None = None,
    ):
        self.error_code = code
        self.error_message = message
        self.error_details = details or []
        super().__init__(status_code=status_code, detail=message)


# ─── Pre-defined error factories ─────────────────────────────────────────────


def validation_error(message: str, details: list[dict[str, Any]] | None = None) -> AppError:
    """400 — Input validation failed."""
    return AppError(400, "VALIDATION_ERROR", message, details)


def missing_field(field_name: str) -> AppError:
    """400 — Required field not provided."""
    return AppError(400, "MISSING_FIELD", f"Required field missing: {field_name}",
                    [{"field": field_name, "message": "This field is required"}])


def insufficient_holdings(symbol: str, requested: int, available: int) -> AppError:
    """400 — Sell/delete would create negative quantity."""
    return AppError(
        400, "INSUFFICIENT_HOLDINGS",
        f"Cannot sell {requested} shares of {symbol}: only {available} available",
        [{"field": "quantity", "message": f"Available: {available}"}],
    )


def invalid_cash_state(broker: str, message: str) -> AppError:
    """400 — Operation would create invalid cash ledger."""
    return AppError(400, "INVALID_CASH_STATE", message,
                    [{"field": "broker", "message": f"Broker: {broker}"}])


def fx_rate_required(currency: str) -> AppError:
    """400 — Non-USD transfer missing FX rate."""
    return AppError(
        400, "FX_RATE_REQUIRED",
        f"FX rate is required for {currency} transfers",
        [{"field": "fx_rate", "message": f"Provide FX rate for {currency} to USD conversion"}],
    )


def not_found(resource: str = "Resource") -> AppError:
    """404 — Resource not found."""
    return AppError(404, "NOT_FOUND", f"{resource} not found")


def access_denied() -> AppError:
    """403 — No permission."""
    return AppError(403, "ACCESS_DENIED", "Access denied")


def provider_unavailable(provider: str) -> AppError:
    """502 — External provider failed."""
    return AppError(502, "MARKET_DATA_UNAVAILABLE", f"Provider '{provider}' is unavailable")


def provider_rate_limited(provider: str) -> AppError:
    """429 — Provider rate limit reached."""
    return AppError(429, "PROVIDER_RATE_LIMITED", f"Rate limit reached for '{provider}'")


# ─── Exception handler for FastAPI app ────────────────────────────────────────


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Convert AppError exceptions to structured JSON responses."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.error_code,
                "message": exc.error_message,
                "details": exc.error_details,
            }
        },
    )
