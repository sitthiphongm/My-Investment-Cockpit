# My Investment Cockpit

A **Premium Personal Investment Cockpit** — a full-stack web application for serious investors to track trades, monitor portfolios, analyze performance, manage risk, and receive AI-powered insights. Built with a provider-agnostic market data architecture supporting free-tier MVP operation with upgrade path to paid providers.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12+ / FastAPI / SQLAlchemy 2.0 (async) / Alembic |
| Frontend | React 19 / TypeScript / Vite / Tailwind CSS / Recharts / TanStack Query / Zustand |
| Database | PostgreSQL 16 |
| Cache | Redis 7 |
| Auth | OAuth 2.0 (Google + Facebook) with HTTP-only session cookies |
| Market Data | Provider-agnostic (FMP, Alpha Vantage, Twelve Data, EODHD, yfinance fallback) |
| AI | Rule-based MVP (upgradeable to local/hosted LLM) |
| Infrastructure | Docker Compose (dev) / Azure Container Apps (prod) / nginx |

## Features

### Portfolio & Trading
- Buy/Sell/Snapshot transaction management with full validation
- Multi-currency money transfers with FX rate tracking (THB/USD)
- Cash ledger per broker (deposits, withdrawals, buys, sells, fees, dividends)
- Tax lot accounting (FIFO, LIFO, Average Cost, Specific Lot)
- Realized P/L with short-term/long-term classification

### Market Data & Analytics
- Provider-agnostic market data with circuit breaker, rate limiter, and fallback chains
- Portfolio summary with market enrichment (P/E, beta, sector, 52-week range)
- Performance history with benchmark comparison (S&P 500, QQQ, custom)
- Portfolio attribution by stock, sector, broker, tag, strategy
- Portfolio Health Score (0-100) with breakdown

### Intelligence & Tools
- Behavioral analytics (win rate, payoff ratio, holding patterns)
- AI weekly memo and trade reviews (rule-based MVP, LLM-ready)
- Scenario simulator (what-if modeling without mutating data)
- Position sizing calculator (risk-based)
- Stock screener with strategy presets
- Price alerts and smart alerts (concentration, drawdown, thesis review)
- Investment thesis board with break condition monitoring
- Sector heatmap visualization

### Platform
- Dark Trading Dashboard UI (Bloomberg-inspired, light mode available)
- Multi-user with OAuth + admin approval workflow
- Per-user data isolation
- CSV import/export + JSON full backup
- Email notifications (SMTP, SendGrid, Mailgun — pluggable)
- Responsive layout

---

## Quick Start (Docker Compose)

The fastest way to run everything locally.

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running

### Steps

```bash
# 1. Clone the repository
git clone <repo-url>
cd "My Investment Cockpit"

# 2. Copy environment template
cp .env.example .env

# 3. (Optional) Add OAuth credentials to .env for login to work
#    See "OAuth Setup" section below

# 4. Build and start all services
docker compose up --build

# 5. Access the application
#    Frontend:  http://localhost
#    API Docs:  http://localhost:8000/docs
#    Health:    http://localhost:8000/health
```

### Services

| Service | Image | Port | Description |
|---------|-------|------|-------------|
| frontend | node:20 + nginx:alpine | 80 | React SPA with API proxy |
| backend | python:3.12-slim | 8000 | FastAPI with Alembic migrations |
| db | postgres:16-alpine | 5432 | Persistent financial data |
| redis | redis:7-alpine | 6379 | Market data cache, rate limiting |

### Commands

```bash
docker compose up --build     # Build and start
docker compose up -d          # Start in background
docker compose down           # Stop containers
docker compose down -v        # Stop + remove volumes (wipes DB)
docker compose logs backend   # View backend logs
```

---

## Local Development (without Docker)

### Prerequisites

- Python 3.12+
- Node.js 20+
- PostgreSQL 16+
- Redis 7+

### Backend

```bash
cd backend

# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS/Linux

# Install dependencies
pip install -r requirements-dev.txt

# Copy env and configure
cp .env.example .env
# Edit .env: set DATABASE_URL, REDIS_URL, OAuth keys

# Run database migrations
alembic upgrade head

# Start development server
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start dev server (proxies /api to localhost:8000 via nginx.conf in Docker,
# or configure VITE_API_BASE_URL for direct connection)
npm run dev
```

