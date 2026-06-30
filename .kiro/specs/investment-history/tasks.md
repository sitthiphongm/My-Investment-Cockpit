# Implementation Plan: Investment History โ€” Premium Personal Investment Cockpit

## Overview

This implementation plan follows a three-phase approach aligned with the requirements document. Phase 1 (MVP Core) establishes the foundation with internal accounting, authentication, and deployment. Phase 2 (Market Data & Analytics) adds external market data, performance tracking, and portfolio intelligence. Phase 3 (Premium Intelligence) delivers AI insights, behavioral analytics, advanced tools, and mobile responsiveness.

**Technology Stack:** FastAPI + Python 3.12+, React 18+ TypeScript, PostgreSQL 16, Redis 7, SQLAlchemy 2.0/Alembic, Tailwind CSS, Recharts/Tremor, Docker Compose.

---

## Phase 1 โ€” MVP Core

## Tasks

- [x] 1. Project scaffolding and infrastructure setup
  - [x] 1.1 Initialize backend project structure with FastAPI, SQLAlchemy, Alembic, and pytest
    - Create `backend/` directory with `app/`, `tests/`, `alembic/` structure
    - Set up `pyproject.toml` with dependencies: fastapi, uvicorn, sqlalchemy[asyncio], asyncpg, alembic, pydantic, redis, httpx, hypothesis, pytest, pytest-asyncio
    - Configure Alembic for async PostgreSQL migrations
    - Create base SQLAlchemy models, database session factory, and settings module
    - Set up pytest configuration with hypothesis profile
    - _Requirements: 43.1, 43.2, 43.5, 44.1_

  - [x] 1.2 Initialize frontend project structure with React, TypeScript, and Tailwind CSS
    - Create `frontend/` directory with Vite + React 18 + TypeScript template
    - Install and configure Tailwind CSS with dark/light theme tokens from design
    - Set up React Router v6, Zustand state management, React Query (TanStack Query)
    - Configure Vitest + React Testing Library + fast-check
    - Create design token constants matching the Dark Trading Dashboard theme
    - _Requirements: 36.1, 36.2, 36.6, 43.3_

  - [x] 1.3 Create Docker Compose configuration for development environment
    - Define services: `db` (postgres:16), `redis` (redis:7-alpine), `backend` (python:3.12-slim), `frontend` (node:20 + nginx:alpine)
    - Configure volumes, networks, health checks, and port mappings
    - Create `.env.example` with all required environment variables from design
    - Create `docker-compose.yml` and `docker-compose.override.yml` for dev hot-reload
    - _Requirements: 43.1, 43.5, 43.6_

  - [x] 1.4 Create initial database migrations for core models
    - Create Alembic migration for: `users`, `sessions`, `transactions`, `transaction_notes`, `tags`, `transaction_tags`, `transfers`, `cash_adjustments`, `user_settings`
    - Include all fields, constraints, indexes, and foreign keys per design ERD
    - Add composite indexes for (user_id, date), (user_id, stock_symbol), (user_id, broker)
    - _Requirements: 1.7, 1.8, 3.1, 4.1, 39.1, 41.1_

  - [x] 1.5 Implement shared backend infrastructure (error handling, middleware, dependencies)
    - Create consistent API error response format per design (error code, message, details)
    - Implement auth middleware for session validation and user extraction
    - Create Pydantic base schemas with validators for common types (UUID, date, Decimal)
    - Implement pagination helper (offset/limit with total count)
    - Create dependency injection for database sessions and current user
    - _Requirements: 44.3, 44.4, 44.5_

- [x] 2. Authentication and user management
  - [x] 2.1 Implement OAuth 2.0 authentication with Google and Facebook
    - Create `/api/auth/login/google`, `/api/auth/login/facebook` endpoints
    - Create `/api/auth/callback/google`, `/api/auth/callback/facebook` handlers
    - Implement session creation with secure HTTP-only cookies
    - Create `/api/auth/me` endpoint returning user info + status
    - Create `/api/auth/logout` endpoint to terminate session
    - Handle OAuth failure gracefully with error redirect
    - _Requirements: 39.1, 39.2, 39.3, 39.4, 39.5_

  - [x] 2.2 Implement admin user management and approval workflow
    - First registered user becomes Admin automatically
    - New users start as Pending until approved
    - Create `/api/admin/users` GET, `/api/admin/users/{id}/approve`, `/block`, `/revert` endpoints
    - Block non-admin access to admin endpoints
    - Blocked users denied access; Pending users see approval-pending page
    - _Requirements: 40.1, 40.2, 40.3, 40.4, 40.5_

  - [x]* 2.3 Write unit tests for authentication and admin services
    - Test OAuth callback handling and session creation/expiry
    - Test first-user-admin rule and status transitions (Pendingโ’Approvedโ’Blockedโ’Pending)
    - Test non-admin rejection from admin endpoints
    - _Requirements: 39.1, 40.1_

  - [x] 2.4 Implement per-user data isolation middleware
    - All repository queries scoped by authenticated user_id
    - Access to other user's resources returns 403 without revealing resource details
    - Shared market data cache allowed across users
    - _Requirements: 41.1, 41.2, 41.3, 41.4_

  - [x]* 2.5 Write property test for per-user data isolation
    - **Property 32: Per-User Data Isolation**
    - Generate multi-user data sets; verify querying as user A never returns user B's records
    - **Validates: Requirements 41.1, 41.2, 41.3**

- [x] 3. Trading Log โ€” Core transaction CRUD
  - [x] 3.1 Implement transaction creation service and API endpoint
    - Create `POST /api/transactions` with full validation
    - Auto-calculate gross_value (qty ร— price) and net_capital_flow (buy: +fees, sell: -fees)
    - Validate required fields, reject future dates, invalid formats, qty โค 0, price โค 0
    - Reject sell if quantity exceeds current holdings for the symbol
    - Assign unique transaction ID and persist
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8_

  - [x]* 3.2 Write property tests for transaction calculations
    - **Property 1: Transaction Calculation Correctness**
    - Generate random qty, price, fee, vat; verify gross_value = Qร—P and net_capital_flow formulas
    - **Validates: Requirements 1.1, 1.3, 1.4**

  - [x]* 3.3 Write property test for invalid transaction rejection
    - **Property 2: Invalid Transaction Rejection**
    - Generate transactions with missing/invalid fields; verify rejection with field-level errors
    - **Validates: Requirements 1.2, 1.6**

  - [x]* 3.4 Write property test for holdings non-negativity invariant
    - **Property 3: Holdings Non-Negativity Invariant**
    - Generate buy/sell/snapshot sequences; verify total held quantity never goes negative
    - **Validates: Requirements 1.5, 6.2**

  - [x] 3.5 Implement bulk snapshot import
    - Create `POST /api/transactions/snapshot` for atomic bulk import
    - Validate all rows; reject entire batch if any fail
    - Report all row-level validation errors
    - Snapshot entries included in holdings, cost basis, allocation calculations
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

  - [x]* 3.6 Write property test for snapshot import atomicity
    - **Property 4: Snapshot Import Atomicity**
    - Generate batches with invalid entries; verify entire batch rejected, no partial persistence
    - **Validates: Requirements 2.4, 2.5**

  - [x] 3.7 Implement transaction list, edit, delete, and export
    - Create `GET /api/transactions` with filters: date_range, symbol, broker, action, tag, strategy, status
    - Create `GET /api/transactions/{id}`, `PUT /api/transactions/{id}`, `DELETE /api/transactions/{id}`
    - Default sort by date descending
    - Reject edits/deletes causing negative holdings or invalid cash
    - Recalculate derived values after edit/delete
    - Create `GET /api/transactions/export` for CSV export
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 6.1, 6.2, 6.3, 6.4_

  - [x]* 3.8 Write property tests for query sort order and filter logic
    - **Property 9: Query Sort Order** โ€” Verify trading log sorted date descending regardless of filters
    - **Property 10: Filter AND Logic Correctness** โ€” Verify all returned items satisfy ALL active filters
    - **Validates: Requirements 5.1, 5.2**

  - [x]* 3.9 Write property test for edit recalculation consistency
    - **Property 11: Edit Recalculation Consistency**
    - Generate transactions, edit one; verify ID unchanged and all derived values consistent with full recalculation
    - **Validates: Requirements 6.1, 6.3**

