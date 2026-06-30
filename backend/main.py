"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.errors import AppError, app_error_handler
from app.redis import redis_client
from app.routers.admin import router as admin_router
from app.routers.advanced_screener import router as advanced_screener_router
from app.routers.ai_insights import router as ai_insights_router
from app.routers.alerts import router as alerts_router
from app.routers.auth import router as auth_router
from app.routers.behavioral import router as behavioral_router
from app.routers.cash_ledger import router as cash_ledger_router
from app.routers.dashboard import router as dashboard_router
from app.routers.dividends import router as dividends_router
from app.routers.ideas import router as ideas_router
from app.routers.import_export import router as import_export_router
from app.routers.journal import router as journal_router
from app.routers.performance import router as performance_router
from app.routers.portfolio import router as portfolio_router
from app.routers.position_sizing import router as position_sizing_router
from app.routers.realized_pl import router as realized_pl_router
from app.routers.screener import router as screener_router
from app.routers.settings import router as settings_router
from app.routers.simulator import router as simulator_router
from app.routers.stock_info import router as stock_info_router
from app.routers.tags import router as tags_router
from app.routers.transactions import router as transactions_router
from app.routers.transfers import router as transfers_router
from app.routers.trending import router as trending_router
from app.routers.watchlist import router as watchlist_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown events."""
    # Startup: verify Redis connection
    try:
        await redis_client.ping()
    except Exception as e:
        print(f"Warning: Redis connection failed: {e}")

    yield

    # Shutdown: close Redis connection
    await redis_client.aclose()


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register structured error handler
app.add_exception_handler(AppError, app_error_handler)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "app": settings.app_name}


# Register routers
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(advanced_screener_router)
app.include_router(ai_insights_router)
app.include_router(alerts_router)
app.include_router(behavioral_router)
app.include_router(cash_ledger_router)
app.include_router(dashboard_router)
app.include_router(dividends_router)
app.include_router(ideas_router)
app.include_router(import_export_router)
app.include_router(journal_router)
app.include_router(performance_router)
app.include_router(portfolio_router)
app.include_router(position_sizing_router)
app.include_router(realized_pl_router)
app.include_router(screener_router)
app.include_router(settings_router)
app.include_router(simulator_router)
app.include_router(stock_info_router)
app.include_router(tags_router)
app.include_router(transactions_router)
app.include_router(transfers_router)
app.include_router(trending_router)
app.include_router(watchlist_router)