Frontend: `http://localhost:5173` | Backend API: `http://localhost:8000/docs`

### Running Tests

```bash
cd backend
venv\Scripts\activate

# Full test suite (610 tests, ~2 min)
pytest tests/ -v

# Property-based tests only
pytest tests/test_pbt_*.py -v

# Unit tests only
pytest tests/ --ignore=tests/test_integration.py --ignore=tests/test_pbt_*.py -v

# With coverage
pytest tests/ --cov=app --cov-report=html
```

---

## Environment Variables

All configuration is via environment variables. See `.env.example` for the full list.

### Required

| Variable | Description |
|----------|-------------|
| `SECRET_KEY` | Random string for session signing |
| `DATABASE_URL` | PostgreSQL async connection string |
| `REDIS_URL` | Redis connection string |

### OAuth (required for login)

| Variable | Description |
|----------|-------------|
| `GOOGLE_CLIENT_ID` | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret |
| `FACEBOOK_CLIENT_ID` | Facebook OAuth app ID |
| `FACEBOOK_CLIENT_SECRET` | Facebook OAuth app secret |
| `OAUTH_REDIRECT_BASE_URL` | Backend public URL for callbacks |

### Market Data Providers (optional for MVP)

| Variable | Default | Description |
|----------|---------|-------------|
| `MARKET_DATA_PROVIDER` | `yfinance` | Primary: fmp, alpha_vantage, twelve_data, eodhd, yfinance |
| `MARKET_DATA_FALLBACK` | `yfinance` | Fallback provider |
| `FMP_API_KEY` | — | Financial Modeling Prep API key |
| `FX_PROVIDER` | `manual` | FX rate source: unirate, alpha_vantage, manual |
| `AI_PROVIDER` | `disabled` | AI mode: disabled, rule_based, local_llm, hosted_llm |
| `EMAIL_PROVIDER` | `smtp` | Email: smtp, sendgrid, mailgun, ses |
| `EMAIL_DEV_MODE` | `true` | Write emails to logs instead of sending |

---

## Deploy to Azure

### Option A: Azure Container Apps (Recommended)

Best for: Managed scaling, simple deployment, cost-effective.

#### 1. Create Azure Resources

```bash
az login

RESOURCE_GROUP="rg-investment-cockpit"
LOCATION="southeastasia"
ACR_NAME="investmentcockpitcr"

# Resource group
az group create --name $RESOURCE_GROUP --location $LOCATION

# Container Registry
az acr create --resource-group $RESOURCE_GROUP --name $ACR_NAME --sku Basic
az acr login --name $ACR_NAME

# PostgreSQL Flexible Server
az postgres flexible-server create \
  --resource-group $RESOURCE_GROUP \
  --name cockpit-db \
  --location $LOCATION \
  --admin-user pgadmin \
  --admin-password '<STRONG_PASSWORD>' \
  --sku-name Standard_B1ms \
  --tier Burstable \
  --version 16

az postgres flexible-server db create \
  --resource-group $RESOURCE_GROUP \
  --server-name cockpit-db \
  --database-name investment_history

# Azure Cache for Redis
az redis create \
  --resource-group $RESOURCE_GROUP \
  --name cockpit-redis \
  --location $LOCATION \
  --sku Basic \
  --vm-size c0
```

#### 2. Build and Push Images

```bash
# Backend
docker build -t $ACR_NAME.azurecr.io/backend:latest ./backend
docker push $ACR_NAME.azurecr.io/backend:latest

# Frontend (set production API URL)
docker build \
  --build-arg VITE_API_BASE_URL=https://cockpit-backend.<REGION>.azurecontainerapps.io \
  -t $ACR_NAME.azurecr.io/frontend:latest \
  ./frontend
docker push $ACR_NAME.azurecr.io/frontend:latest
```

#### 3. Deploy Container Apps