- [x] 4. Money Transfers and FX Support
  - [x] 4.1 Implement money transfer CRUD with FX conversion
    - Create `POST /api/transfers` with FX calculation (converted_usd = amount / fx_rate)
    - Require FX rate for non-USD transfers (reject if missing and no auto-fetch)
    - Store both original amount and converted USD value
    - Store fx_provider, fx_source_timestamp, fx_fetch_timestamp for auditability
    - Create `GET /api/transfers`, `PUT /api/transfers/{id}`, `DELETE /api/transfers/{id}`, `GET /api/transfers/export`
    - Preserve audit history on edits
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.10, 3.11_

  - [x]* 4.2 Write property tests for FX conversion
    - **Property 5: FX Conversion Correctness** โ€” Verify converted_usd = amount / fx_rate for all non-USD transfers
    - **Property 36: Non-USD Transfer Requires FX Rate** โ€” Verify non-USD without FX rate is rejected
    - **Validates: Requirements 3.1, 3.3, 3.4, 3.5**

  - [x] 4.3 Implement FX rate caching and manual entry
    - Create `GET /api/settings/fx-rates` and `POST /api/settings/fx-rates` for manual entry
    - Cache FX rates by currency pair and date in database
    - Mark stale when no valid rate available for date
    - Return cached rate when available for auto-population in transfer form
    - _Requirements: 3.8, 3.9, 3.10, 3.11_

- [x] 5. Cash Ledger
  - [x] 5.1 Implement cash ledger calculation service
    - Calculate broker-level cash: deposits - withdrawals - buys + sells - fees + dividends ยฑ adjustments
    - Create `GET /api/cash-ledger` (by broker) and `GET /api/cash-ledger/summary` (total)
    - Create `POST /api/cash-ledger/adjustments` for manual entries with notes
    - Generate warning when calculated balance is negative
    - Create `GET /api/cash-ledger/export` for CSV export
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

  - [x]* 5.2 Write property tests for cash ledger
    - **Property 7: Cash Ledger Accounting Invariant** โ€” Verify formula: ending = start + deposits - withdrawals - buys + sells - fees + dividends ยฑ adjustments
    - **Property 8: Negative Cash Warning** โ€” Verify warning generated when balance < 0
    - **Validates: Requirements 4.1, 4.3, 4.4**

- [x] 6. Checkpoint โ€” Phase 1 Backend Core
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Dashboard โ€” MVP internal metrics
  - [x] 7.1 Implement dashboard API endpoint with internal metrics
    - Create `GET /api/dashboard` returning: Total Portfolio Value, Net Invested (from transfers), Total Gain/Loss, Overall ROI, Cash Available, recent transactions
    - Calculate Net Invested from sum of In transfers (USD) minus Out transfers (USD)
    - Include What_Changed section (changes since last login)
    - Include Action_Needed section (placeholder for Phase 2 alerts)
    - _Requirements: 9.1, 9.2, 9.3_

  - [x]* 7.2 Write property test for FX-aware dashboard aggregation
    - **Property 6: FX-Aware Dashboard Aggregation**
    - Generate mixed-currency transfers; verify Total Invested = ฮฃ(In converted_usd), Total Withdrawn = ฮฃ(Out converted_usd), Net = Total In - Total Out
    - **Validates: Requirements 3.6, 9.1**

- [x] 8. Frontend โ€” Shared layout and navigation
  - [x] 8.1 Build AppShell, NavigationMenu, and theme system
    - Implement dark sidebar with Lucide icons, grouped sections per design nav structure
    - Implement collapsible sidebar with icon-only mode
    - Implement theme toggle (dark/light) with Tailwind dark mode classes
    - Create design token CSS variables matching design specification
    - Show user profile, logout button, and admin link (admin only)
    - _Requirements: 35.1, 35.2, 35.3, 35.4, 35.5, 35.6, 36.1, 36.2, 36.3_

  - [x] 8.2 Build shared UI components library
    - Create DataTable (sortable headers, sticky headers, pagination, column visibility, density toggle, row actions, export)
    - Create DarkCard, MetricCard (value + label + change indicator)
    - Create ConfirmModal, Toast notifications (3s+ display)
    - Create FilterPanel (date range, multi-select, search)
    - Create LoadingSkeleton, EmptyState, ErrorState components
    - Create Badge component (Winner, Loser, Warning, etc.)
    - _Requirements: 36.4, 36.5, 36.6, 36.7, 38.1, 38.2, 38.3, 38.4, 38.5_

- [x] 9. Frontend โ€” Login and authentication flow
  - [x] 9.1 Build login page with Google and Facebook OAuth buttons
    - Create `/login` route with OAuth provider buttons
    - Handle OAuth callback redirect and session establishment
    - Redirect unauthenticated users to login
    - Show approval-pending page for Pending users
    - Show blocked message for Blocked users
    - Handle OAuth failure gracefully with error display
    - _Requirements: 39.1, 39.3, 39.4, 39.5, 40.2, 40.4_

  - [x] 9.2 Build admin panel page
    - Create `/admin` route with user list table
    - Display user status (Approved, Pending, Blocked)
    - Implement Approve, Block, Revert actions per row
    - Restrict access to admin users only
    - _Requirements: 40.1, 40.2, 40.3, 40.4, 40.5_

- [x] 10. Frontend โ€” Trading Log page
  - [x] 10.1 Build Trading Log page with transaction CRUD
    - Create `/trading` route with DataTable listing all transactions
    - Implement create transaction form (Buy/Sell with all fields)
    - Implement edit and delete with ConfirmModal
    - Display visual badges for Snapshot, Buy, Sell, Dividend, Adjustment
    - Implement filters: date range, symbol, broker, action, tag, strategy
    - Implement CSV export action
    - Implement row actions: View Details, Edit, Delete, Add Note
    - _Requirements: 1.1, 1.2, 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 6.4_

  - [x] 10.2 Build snapshot import interface
    - Create snapshot import form/modal for bulk position entry
    - Display validation errors per row
    - Visually distinguish snapshot rows in the trading log table
    - _Requirements: 2.1, 2.3, 2.4, 2.5_

- [x] 11. Frontend โ€” Money Transfers page
  - [x] 11.1 Build Money Transfers page with FX support
    - Create `/transfers` route with DataTable listing transfers
    - Implement create/edit transfer form with currency selector (THB/USD)
    - Show FX rate input when currency is non-USD
    - Auto-calculate converted USD amount on input
    - Display all FX columns: Original Currency, Original Amount, FX Rate, Converted USD, FX Fee, Note
    - Implement delete with ConfirmModal
    - Implement CSV export with all FX columns
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.7_

- [x] 12. Frontend โ€” Dashboard page
  - [x] 12.1 Build Dashboard page with MVP internal metrics
    - Create `/` (root) route as Dashboard
    - Display MetricCards: Total Portfolio Value, Net Invested, Total Gain/Loss, Overall ROI, Cash Available
    - Display What_Changed section (recent changes since last login)
    - Display Action_Needed section (placeholder for Phase 2)
    - Display Recent Transactions card
    - Apply dark trading dashboard layout
    - _Requirements: 9.1, 9.2, 9.3, 9.5, 9.6_

- [x] 13. Frontend โ€” Settings page
  - [x] 13.1 Build Settings page with user preferences
    - Create `/settings` route with DarkCard sections for each group (Theme, Trading, Broker, AI)
    - Theme toggle (Dark/Light) โ€” must switch between dark and light design tokens and persist to database
    - Default cost basis method selection (FIFO, LIFO, AvgCost, SpecificLot)
    - Default broker and currency settings
    - AI mode toggle (Disabled for MVP)
    - Wire form controls to `GET /api/settings` and `PUT /api/settings` endpoints
    - _Requirements: 36.1, 36.3, 18.1, 18.2_

- [x] 14. Checkpoint โ€” Phase 1 Complete
  - Ensure all Phase 1 tests pass (backend + frontend), ask the user if questions arise.
  - Verify Docker Compose stack runs end-to-end: login โ’ create transaction โ’ view dashboard

---

## Phase 2 โ€” Market Data & Analytics

- [x] 15. Provider adapter layer and market data service
  - [x] 15.1 Implement provider adapter interfaces and resilience layer
    - Create abstract `MarketDataAdapter`, `FXRateAdapter`, `FundamentalsAdapter`, `EmailAdapter` protocol classes
    - Implement circuit breaker with state transitions (Closedโ’Openโ’HalfOpenโ’Closed)
    - Implement rate limiter with Redis-backed request counting
    - Implement retry with exponential backoff
    - Implement fallback chain orchestration
    - Create `ProviderStatus` tracking (success/failure counts, circuit state)
    - _Requirements: 8.7, 8.8, 8.13, 46.1, 46.2, 46.3, 46.4, 46.5_

  - [x] 15.2 Implement Financial Modeling Prep (FMP) market data adapter
    - Implement `MarketDataAdapter` for FMP: get_quote, get_historical, get_company_profile, get_batch_quotes
    - Map FMP response to internal `QuoteData`, `CompanyProfile` contracts
    - Handle FMP rate limits and error responses
    - _Requirements: 8.1, 8.7, 46.1_

  - [x] 15.3 Implement Alpha Vantage market data adapter (fallback)
    - Implement `MarketDataAdapter` for Alpha Vantage as secondary provider
    - Map Alpha Vantage response to internal contracts
    - _Requirements: 8.7, 8.13, 46.1_

  - [x] 15.4 Implement FX rate adapter (UniRateAPI or compatible)
    - Implement `FXRateAdapter` with get_rate and get_latest_rate
    - Cache rates by (currency_pair, date) in Redis with configurable TTL
    - Support manual override when provider unavailable
    - _Requirements: 3.8, 3.9, 8.7, 46.1_

  - [x] 15.5 Implement MarketDataService orchestrator with caching
    - Create unified service with Redis caching layer
    - Implement provider priority order, fallback behavior
    - Store provider_name, source_timestamp, last_fetched, staleness for each cached item
    - Retain last valid cache on refresh failure with stale flag
    - Support manual refresh with rate-limit protection
    - Create `GET /api/providers/status` and `GET /api/providers/compatibility` endpoints
    - _Requirements: 8.2, 8.3, 8.4, 8.9, 8.10, 8.11, 8.12, 8.13, 8.14, 46.6, 46.7, 46.8_

  - [x]* 15.6 Write unit tests for provider adapters and circuit breaker
    - Test FMP and Alpha Vantage response mapping and error handling
    - Test circuit breaker state transitions and failure thresholds
    - Test rate limiter request counting and window reset
    - Test fallback chain: primary fails โ’ fallback โ’ cache โ’ N/A
    - _Requirements: 8.7, 46.3_

- [x] 16. Portfolio Summary with market data
  - [x] 16.1 Implement portfolio summary service and API
    - Create `GET /api/portfolio/summary` โ€” calculate positions with market data enrichment
    - Include: Symbol, Company Name, Qty, Avg Cost, Total Cost, Current Price, Market Value, Unrealized P/L, ROI, Allocation, Sector, Industry, Beta, P/E, Dividend Yield, 52-week range, Sentiment
    - Calculate aggregates: Total Cost, Market Value, Unrealized P/L, Overall ROI, Cash, Net Invested
    - Create `GET /api/portfolio/closed` for zero-quantity positions
    - Create `POST /api/portfolio/refresh` (rate-limited)
    - Create `PUT /api/portfolio/{symbol}/sentiment`
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

  - [x]* 16.2 Write property test for zero-quantity position exclusion
    - **Property 12: Zero-Quantity Position Exclusion**
    - Generate positions including zero-qty; verify active summary excludes them
    - **Validates: Requirements 7.5**

  - [x]* 16.3 Write property test for allocation sum invariant
    - **Property 35: Allocation Sum Invariant**
    - Generate multi-position portfolios; verify allocation percentages sum to 100% (ยฑ0.01%)
    - **Validates: Requirements 7.1, 12.1**

- [x] 17. Realized P/L and Tax Lot Accounting
  - [x] 17.1 Implement tax lot accounting engine
    - Create tax lot creation on buy/snapshot transactions
    - Implement FIFO, LIFO, Average Cost, and Specific Lot depletion methods
    - Calculate realized P/L on sell: (sell_price - cost_basis) ร— qty
    - Classify as Short-term (<365 days) or Long-term (โฅ365 days)
    - Track remaining_quantity and lot status (Open/Closed/Partial)
    - Create `GET /api/realized-pl`, `GET /api/realized-pl/summary`, `GET /api/realized-pl/tax-lots`
    - Create `GET /api/realized-pl/settings`, `PUT /api/realized-pl/settings`
    - Create `GET /api/realized-pl/export`
    - _Requirements: 18.1, 18.2, 18.3, 18.4, 18.5_

  - [x]* 17.2 Write property tests for tax lot accounting
    - **Property 17: Tax Lot FIFO/LIFO Ordering** โ€” Verify FIFO depletes oldest first, LIFO depletes newest, Avg Cost uses weighted average; remaining + sold = purchased
    - **Property 18: Realized P/L Calculation** โ€” Verify realized_pl = (sell_price - cost_basis) ร— qty; correct term classification
    - **Validates: Requirements 18.1, 18.2, 18.3, 18.4**

- [x] 18. Performance History and Returns
  - [x] 18.1 Implement performance snapshot service and returns calculations
    - Create database migration for `performance_snapshots` table
    - Create `POST /api/performance/snapshots`, `GET /api/performance/snapshots`, `PUT`, `DELETE`
    - Calculate Period Return, Cumulative Return, Monthly/Yearly Return, Maximum Drawdown
    - Create `GET /api/performance/returns` with period parameter
    - Create `GET /api/performance/drawdown`
    - Support selectable ranges: 1D, 1W, 1M, 3M, YTD, 1Y, All
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6_

  - [x]* 18.2 Write property tests for performance calculations
    - **Property 13: Period Return Calculation** โ€” Verify period_return = ((later - earlier) / earlier) ร— 100
    - **Property 14: Maximum Drawdown Calculation** โ€” Verify max drawdown bounded [0, 100], equals largest peak-to-trough decline
    - **Validates: Requirements 10.2, 21.1**

- [x] 19. Benchmark Comparison
  - [x] 19.1 Implement benchmark comparison service
    - Allow users to select benchmarks (S&P 500, Nasdaq 100, QQQ, SPY, VT, custom ticker)
    - Fetch benchmark historical data via market data adapter
    - Calculate Alpha, Relative Performance, Tracking Difference, Win/Loss months
    - Create `GET /api/performance/benchmark` and `PUT /api/performance/benchmark/config`
    - _Requirements: 11.1, 11.2, 11.3, 11.4_

  - [x]* 19.2 Write property test for benchmark comparison
    - **Property 15: Benchmark Comparison Correctness**
    - Generate portfolio + benchmark return series; verify alpha = portfolio_return - benchmark_return; verify win_months count
    - **Validates: Requirements 11.2, 11.4**