```bash
# Create environment
az containerapp env create \
  --name cockpit-env \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION

# Backend
az containerapp create \
  --name cockpit-backend \
  --resource-group $RESOURCE_GROUP \
  --environment cockpit-env \
  --image $ACR_NAME.azurecr.io/backend:latest \
  --registry-server $ACR_NAME.azurecr.io \
  --target-port 8000 \
  --ingress external \
  --min-replicas 1 \
  --env-vars \
    DATABASE_URL="postgresql+asyncpg://pgadmin:<PW>@cockpit-db.postgres.database.azure.com:5432/investment_history?ssl=require" \
    REDIS_URL="rediss://:<KEY>@cockpit-redis.redis.cache.windows.net:6380/0" \
    SECRET_KEY="<RANDOM_SECRET>" \
    MARKET_DATA_PROVIDER="fmp" \
    FMP_API_KEY="<YOUR_FMP_KEY>" \
    AI_PROVIDER="rule_based" \
    GOOGLE_CLIENT_ID="<ID>" \
    GOOGLE_CLIENT_SECRET="<SECRET>" \
    FACEBOOK_CLIENT_ID="<ID>" \
    FACEBOOK_CLIENT_SECRET="<SECRET>" \
    OAUTH_REDIRECT_BASE_URL="https://cockpit-backend.<REGION>.azurecontainerapps.io" \
    FRONTEND_URL="https://cockpit-frontend.<REGION>.azurecontainerapps.io" \
    CORS_ORIGINS='["https://cockpit-frontend.<REGION>.azurecontainerapps.io"]'

# Frontend
az containerapp create \
  --name cockpit-frontend \
  --resource-group $RESOURCE_GROUP \
  --environment cockpit-env \
  --image $ACR_NAME.azurecr.io/frontend:latest \
  --registry-server $ACR_NAME.azurecr.io \
  --target-port 80 \
  --ingress external \
  --min-replicas 1
```

#### 4. Run Database Migrations

```bash
az containerapp job create \
  --name cockpit-migrate \
  --resource-group $RESOURCE_GROUP \
  --environment cockpit-env \
  --image $ACR_NAME.azurecr.io/backend:latest \
  --registry-server $ACR_NAME.azurecr.io \
  --trigger-type Manual \
  --replica-timeout 300 \
  --env-vars DATABASE_URL="<SAME_AS_BACKEND>" \
  --command "alembic" "upgrade" "head"

az containerapp job start --name cockpit-migrate --resource-group $RESOURCE_GROUP
```

### Option B: Azure App Service

Best for: Teams already using App Service, simpler CI/CD integration.

```bash
# App Service Plan
az appservice plan create \
  --name cockpit-plan \
  --resource-group $RESOURCE_GROUP \
  --is-linux --sku B1

# Backend Web App
az webapp create \
  --resource-group $RESOURCE_GROUP \
  --plan cockpit-plan \
  --name cockpit-api \
  --deployment-container-image-name $ACR_NAME.azurecr.io/backend:latest

az webapp config appsettings set \
  --resource-group $RESOURCE_GROUP \
  --name cockpit-api \
  --settings WEBSITES_PORT=8000 DATABASE_URL="<URL>" REDIS_URL="<URL>" SECRET_KEY="<KEY>"

az webapp config set \
  --resource-group $RESOURCE_GROUP \
  --name cockpit-api \
  --startup-file "alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 8000"

# Frontend (Azure Static Web Apps)
cd frontend
VITE_API_BASE_URL=https://cockpit-api.azurewebsites.net npm run build
# Deploy dist/ to Azure Static Web Apps or Blob Storage + CDN
```

---

## OAuth Setup

### Google