- [x] 20. Portfolio Attribution
  - [x] 20.1 Implement portfolio attribution service
    - Calculate attribution by Stock, Sector, Broker, Tag, Strategy, Currency/FX, Dividend, Realized P/L, Unrealized P/L
    - Show top contributors and detractors over selected time periods
    - Create `GET /api/portfolio/attribution` endpoint
    - _Requirements: 12.1, 12.2, 12.3_

  - [x]* 20.2 Write property test for attribution sum invariant
    - **Property 16: Attribution Sum Invariant**
    - Generate multi-position portfolios; verify sum of position contributions = total portfolio return (within floating-point tolerance)
    - **Validates: Requirements 12.1, 12.2**

- [x] 21. Alerts and Email Notifications
  - [x] 21.1 Implement alert service and evaluation engine
    - Create database migration for `alerts`, `alert_history` tables
    - Create `POST /api/alerts`, `GET /api/alerts`, `PUT /api/alerts/{id}`, `DELETE /api/alerts/{id}`
    - Implement `POST /api/alerts/{id}/snooze` and `POST /api/alerts/{id}/resolve`
    - Implement alert evaluation for price alerts (Above/Below)
    - Implement smart alerts: concentration, drawdown, overweight, underweight, high beta, stale data
    - Group alerts by urgency (Low, Medium, High, Critical)
    - Create `GET /api/alerts/preferences`, `PUT /api/alerts/preferences`
    - _Requirements: 15.1, 15.2, 15.3, 15.4, 15.5, 15.6, 15.7_

  - [x] 21.2 Implement email notification adapter and service
    - Create `EmailAdapter` protocol with SMTP implementation
    - Support development mode (write to logs instead of sending)
    - Send HTML-formatted email for triggered alerts
    - Log errors and continue in-app flow on email failure
    - Support opt-in/out by alert category
    - _Requirements: 16.1, 16.2, 16.3, 16.4, 16.5, 16.6_

  - [x]* 21.3 Write property test for alert trigger correctness
    - **Property 19: Alert Trigger Correctness**
    - Generate alert configs (Above/Below) + current prices; verify trigger if and only if condition met
    - **Validates: Requirements 15.1, 15.2**

  - [x]* 21.4 Write property test for risk concentration warnings
    - **Property 22: Risk Concentration Warnings**
    - Generate portfolios; verify position warning at >25% and sector warning at >50%
    - **Validates: Requirements 21.2, 21.3**

- [x] 22. Dividend Tracker
  - [x] 22.1 Implement dividend tracker service and API
    - Create database migration for `dividend_records` table
    - Create `POST /api/dividends`, `GET /api/dividends`, `PUT /api/dividends/{id}`, `DELETE /api/dividends/{id}`
    - Calculate Yield on Cost and projected annual dividend income
    - Create `GET /api/dividends/summary` (by stock, broker, month, year)
    - Create `GET /api/dividends/projection` and `GET /api/dividends/export`
    - Include dividends in cash ledger and total return calculations
    - _Requirements: 17.1, 17.2, 17.3, 17.4, 17.5, 17.6, 17.7_

  - [x]* 22.2 Write property test for dividend yield on cost
    - **Property 20: Dividend Yield on Cost**
    - Generate dividend records + cost basis; verify yield_on_cost = (D / C) ร— 100
    - **Validates: Requirements 17.2, 17.3**

- [x] 23. Portfolio Health Score
  - [x] 23.1 Implement portfolio health score calculation
    - Calculate weighted score from 9 components: diversification, concentration, drawdown, benchmark, cash drag, data quality, thesis completeness, journal discipline, risk-adjusted return
    - Create `GET /api/portfolio/health-score` with breakdown and suggested actions
    - Ensure score bounded [0, 100]
    - _Requirements: 22.1, 22.2, 22.3, 22.4_

  - [x]* 23.2 Write property test for health score bounds
    - **Property 23: Health Score Bounds and Composition**
    - Generate component scores [0,100] with weights summing to 1.0; verify weighted sum in [0,100]
    - **Validates: Requirements 22.1, 22.2**

- [x] 24. Watchlist
  - [x] 24.1 Implement watchlist service and API
    - Create database migration for `watchlist_items` table
    - Create `POST /api/watchlist`, `GET /api/watchlist`, `PUT /api/watchlist/{id}`, `DELETE /api/watchlist/{id}`
    - Fetch market data for watchlist symbols
    - Highlight stocks at or near target entry price
    - Create `GET /api/watchlist/near-target`
    - _Requirements: 23.1, 23.2, 23.3, 23.4, 23.5_

  - [x]* 24.2 Write property test for watchlist at-target logic
    - **Property 24: Watchlist At-Target Logic**
    - Generate watchlist items + current prices; verify highlight if and only if current_price โค target_entry_price
    - **Validates: Requirements 23.3**

- [x] 25. Trending Stocks
  - [x] 25.1 Implement trending stocks service
    - Create `GET /api/trending` โ€” Trending, Top Gainers, Top Losers, Most Active
    - Cache trending data for 15 minutes minimum
    - Show data source and last refreshed timestamp
    - Show unavailable state gracefully when no provider quota available
    - _Requirements: 24.1, 24.2, 24.3, 24.4, 24.5, 24.6, 24.7_

- [x] 26. Tags system
  - [x] 26.1 Implement tags service and API
    - Create `POST /api/tags`, `GET /api/tags`, `PUT /api/tags/{id}`, `DELETE /api/tags/{id}`
    - Assign multiple tags to portfolio stocks, watchlist items, transactions, ideas
    - Calculate performance by tag (cost, market value, unrealized P/L, realized P/L, ROI)
    - Create `GET /api/tags/performance` and `GET /api/tags/{id}/assignments`
    - Support tag deletion with reassignment option
    - _Requirements: 25.1, 25.2, 25.3, 25.4_

  - [x]* 26.2 Write property test for per-tag performance aggregation
    - **Property 25: Per-Tag Performance Aggregation**
    - Generate tagged stocks; verify total_cost = ฮฃ(position costs), market_value = ฮฃ(position values), roi = (unrealized_pl / total_cost) ร— 100
    - **Validates: Requirements 25.3**

- [x] 27. Reports module
  - [x] 27.1 Implement reports service and export
    - Create `GET /api/reports/portfolio-summary`, `/performance`, `/realized-pl`, `/dividends`, `/cash-ledger`, `/tax-lots`, `/benchmark`
    - Create `GET /api/reports/export/{type}` for PDF/CSV/Markdown export
    - Include date range filters and generated timestamp
    - _Requirements: 42.1, 42.2, 42.3_

- [x] 28. MVP degradation mode
  - [x] 28.1 Implement free-tier degradation and graceful fallback UI indicators
    - Prioritize internal accounting when external providers unavailable
    - Show cached or manually entered data when providers fail
    - Display degraded-state messages (Retry Later, Use Cached, Add Manual Price, Configure Provider)
    - Never block page load due to provider failure
    - Record data quality impact from free-tier limitations
    - _Requirements: 47.1, 47.2, 47.3, 47.4, 47.5, 47.6, 47.7, 47.8_

- [x] 29. Checkpoint โ€” Phase 2 Backend Complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 30. Frontend โ€” Portfolio Summary page
  - [x] 30.1 Build Portfolio Summary page with market data
    - Create `/portfolio` route with full position table
    - Display all columns: Symbol, Name, Qty, Avg Cost, Total Cost, Price, Market Value, P/L, ROI, Allocation, Sector, Beta, P/E, Yield, 52-week range, Sentiment
    - Show aggregate row with totals
    - Implement position badges (Winner, Loser, Overweight, High Beta, Data Warning)
    - Show DataQualityIndicator with freshness labels
    - Implement row actions: Add Note, Set Alert, Create Thesis, Simulate
    - Show closed positions toggle
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 8.5, 8.6_

- [x] 31. Frontend โ€” Performance History page
  - [x] 31.1 Build Performance History page with charts
    - Create `/performance` route
    - Display performance chart (Recharts line chart) with selectable ranges (1D, 1W, 1M, 3M, YTD, 1Y, All)
    - Show benchmark overlay on same chart
    - Display metrics: Period Return, Cumulative Return, Max Drawdown, Alpha
    - Show monthly/yearly return tables
    - Implement snapshot CRUD (create, edit, delete with recalculation)
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 11.3, 11.4_

- [x] 32. Frontend โ€” Alerts page
  - [x] 32.1 Build Alerts page and notification center
    - Create `/alerts` route with tabs: Active, Triggered, Snoozed, Resolved
    - Implement create alert form (Price Above/Below, Smart alerts)
    - Implement snooze, resolve, delete actions
    - Show urgency grouping and data confidence indicators
    - Display email notification preferences settings
    - _Requirements: 15.3, 15.4, 15.5, 16.4_

- [x] 33. Frontend โ€” Dividend Tracker page
  - [x] 33.1 Build Dividend Tracker page
    - Create `/dividends` route with dividend records table
    - Implement create/edit/delete dividend records
    - Display summary by stock, broker, month, year
    - Show Yield on Cost and projected annual income
    - Show data-source labels for API vs manual entries
    - Implement export
    - _Requirements: 17.1, 17.2, 17.3, 17.4, 17.6, 17.7_

- [x] 34. Frontend โ€” Realized P/L page
  - [x] 34.1 Build Realized P/L page
    - Create `/realized-pl` route with realized P/L records table
    - Display: Date, Symbol, Qty Sold, Sell Price, Cost Basis, Realized P/L, Holding Duration, Method, Term
    - Show summary totals (monthly/yearly/all-time)
    - Show tax lot details by symbol
    - Implement cost basis method setting
    - Implement export
    - _Requirements: 18.1, 18.3, 18.4, 18.5_

- [x] 35. Frontend โ€” Watchlist page
  - [x] 35.1 Build Watchlist page
    - Create `/watchlist` route with watchlist table and market data
    - Highlight stocks at or near target price
    - Implement add/edit/remove watchlist items
    - Show opportunities near buy zone summary
    - Implement row actions: Set Alert, Create Thesis, Add to Portfolio, Simulate
    - _Requirements: 23.1, 23.2, 23.3, 23.4, 23.5_

- [x] 36. Frontend โ€” Reports page
  - [x] 36.1 Build Reports page with export functionality
    - Create `/reports` route with report type selection
    - Generate and display Portfolio Summary, Performance, Realized P/L, Dividend, Cash Ledger, Tax Lots, Benchmark reports
    - Implement PDF/CSV/Markdown export per report type
    - Include date range filters and generated timestamp
    - _Requirements: 42.1, 42.2, 42.3_

- [x] 37. Frontend โ€” Dashboard enhancements for Phase 2
  - [x] 37.1 Enhance Dashboard with market data, alerts, and benchmark comparison
    - Add Daily Change metric card
    - Add Benchmark Comparison indicator (outperforming/underperforming)
    - Add Top Contributors / Top Detractors cards
    - Add Risk Warnings card
    - Add Watchlist Near Target card
    - Add Portfolio Health Score mini-display
    - _Requirements: 9.1, 9.4, 11.4, 12.4, 22.1_

- [x] 38. Checkpoint โ€” Phase 2 Complete
  - Ensure all Phase 2 tests pass (backend + frontend), ask the user if questions arise.
  - Verify portfolio summary shows market data, performance charts render, alerts trigger correctly

---

## Phase 3 โ€” Premium Intelligence

- [x] 39. Trade Journal and Behavioral Analytics
  - [x] 39.1 Implement trade journal service
    - Create `PUT /api/transactions/{id}/notes` (up to 2000 chars)
    - Create `PUT /api/transactions/{id}/tags` for tag assignment
    - Support predefined and custom tags, strategy, thesis, catalyst, risk level, confidence
    - Support filtering by tag, strategy, sentiment, outcome in trading log and journal views
    - _Requirements: 13.1, 13.2, 13.3, 13.4_

  - [x] 39.2 Implement behavioral analytics service
    - Calculate win rate, avg winner, avg loser, payoff ratio, avg holding period
    - Identify patterns: selling winners early, holding losers too long, overtrading, concentration in losing themes
    - Create `GET /api/behavioral/stats`, `/patterns`, `/by-tag`, `/by-sector`, `/by-strategy`
    - Use realized trades, journal tags, and holding periods
    - _Requirements: 14.1, 14.2, 14.3, 14.4_

  - [x]* 39.3 Write property test for behavioral analytics formulas
    - **Property 30: Behavioral Analytics Formulas**
    - Generate realized trades; verify win_rate = (positive trades / total) ร— 100, payoff_ratio = avg_winner / |avg_loser|, avg_holding = mean(holding_days)
    - **Validates: Requirements 14.1**

- [x] 40. Rebalancing and Position Sizing
  - [x] 40.1 Implement rebalancing insights service
    - Create database migration for `target_allocations` table
    - Allow target allocation by stock, sector, tag, asset class
    - Calculate current vs target allocation with deviation
    - Recommend buy/sell amounts to rebalance
    - Create `GET /api/rebalancing/insights`, `/targets`, `PUT /api/rebalancing/targets`
    - _Requirements: 19.1, 19.2, 19.3, 19.4, 19.5_

  - [x] 40.2 Implement position sizing recommendation service
    - Calculate suggested shares = (portfolio_value ร— max_risk) / (entry - stop_loss)
    - Display recommended shares, capital required, portfolio allocation, expected downside
    - Warn if proposed position causes concentration violations
    - Create `POST /api/rebalancing/position-size`
    - _Requirements: 20.1, 20.2, 20.3_

  - [x]* 40.3 Write property tests for rebalancing and position sizing
    - **Property 28: Rebalancing Deviation Calculation** โ€” Verify deviation = actual% - target%; recommended amounts bring positions to target
    - **Property 29: Position Sizing Formula** โ€” Verify suggested_shares = (Vร—R)/(E-S), capital = sharesร—E, downside = sharesร—(E-S)
    - **Validates: Requirements 19.1, 19.3, 19.4, 20.1, 20.2**

- [x] 41. Risk Metrics Dashboard
  - [x] 41.1 Implement risk metrics service
    - Calculate Portfolio Beta (weighted average), Sector Concentration, Position Concentration, Max Drawdown, Volatility, Cash Ratio
    - Generate risk warnings for position >25%, sector >50%
    - Create `GET /api/risk/metrics` and `GET /api/risk/warnings`
    - Include Portfolio Health Score on risk page
    - _Requirements: 21.1, 21.2, 21.3, 21.4, 21.5_

  - [x]* 41.2 Write property test for portfolio beta weighted average
    - **Property 21: Portfolio Beta Weighted Average**
    - Generate positions with known betas; verify portfolio_beta = ฮฃ(weight_i ร— beta_i)
    - **Validates: Requirements 21.1**