1. [Google Cloud Console](https://console.cloud.google.com/apis/credentials) → Create OAuth 2.0 Client ID
2. Add redirect URI: `{OAUTH_REDIRECT_BASE_URL}/api/auth/callback/google`
3. Copy Client ID + Secret to `.env`

### Facebook

1. [Facebook Developers](https://developers.facebook.com/apps/) → Create App → Add Facebook Login
2. Add redirect URI: `{OAUTH_REDIRECT_BASE_URL}/api/auth/callback/facebook`
3. Copy App ID + Secret to `.env`

---

## Project Structure

```
My Investment Cockpit/
├── backend/
│   ├── app/
│   │   ├── config.py                    # Provider-agnostic settings
│   │   ├── database.py                  # SQLAlchemy async engine
│   │   ├── dependencies.py              # Auth + user isolation middleware
│   │   ├── errors.py                    # Structured error handling
│   │   ├── redis.py                     # Redis client
│   │   ├── infrastructure/
│   │   │   └── providers/               # Market data adapter layer
│   │   │       ├── base.py              # Protocol interfaces
│   │   │       ├── circuit_breaker.py   # Resilience pattern
│   │   │       ├── fmp_adapter.py       # Financial Modeling Prep
│   │   │       └── yfinance_adapter.py  # yfinance (fallback)
│   │   ├── models/                      # 22 SQLAlchemy ORM models
│   │   ├── routers/                     # 22 API route modules
│   │   ├── schemas/                     # Pydantic request/response
│   │   └── services/                    # 21 business logic services
│   ├── alembic/versions/                # Database migrations (v1 + v2)
│   ├── tests/                           # 610 tests (unit + PBT + integration)
│   ├── main.py                          # FastAPI entry point
│   ├── requirements.txt                 # Production dependencies
│   ├── requirements-dev.txt             # Dev/test dependencies
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── api/                         # Axios API client
│   │   ├── components/                  # Shared UI (DataTable, Navigation, etc.)
│   │   ├── hooks/                       # React Query hooks
│   │   ├── lib/                         # TanStack Query client
│   │   ├── pages/                       # 21 page components
│   │   ├── store/                       # Zustand state (theme, sidebar)
│   │   ├── types/                       # TypeScript interfaces
│   │   └── utils/                       # Formatting, theme tokens
│   ├── package.json
│   ├── nginx.conf                       # Production nginx (SPA + API proxy)
│   └── Dockerfile                       # Multi-stage (Node build + nginx)
├── docker-compose.yml                   # Full-stack local deployment
├── .env.example                         # All environment variables
├── .dockerignore
└── README.md
```

---

## API Documentation

When the backend is running, interactive API docs are available at:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

### API Modules (22 routers)

| Module | Prefix | Description |
|--------|--------|-------------|
| Auth | `/api/auth` | OAuth login, callback, logout, /me |
| Admin | `/api/admin` | User approval/block (admin only) |
| Transactions | `/api/transactions` | Trading log CRUD + snapshot import |
| Transfers | `/api/transfers` | Money transfers with FX |
| Cash Ledger | `/api/cash-ledger` | Broker cash accounting |
| Portfolio | `/api/portfolio` | Summary, attribution, heatmap, health score |
| Performance | `/api/performance` | Snapshots, returns, benchmark |
| Dashboard | `/api/dashboard` | Aggregated overview |
| Alerts | `/api/alerts` | Price + smart alerts |
| Dividends | `/api/dividends` | Dividend tracking + projections |
| Realized P/L | `/api/realized-pl` | Tax lot accounting |
| Watchlist | `/api/watchlist` | Monitored stocks |
| Ideas | `/api/ideas` | Thesis board + break conditions |
| Screener | `/api/screener` | Stock screener + presets |
| Tags | `/api/tags` | Custom categorization |
| Trending | `/api/trending` | Market movers (cached) |
| Journal | `/api/journal` | Notes + tag management |
| Behavioral | `/api/behavioral` | Win rate, patterns, analytics |
| AI Insights | `/api/ai` | Weekly memo, trade review |
| Simulator | `/api/simulator` | What-if scenario modeling |
| Import/Export | `/api/import-export` | CSV import, JSON backup |
| Position Sizing | `/api/rebalancing` | Risk-based sizing calculator |

---

## Notes

- The first user to register automatically becomes Admin
- New users require admin approval before accessing the app
- All investment data is fully isolated per user
- Market data is cached in Redis (1h for portfolio, 15min for trending)
- The system remains fully functional without external market data providers (internal accounting works offline)
- AI insights use rule-based generation by default (no paid API required)
- All monetary values support USD with optional THB conversion via FX rates

## License

Private — not for redistribution.
#   M y - I n v e s t m e n t - C o c k p i t  
 