- [x] 42. Investment Thesis Board
  - [x] 42.1 Implement investment ideas service and API
    - Create database migration for `investment_ideas`, `thesis_break_conditions` tables
    - Create full CRUD: `POST /api/ideas`, `GET /api/ideas`, `PUT /api/ideas/{id}`, `DELETE /api/ideas/{id}`
    - Support statuses: Researching, Watching, Near Entry, Bought, Passed, Closed
    - Link idea to transaction on Bought status
    - Create `GET /api/ideas/board` (Kanban) and `GET /api/ideas/calendar`
    - _Requirements: 26.1, 26.2, 26.3, 26.4, 26.5_

  - [x] 42.2 Implement thesis break condition monitoring
    - Create `POST /api/ideas/{id}/break-conditions`, `GET /api/ideas/{id}/break-conditions`, `DELETE`
    - Support condition types: price_below, drawdown_pct, time_elapsed, custom
    - Track review dates and flag overdue thesis reviews
    - Trigger alerts when conditions require thesis review
    - _Requirements: 27.1, 27.2, 27.3, 27.4_

  - [x]* 42.3 Write property test for thesis break condition trigger
    - **Property 33: Thesis Break Condition Trigger**
    - Generate price_below conditions + current prices; verify triggered if and only if P < T
    - Generate drawdown_pct conditions; verify triggered if and only if drawdown > threshold
    - **Validates: Requirements 27.1, 27.3**

- [x] 43. Stock Screener
  - [x] 43.1 Implement stock screener service and API
    - Create database migration for `screener_presets` table
    - Support filters: P/E range, Dividend Yield, Market Cap, Sector, Industry, Beta, Price to Book, 52-week range, Volume
    - Provide quick strategy chips: High Dividend, Low P/E, Mega Cap, Tech Growth, Value Banks, Near 52-Week Low, High Quality
    - Create `POST /api/screener/search`, `GET /api/screener/presets`, `POST /api/screener/presets`, `PUT`, `DELETE`
    - Create `GET /api/screener/strategies`
    - Support running against local normalized stock universe
    - Label results as delayed/cached/provider-limited
    - _Requirements: 29.1, 29.2, 29.3, 29.4, 29.5, 29.6, 29.7, 29.8, 29.9, 29.10, 29.11, 29.12_

  - [x]* 43.2 Write property test for screener filter correctness
    - **Property 26: Screener Filter Correctness**
    - Generate stock universe + filter criteria; verify all results satisfy ALL filters; no valid stock excluded
    - **Validates: Requirements 29.1**

- [x] 44. Scenario Simulator
  - [x] 44.1 Implement scenario simulator service
    - Model: price changes, buy/sell, cash deposit, FX rate change, dividend change, rebalancing
    - Calculate impact on: Total Value, P/L, Allocation, Beta, Cash, Concentration, Health Score
    - Create `POST /api/simulator/run` and `GET /api/simulator/compare`
    - Ensure real portfolio data is NEVER mutated by simulation
    - _Requirements: 30.1, 30.2, 30.3, 30.4_

  - [x]* 44.2 Write property test for scenario simulator non-mutation
    - **Property 27: Scenario Simulator Non-Mutation**
    - Run simulations; verify real portfolio data (transactions, positions, cash) unchanged after simulation
    - **Validates: Requirements 30.4**

- [x] 45. AI Insights (Rule-Based MVP + LLM-Ready)
  - [x] 45.1 Implement AI insight service with rule-based generation
    - Create `AIInsightAdapter` protocol with RuleBased, LocalLLM, HostedLLM implementations
    - Implement rule-based weekly memo generation (no paid AI required for MVP)
    - Implement rule-based trade review generation
    - Create `GET /api/ai/weekly-memo`, `/history`, `POST /api/ai/weekly-memo/generate`
    - Create `GET /api/ai/trade-review/{tx_id}`, `POST /api/ai/trade-review/generate`
    - Create `GET /api/ai/settings`, `PUT /api/ai/settings`
    - Store generated memos; avoid unnecessary regeneration
    - Disclose generation mode (Rules/LocalLLM/HostedLLM) on each output
    - _Requirements: 31.1, 31.2, 31.3, 31.4, 31.5, 31.6, 31.7, 31.8, 32.1, 32.2, 32.3, 32.4, 32.5, 32.6, 45.1, 45.2, 45.3, 45.4, 45.5_

  - [x] 45.2 Implement one-click portfolio review
    - Create `POST /api/dashboard/review` aggregating: Performance, Benchmark, Attribution, Risk, Cash, Watchlist, Thesis, Alerts, Next Actions
    - Create `GET /api/dashboard/review/export` for PDF/Markdown export
    - _Requirements: 33.1, 33.2, 33.3_

- [x] 46. Import/Export
  - [x] 46.1 Implement import/export service
    - Create `POST /api/import-export/import` for CSV (transactions, transfers, dividends, watchlist, ideas, snapshots)
    - Create `POST /api/import-export/import/preview` for validation preview before commit
    - Create `GET /api/import-export/export/backup` for full account JSON backup
    - Create `POST /api/import-export/import/restore` for JSON restore
    - Atomic import: all-or-nothing per file
    - _Requirements: 34.1, 34.2, 34.3, 34.4_

  - [x]* 46.2 Write property tests for import/export
    - **Property 31: Import/Export Round-Trip** โ€” Export JSON, reimport to fresh account; verify equivalent dataset
    - **Property 34: CSV Export Completeness** โ€” Verify exported row count = matching transactions; all required fields present
    - **Validates: Requirements 34.1, 34.4, 5.5**

- [x] 47. Checkpoint โ€” Phase 3 Backend Complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 48. Frontend โ€” Trade Journal page
  - [x] 48.1 Build Trade Journal page
    - Create `/journal` route with notes/tags/strategy view
    - Display transaction notes, tags, strategies with filtering
    - Link to behavioral analytics insights
    - Show trade review summaries where available
    - _Requirements: 13.1, 13.4, 13.5_

- [x] 49. Frontend โ€” Investment Ideas page
  - [x] 49.1 Build Investment Ideas page with Board/List/Calendar views
    - Create `/ideas` route with three view modes
    - Board view: Kanban by status (Researching โ’ Watching โ’ Near Entry โ’ Bought โ’ Passed โ’ Closed)
    - List view: Sortable table with all idea fields
    - Calendar view: By review/catalyst dates
    - Implement idea CRUD with full thesis fields
    - Show thesis break conditions and overdue review indicators
    - Link to transaction on Bought status
    - _Requirements: 26.1, 26.2, 26.3, 26.4, 26.5, 27.1, 27.2_

- [x] 50. Frontend โ€” Stock Screener page
  - [x] 50.1 Build Stock Screener page with professional layout
    - Create `/screener` route
    - Compact filter panel with quick strategy chips
    - Result summary cards (Count, Median P/E, Top Sector, Warnings)
    - Professional data table with sticky header, sortable columns, badges, pagination
    - Row actions: Add to Watchlist, Set Alert, Create Thesis, Simulate
    - Label data as delayed/cached/provider-limited
    - Implement preset save/load/edit/delete
    - _Requirements: 29.1, 29.2, 29.3, 29.4, 29.5, 29.6, 29.7, 29.8, 29.10_

- [x] 51. Frontend โ€” Risk & Rebalancing page
  - [x] 51.1 Build Risk & Rebalancing page
    - Create `/risk` route
    - Display risk metrics: Portfolio Beta, Sector/Position Concentration, Max Drawdown, Volatility, Cash Ratio
    - Show risk warnings with thresholds
    - Display current vs target allocation with deviation
    - Implement target allocation configuration
    - Implement position sizing calculator form
    - Display Portfolio Health Score with breakdown
    - _Requirements: 19.1, 19.2, 19.3, 20.1, 20.2, 21.1, 21.2, 21.3, 22.1_

- [x] 52. Frontend โ€” Scenario Simulator
  - [x] 52.1 Build Scenario Simulator interface
    - Add simulator accessible from Risk page or as modal
    - Support scenario inputs: price change, buy/sell, cash, FX, rebalance
    - Display Current vs Simulated portfolio comparison
    - Show impact on Value, P/L, Allocation, Beta, Cash, Concentration, Health Score
    - Clearly indicate simulated data does not affect real portfolio
    - _Requirements: 30.1, 30.2, 30.3, 30.4_

- [x] 53. Frontend โ€” AI Insights and Portfolio Review
  - [x] 53.1 Build AI Insight components and weekly memo display
    - Add AI Insight Card to Dashboard (plain-language portfolio summary)
    - Create weekly memo view page with historical memos list
    - Create trade review display on sold position detail
    - Show generation mode disclosure (Rules/Local LLM/Hosted LLM)
    - Show stale data warnings within AI content
    - Implement One-Click Portfolio Review button on Dashboard with export
    - _Requirements: 9.5, 31.1, 31.3, 31.4, 32.1, 32.5, 32.6, 33.1, 33.2, 33.3_

- [x] 54. Frontend โ€” Sector Heatmap
  - [x] 54.1 Build Sector Heatmap component
    - Create `GET /api/portfolio/sector-heatmap` backend endpoint
    - Implement treemap visualization (sized by allocation, colored by performance)
    - Support drill-down into sector positions
    - Optimize colors for dark mode
    - Integrate on Portfolio Summary and Dashboard
    - _Requirements: 28.1, 28.2, 28.3, 28.4_

- [x] 55. Responsive mobile experience
  - [x] 55.1 Implement responsive layouts for tablet and mobile
    - Collapse sidebar into bottom nav or drawer on mobile
    - Mobile dashboard: prioritize Value, Daily Change, Alerts, Watchlist, Actions
    - Transform wide tables to card rows or horizontally scrollable on small screens
    - Ensure critical actions reachable within 1-2 taps
    - _Requirements: 37.1, 37.2, 37.3, 37.4, 37.5_

- [x] 56. Frontend โ€” Import/Export interface
  - [x] 56.1 Build Import/Export page
    - Implement CSV import with file upload, validation preview, and commit
    - Implement full account JSON backup download
    - Implement JSON restore with confirmation
    - Show row-level validation errors on import preview
    - _Requirements: 34.1, 34.2, 34.3, 34.4_

- [x] 57. Final checkpoint โ€” Ensure all tests pass
  - Ensure all tests pass (all 36 property tests + unit tests + integration tests), ask the user if questions arise.
  - Verify full Docker Compose deployment works end-to-end
  - Confirm all three phases are functional and integrated

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation between phases
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- Phase 1 can operate entirely without external API providers
- Phase 2 requires at least one configured market data provider (FMP recommended for free tier)
- Phase 3 AI features work with rule-based mode by default (no paid AI required)
- All providers are swappable via environment variables without code changes

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2"] },
    { "id": 1, "tasks": ["1.3", "1.4", "1.5"] },
    { "id": 2, "tasks": ["2.1", "2.4", "8.1"] },
    { "id": 3, "tasks": ["2.2", "2.3", "2.5", "8.2"] },
    { "id": 4, "tasks": ["3.1", "9.1", "9.2"] },
    { "id": 5, "tasks": ["3.2", "3.3", "3.4", "3.5"] },
    { "id": 6, "tasks": ["3.6", "3.7", "4.1", "4.3", "5.1"] },
    { "id": 7, "tasks": ["3.8", "3.9", "4.2", "5.2", "7.1"] },
    { "id": 8, "tasks": ["7.2", "10.1", "10.2", "11.1", "12.1", "13.1"] },
    { "id": 9, "tasks": ["15.1", "15.4"] },
    { "id": 10, "tasks": ["15.2", "15.3", "15.5"] },
    { "id": 11, "tasks": ["15.6", "16.1", "17.1", "18.1"] },
    { "id": 12, "tasks": ["16.2", "16.3", "17.2", "18.2", "19.1"] },
    { "id": 13, "tasks": ["19.2", "20.1", "21.1", "21.2", "22.1"] },
    { "id": 14, "tasks": ["20.2", "21.3", "21.4", "22.2", "23.1", "24.1"] },
    { "id": 15, "tasks": ["23.2", "24.2", "25.1", "26.1", "27.1"] },
    { "id": 16, "tasks": ["26.2", "28.1", "30.1", "31.1"] },
    { "id": 17, "tasks": ["32.1", "33.1", "34.1", "35.1", "36.1", "37.1"] },
    { "id": 18, "tasks": ["39.1", "39.2", "40.1", "40.2", "41.1"] },
    { "id": 19, "tasks": ["39.3", "40.3", "41.2", "42.1"] },
    { "id": 20, "tasks": ["42.2", "42.3", "43.1", "44.1"] },
    { "id": 21, "tasks": ["43.2", "44.2", "45.1", "45.2"] },
    { "id": 22, "tasks": ["46.1"] },
    { "id": 23, "tasks": ["46.2", "48.1", "49.1", "50.1"] },
    { "id": 24, "tasks": ["51.1", "52.1", "53.1", "54.1"] },
    { "id": 25, "tasks": ["55.1", "56.1"] }
  ]
}
```

- [x] 50. UI Enhancement — Table Alignment and Pagination for Trading Log
  - [x] 50.1 Fix table column alignment (header vs body) in Trading Log
    - Changed `table-layout` from `auto` to `fixed` for `.data-table`
    - Added `<colgroup>` with explicit column widths for the Trading Log table (`.trading-table`)
    - Added `.number-col` class for right-aligned header text on numeric columns (Qty, Price, Gross Value, Fee, VAT, Net Capital Flow)
    - Ensured `overflow: hidden; text-overflow: ellipsis` on th/td to prevent text overflow
    - _Requirements: 5.3, 36.1, 36.2_

  - [x] 50.2 Add Pagination component and integrate with Trading Log
    - Created reusable `Pagination.tsx` component with Previous/Next buttons, page number buttons, ellipsis for large page counts, "Showing X to Y of Z entries" info text, and per-page selector
    - Added pagination state (`currentPage`, `itemsPerPage`) to `TransactionTable`
    - Integrated `useMemo` for slicing sorted items into paginated view
    - Added CSS styles for `.pagination-container`, `.pagination-controls`, and `.pagination-per-page`
    - Per-page options: 10, 20, 50, 100
    - _Requirements: 5.1, 5.3, 36.1_

- [x] 51. Stock Screener — Filter to tradeable stocks only
  - [x] 51.1 Add exchange filter to yfinance EquityQuery
    - Added `is_in` condition for exchange field: NMS, NYQ, NGM, NCM, ASE, PCX (major US exchanges)
    - Replaces previous `eq region us` fallback condition
    - Ensures only NYSE, NASDAQ, AMEX listed stocks are queried
    - _Requirements: 29.2, 29.3_

  - [x] 51.2 Add post-filter in _parse_screen_results
    - Filters out non-EQUITY quoteType (warrants, preferred shares, units)
    - Filters out OTC/pink sheet exchange codes
    - Filters out preferred share symbols (e.g., JPM-PC, BAC-PB)
    - Allows legitimate multi-class symbols (BRK-A, BRK-B)
    - _Requirements: 29.2, 29.3_

- [x] 52. UI Enhancement — Apply table alignment + pagination to ALL data tables
  - [x] 52.1 Apply table-layout: fixed and number-col alignment to all tables
    - Applied `table-layout: fixed` to `.data-table` and `.portfolio-table`
    - Added `overflow: hidden; text-overflow: ellipsis` to all th/td
    - Added `number-col` class to numeric `<th>` headers across all pages
    - Pages updated: TradingPage, TransfersPage, RealizedPLPage, ScreenerPage, WatchlistPage, TrendingPage, DividendsPage, PerformancePage, HeatmapPage, AlertsPage
    - _Requirements: 5.3, 5.4, 36.1, 36.2_

  - [x] 52.2 Add pagination to all data tables
    - Created reusable `usePagination` hook for consistent pagination state management
    - Applied `usePagination` + `<Pagination>` component to all table components:
      - TransfersPage (TransferTable)
      - RealizedPLPage (RealizedPLTable)
      - ScreenerPage (results table)
      - WatchlistPage (WatchlistTable)
      - TrendingPage (trending stocks table)
      - DividendsPage (DividendRecordsTable)
      - PerformancePage (SnapshotTable)
      - HeatmapPage (SectorDetailsTable)
      - AlertsPage (AlertsTable)
    - All tables now show "Showing X to Y of Z entries" + page navigation + per-page selector
    - _Requirements: 5.3, 36.1_

  - [x] 52.3 Fix Stock Screener exchange filter error
    - Fixed "Invalid Operator Value" error caused by unsupported `is_in` operator
    - Changed to `or` of individual `eq` conditions per exchange code
    - _Requirements: 29.2, 29.3_

- [x] 53. Trading Log — Export Excel and Import Excel with duplicate validation
  - [x] 53.1 Backend: Add Excel export endpoint
    - Install `openpyxl` dependency for Excel generation (already present)
    - Created `GET /api/transactions/export-excel` endpoint
    - Generates `.xlsx` with columns: Date, Symbol, Action, Qty, Price per Share, Fee, VAT, Broker, Note
    - Applies current user's filters (date range, symbol, broker, action) to export
    - Returns file as `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`
    - _Requirements: 5.7_

  - [x] 53.2 Backend: Add Excel import preview endpoint
    - Created `POST /api/transactions/import-excel/preview` endpoint (multipart/form-data)
    - Parses uploaded `.xlsx` file using `openpyxl`
    - Validates each row: required fields, data types, date format, positive numbers, valid Action values
    - Detects duplicates by matching (date + stock_symbol + action + quantity + price_per_share)
    - Returns: `{ valid_rows, duplicate_rows, error_rows, preview_data, total_rows }`
    - _Requirements: 5.8, 5.9, 5.10, 5.11, 5.12_

  - [x] 53.3 Backend: Add Excel import commit endpoint
    - Created `POST /api/transactions/import-excel` endpoint (multipart/form-data)
    - Re-validates and re-checks duplicates at commit time
    - Atomic: rejects entire import if any row fails
    - Returns: `{ imported_count, message }`
    - _Requirements: 5.8, 5.9, 5.10, 5.11, 5.13_

  - [x] 53.4 Frontend: Add Export Excel button to Trading Log
    - Added "📥 Export Excel" button next to action buttons
    - Calls `GET /api/transactions/export-excel` with current filters
    - Triggers browser file download
    - _Requirements: 5.7_

  - [x] 53.5 Frontend: Add Import Excel modal to Trading Log
    - Added "📤 Import Excel" button
    - Created `ImportExcelModal` component with:
      - File input (.xlsx only)
      - Preview & Validate button → shows validation results
      - Summary badges (Total, Valid, Duplicates, Errors)
      - Error list with row numbers in red
      - Duplicate warnings in amber
      - Preview table (first 10 rows)
      - Import button (disabled if errors/duplicates)
      - Success → close modal + refresh table
    - _Requirements: 5.8, 5.9, 5.10, 5.11, 5.12, 5.13_


---

## Advanced Stock Screener — Multi-Provider Implementation

- [x] 54. Backend: Multi-Provider Screener Orchestrator
  - [x] 54.1 Create FMP adapter for stock screening
    - Implemented `FMPScreenerAdapter` class in `backend/app/services/providers/fmp_adapter.py`
    - Uses `/stock-screener` endpoint with filters: sector, market_cap, pe, dividend_yield, beta, country
    - Uses `/profile/{symbol}` for enriched company data
    - Handles API key from `FMP_API_KEY` env var
    - Caches responses in Redis (1hr TTL)
    - _Requirements: 48.1_

  - [x] 54.2 Create EODHD adapter for market signals
    - Implemented `EODHDSignalAdapter` class in `backend/app/services/providers/eodhd_adapter.py`
    - Uses `/screener` endpoint with signals parameter for 50d/200d new high/low, wall street signals
    - Caches signals in Redis (6hr TTL)
    - _Requirements: 48.2_

  - [ ] 54.3 Create Alpha Vantage adapter for financial ratios
    - Implement `AlphaVantageOverviewAdapter` class
    - Use `OVERVIEW` function for single-stock financial ratios cross-check
    - _Requirements: 48.3_

  - [ ] 54.4 Create Twelve Data adapter for real-time price
    - Implement `TwelveDataPriceAdapter` class
    - Use `/price` endpoint for real-time price verification
    - _Requirements: 48.4_

  - [x] 54.5 Create ScreenerOrchestrator service
    - Implemented provider chain: FMP → EODHD signals → yfinance fallback
    - Quota tracking per provider
    - Created `POST /api/screener/advanced` endpoint
    - Created `GET /api/screener/provider-status` endpoint
    - _Requirements: 48.1, 48.5, 48.6, 48.7, 48.8_

  - [x] 54.6 Implement system preset definitions
    - Created `GET /api/screener/presets/system` with 8 presets
    - Presets: GARP, Deep Value, Turnaround, Cash Cow, Wall Street Consensus, High Dividend, Low P/E Value, Mega Cap Growth
    - _Requirements: 48.9, 48.10_

  - [x] 54.7 Create available filters metadata endpoint
    - Created `GET /api/screener/filters/available` returning all filter metrics with min/max/step/type
    - _Requirements: 48.15_

- [x] 55. Frontend: Advanced Screener UI
  - [x] 55.1 Build PresetChipsBar component
    - Displays system presets as clickable chips/pills (8 strategies)
    - User presets shown with dashed border
    - Active preset highlighted in blue
    - On click: populates all filter fields with preset values
    - _Requirements: 48.10, 48.11_

  - [x] 55.2 Build DynamicFilterPanel component
    - [+ Add Filter] button opens dropdown of available metrics
    - Dropdown grouped by category (Valuation, Income, Size, Risk, etc.)
    - Each added filter renders as a FilterRow
    - Filters can be removed individually with ✕ button
    - _Requirements: 48.12, 48.13, 48.14_

  - [x] 55.3 Build FilterRow with RangeSlider component
    - Range slider for numeric filters (synced with text input)
    - Text number input for precise values
    - Select dropdown for category filters (Sector)
    - Bidirectional sync between slider and text
    - _Requirements: 48.13_

  - [x] 55.4 Build ProviderStatusBar component
    - Shows provider badges: FMP, EODHD, Alpha Vantage, Twelve Data, yfinance
    - Color coded: green=success, amber=empty, red=error, gray=idle
    - Shows checkmark for providers that were actually used
    - _Requirements: 48.8_

  - [x] 55.5 Integrate advanced screener results table
    - Sortable paginated table with all columns
    - Symbol links to stockanalysis.com
    - Data Source column showing provider badge
    - _Requirements: 48.16, 48.17_

  - [x] 55.6 Build SavePresetModal
    - Simple modal to name and save current filter configuration
    - Saves to existing `/api/screener/presets` endpoint
    - _Requirements: 48.11_
