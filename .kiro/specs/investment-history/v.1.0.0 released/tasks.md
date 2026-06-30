# Implementation Plan: Investment History

## Overview

This implementation plan builds a full-stack Thai stock investment tracker using FastAPI (Python) backend with PostgreSQL, Redis, and yfinance integration, plus a React + TypeScript frontend. Tasks are ordered to establish infrastructure first, then core domain logic, then advanced features, and finally integration/wiring.

## Tasks

- [x] 1. Set up project structure and infrastructure
  - [x] 1.1 Initialize backend project with FastAPI, SQLAlchemy, Pydantic, and Redis
    - Create `backend/` directory with `main.py`, `requirements.txt`, `alembic.ini`
    - Install dependencies: fastapi, uvicorn, sqlalchemy, asyncpg, pydantic, redis, authlib, yfinance
    - Configure database connection (PostgreSQL), Redis connection, CORS middleware
    - Set up Alembic for database migrations
    - _Requirements: 8.1, 8.2, 12.1_

  - [x] 1.2 Create database models and initial migration
    - Define all SQLAlchemy ORM models: User, Transaction, TransactionNote, Tag, TransactionTag, StockTagAssignment, Transfer, PerformanceSnapshot, PriceAlert, DividendRecord, RealizedPL, WatchlistItem, InvestmentIdea, StockSentiment, TargetAllocation, ScreenerPreset, Session
    - Create Alembic migration for initial schema
    - _Requirements: 8.1, 8.2, 8.7, 8.8, 10.12, 10.13, 14.6, 19.6, 21.7, 22.6, 22.7, 24.7, 26.8_

  - [x] 1.3 Create Pydantic request/response models and shared types
    - Define all enums: ActionType, TransferType, AlertType, RiskLevel, IdeaStatus, UserStatus, SentimentType
    - Define request models: TransactionCreate, TransactionUpdate, TransferCreate, TransferUpdate, SnapshotCreate, AlertCreate, DividendCreate, IdeaCreate, IdeaUpdate, ScreenerFilterCreate
    - Define response models: TransactionResponse, TransferResponse, PortfolioPositionResponse, DashboardResponse, PerformanceSnapshotResponse, etc.
    - Include all validators (date not future, symbol uppercase, quantity > 0, etc.)
    - _Requirements: 1.1, 1.2, 1.4, 1.5, 1.7, 1.8, 3.1, 3.4, 3.5, 3.6, 3.7_

  - [x] 1.4 Initialize frontend project with React, TypeScript, and React Router
    - Create `frontend/` directory with Vite + React + TypeScript scaffold
    - Install dependencies: react-router-dom, axios, recharts (for charts), react-hot-toast
    - Set up routing with all pages: Login, Dashboard, Trading, Transfers, Portfolio, Performance, Journal, Watchlist, Ideas, Admin
    - Create base layout with NavigationMenu component
    - _Requirements: 11.1, 11.2, 11.3, 11.4_

  - [x] 1.5 Create shared frontend types and API client
    - Define TypeScript interfaces matching backend response models
    - Create axios-based API client with interceptors for auth and error handling
    - Create shared utility functions for formatting THB currency, percentages, dates
    - _Requirements: 11.1, 25.10_

- [x] 2. Implement authentication and user management
  - [x] 2.1 Implement OAuth authentication backend (Google & Facebook)
    - Create `/api/auth/login/google`, `/api/auth/login/facebook` routes for initiating OAuth
    - Create `/api/auth/callback/google`, `/api/auth/callback/facebook` for handling callbacks
    - Create `/api/auth/logout` to terminate session
    - Create `/api/auth/me` to get current user info
    - Implement session management with secure HTTP-only cookies
    - Store user: display_name, email, profile_picture_url, oauth_provider, oauth_provider_id
    - First registered user becomes Admin automatically
    - New users get "Pending" status by default
    - _Requirements: 25.1, 25.2, 25.3, 25.4, 25.5, 25.6, 25.7, 25.8, 25.9, 25.10, 26.1, 26.2_

  - [x] 2.2 Implement auth middleware and per-user data isolation
    - Create dependency injection for extracting user_id from session
    - Create middleware that blocks unauthenticated requests (redirect to login)
    - Block "Pending" users with PENDING_APPROVAL error
    - Block "Blocked" users with ACCOUNT_BLOCKED error
    - Ensure all data queries filter by user_id
    - _Requirements: 25.5, 25.9, 25.10, 26.5, 26.6, 27.1, 27.2, 27.3, 27.4, 27.5_

  - [x] 2.3 Implement admin user management endpoints
    - Create `/api/admin/users` GET to list all users (admin only)
    - Create `/api/admin/users/{id}/approve` POST
    - Create `/api/admin/users/{id}/block` POST
    - Create `/api/admin/users/{id}/status` PUT for arbitrary status changes
    - Add admin-only guard that returns ACCESS_DENIED for non-admin users
    - _Requirements: 26.3, 26.4, 26.5, 26.6, 26.7, 26.9_

  - [x] 2.4 Write unit tests for authentication and admin services
    - Test OAuth callback handling and session creation
    - Test first-user-admin rule
    - Test status transitions (approve, block, pending)
    - Test blocked user login rejection
    - Test admin-only access guard
    - _Requirements: 25.1–25.10, 26.1–26.9_

  - [x] 2.5 Write property test for per-user data isolation
    - **Property 24: Per-User Data Isolation**
    - Generate multi-user data sets, verify no cross-contamination in queries
    - **Validates: Requirements 27.1, 27.2, 27.3, 27.4**

- [x] 3. Checkpoint - Ensure auth and infrastructure tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Implement trading transactions (core domain)
  - [x] 4.1 Implement TradingService with create, edit, delete, list operations
    - Create transaction: validate inputs, compute gross_value and net_capital_flow, persist
    - Edit transaction: validate, check holdings invariant, recalculate derived fields, persist
    - Delete transaction: check holdings invariant, remove record, recalculate portfolio
    - List transactions: support sorting by date desc, filters (date range, symbol, broker, action)
    - Holdings check: reject sell/delete/edit if resulting quantity < 0
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.9, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

  - [x] 4.2 Implement snapshot import (bulk import)
    - Accept array of snapshot entries, validate all-or-nothing (atomic)
    - Reject entire batch if any entry fails validation
    - Store with Action="Snapshot" and date label "(Snapshot)"
    - Include snapshot quantities in holdings calculation
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

  - [x] 4.3 Create trading transaction API routes
    - POST `/api/transactions` — create buy/sell transaction
    - GET `/api/transactions` — list with filters (date_from, date_to, symbol, broker, action)
    - PUT `/api/transactions/{id}` — edit transaction
    - DELETE `/api/transactions/{id}` — delete transaction
    - POST `/api/transactions/snapshot` — bulk import
    - Wire routes to TradingService with user_id from auth middleware
    - _Requirements: 1.1–1.8, 2.1–2.6, 4.1–4.9, 6.1–6.6_

  - [x] 4.4 Write property tests for trading calculations
    - **Property 1: Net Capital Flow Calculation**
    - Generate random qty, price, fee, vat; verify gross_value = qty × price, net_capital_flow follows buy/sell formula
    - **Validates: Requirements 1.1, 1.2, 1.3**

  - [x] 4.5 Write property test for input validation rejection
    - **Property 2: Invalid Transaction Inputs Are Rejected**
    - Generate transactions with missing fields, invalid values; verify rejection with error details
    - **Validates: Requirements 1.4, 1.5, 1.7, 1.8**

  - [x] 4.6 Write property test for holdings quantity invariant
    - **Property 3: Holdings Quantity Invariant**
    - Generate sequences of buy/sell/snapshot; verify total held = Σbuy + Σsnapshot - Σsell, no negatives allowed
    - **Validates: Requirements 1.6, 2.2, 6.1, 6.3**

  - [x] 4.7 Write property test for snapshot atomicity
    - **Property 4: Snapshot Import Atomicity**
    - Generate batches with some invalid entries; verify entire batch rejected, nothing persisted
    - **Validates: Requirements 2.5, 2.4, 2.6**

  - [x] 4.8 Write property test for edit recalculation
    - **Property 25: Edit Recalculation Consistency**
    - Generate edit operations; verify gross_value, net_capital_flow, and holdings are recalculated correctly
    - **Validates: Requirements 6.5**

- [x] 5. Implement money transfers
  - [x] 5.1 Implement TransferService with create, edit, delete, list operations
    - Create transfer: validate 4 fields (date, broker, type, amount), persist
    - Edit transfer: validate, preserve unchanged fields, persist
    - Delete transfer: remove record
    - List transfers: sorted by date desc, filter by broker (case-insensitive)
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 7.1, 7.2, 7.3, 7.4_

  - [x] 5.2 Create money transfer API routes
    - POST `/api/transfers` — create transfer
    - GET `/api/transfers` — list with optional broker filter
    - PUT `/api/transfers/{id}` — edit transfer
    - DELETE `/api/transfers/{id}` — delete transfer
    - Wire routes to TransferService with user_id from auth middleware
    - _Requirements: 3.1–3.7, 7.1–7.4_

  - [x] 5.3 Write property test for transfer validation
    - **Property 5: Transfer Validation**
    - Generate invalid transfers (bad amounts, blank broker, invalid type, future dates); verify rejection
    - **Validates: Requirements 3.4, 3.5, 3.6, 3.7**

  - [x] 5.4 Write property tests for query sorting and filtering
    - **Property 6: Query Results Are Sorted**
    - Generate records with random dates; verify trading log desc, transfers desc, performance asc
    - **Property 7: Filter Correctness (AND Logic)**
    - Generate records + random filter combos; verify all results satisfy ALL active filters
    - **Validates: Requirements 3.2, 3.3, 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 10.2**

- [x] 6. Checkpoint - Ensure core trading and transfer tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Implement market data service and portfolio
  - [x] 7.1 Implement MarketDataService with Redis caching
    - Fetch ticker info via yfinance: all 16 fields (longName, currentPrice, sector, industry, etc.)
    - Cache results in Redis with configurable TTL (default 1 hour for portfolio, 15 min for trending)
    - Check cache staleness before fetching
    - Handle errors: symbol not found, network failure, rate limiting (exponential backoff)
    - Return cached data on failure, display staleness warning
    - Display "N/A" for fields that are None from yfinance
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 12.7, 12.8, 12.9, 12.10_

  - [x] 7.2 Implement PortfolioService with calculations
    - Calculate avg_cost (weighted average across buys + snapshots)
    - Calculate allocation (position cost / total cost × 100)
    - Calculate unrealized P/L (market_value - total_cost)
    - Calculate ROI percent (unrealized_pl / total_cost × 100)
    - Aggregate totals row (sum of costs, market values, P/L)
    - Exclude zero-quantity positions
    - Set/get sentiment per stock (Bear/Bull)
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8, 5.9, 5.10_

  - [x] 7.3 Create portfolio API routes
    - GET `/api/portfolio/summary` — aggregated portfolio with market data
    - POST `/api/portfolio/refresh` — force market data refresh
    - PUT `/api/portfolio/{symbol}/sentiment` — set Bear/Bull sentiment
    - Wire to PortfolioService and MarketDataService
    - _Requirements: 5.1–5.10, 12.1–12.10_

  - [x] 7.4 Write property tests for portfolio calculations
    - **Property 8: Average Cost Weighted Calculation**
    - Generate buy/snapshot sets; verify weighted average formula
    - **Property 9: Allocation Sum Invariant**
    - Generate multi-position portfolios; verify sum = 100% within tolerance
    - **Property 10: Portfolio Aggregate Totals**
    - Generate positions; verify aggregate cost = Σ costs, aggregate MV = Σ MVs, aggregate P/L = MV - cost
    - **Property 11: Zero-Quantity Exclusion**
    - Generate positions with some at zero quantity; verify excluded from results
    - **Validates: Requirements 5.2, 5.3, 5.4, 5.5**

- [x] 8. Implement dashboard and performance history
  - [x] 8.1 Implement DashboardService
    - Calculate Total Invested (sum of "In" transfers), Total Withdrawn (sum of "Out" transfers), Net Invested
    - Calculate Total Market Value (Σ qty × current_price), Overall P/L, Overall ROI
    - Calculate capital per broker (net "In" minus "Out" per broker)
    - Count held positions and distinct brokers
    - Handle case: no data → all zeros; incomplete market data → show "not available"
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7, 9.8_

  - [x] 8.2 Implement PerformanceService with snapshots and returns
    - Record snapshot: date, total_portfolio_value, total_cost
    - List snapshots sorted by date ascending with period return calculation
    - Calculate period return: (current - previous) / previous × 100
    - Calculate cumulative return: (latest - earliest) / earliest × 100
    - Support date range filter, monthly/yearly aggregation views
    - Edit/delete snapshots with adjacent period return recalculation
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7, 10.8, 10.9, 10.10, 10.11, 10.12, 10.13_

  - [x] 8.3 Create dashboard and performance API routes
    - GET `/api/dashboard` — aggregated dashboard data
    - GET `/api/performance/snapshots` — list with filters
    - POST `/api/performance/snapshots` — record snapshot
    - PUT `/api/performance/snapshots/{id}` — edit snapshot
    - DELETE `/api/performance/snapshots/{id}` — delete snapshot
    - _Requirements: 9.1–9.8, 10.1–10.13_

  - [x] 8.4 Write property tests for dashboard and performance calculations
    - **Property 12: Dashboard Monetary Aggregations**
    - Generate transfers; verify Total Invested = Σ"In", Total Withdrawn = Σ"Out", Net = In - Out, per-broker breakdown
    - **Property 13: Period Return Calculation**
    - Generate consecutive snapshots; verify ((current - previous) / previous) × 100
    - **Property 14: Cumulative Return Calculation**
    - Generate snapshot sequences; verify ((latest - earliest) / earliest) × 100
    - **Validates: Requirements 9.1, 9.4, 10.3, 10.4**

- [x] 9. Checkpoint - Ensure portfolio, dashboard, and performance tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. Implement trade journal, price alerts, and dividends
  - [x] 10.1 Implement trade journal (notes and tags on transactions)
    - PUT `/api/transactions/{id}/notes` — attach/update note (max 1000 chars)
    - PUT `/api/transactions/{id}/tags` — set tags on transaction
    - GET `/api/journal/tags` — list all user tags with filtering
    - Support predefined tags + custom tags (1–50 chars)
    - Filter trading log by tag
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5_

  - [x] 10.2 Implement price alerts service and endpoints
    - POST `/api/alerts` — create alert (symbol, type Above/Below, target_price, optional note)
    - GET `/api/alerts` — list active alerts sorted by symbol
    - DELETE `/api/alerts/{id}` — delete alert
    - Trigger check: on market data refresh, mark alerts as triggered when price crosses target
    - Support multiple alerts per symbol
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5, 14.6_

  - [x] 10.3 Implement dividend tracker service and endpoints
    - POST `/api/dividends` — record dividend (date, symbol, amount_per_share, shares_held, total_amount)
    - GET `/api/dividends` — list sorted by date desc
    - GET `/api/dividends/summary` — by stock or by time period (monthly/yearly)
    - GET `/api/dividends/projection` — projected annual income based on recent rate × current qty
    - Calculate dividend yield on cost: (annual dividends / total cost) × 100
    - _Requirements: 15.1, 15.2, 15.3, 15.4, 15.5, 15.6_

  - [x] 10.4 Write property tests for alerts and dividends
    - **Property 15: Price Alert Trigger Correctness**
    - Generate alert configs + market prices; verify trigger iff (Above AND price >= target) OR (Below AND price <= target)
    - **Property 26: Dividend Yield on Cost Calculation**
    - Generate dividend records + costs; verify (annual_dividends / total_cost) × 100
    - **Validates: Requirements 14.2, 15.3**

- [x] 11. Implement realized P/L and rebalancing
  - [x] 11.1 Implement realized P/L auto-calculation
    - On each sell transaction, auto-calculate: (sell_price - avg_cost_at_sale) × sell_qty
    - Store: date, symbol, sell_qty, sell_price, avg_cost_at_sale, realized_pl, hold_duration_days, term_type
    - Classify: Short-term (<365 days) or Long-term (≥365 days)
    - GET `/api/realized-pl` — list sorted by date desc
    - GET `/api/realized-pl/summary` — cumulative totals (monthly, yearly, all-time)
    - Support time period filter
    - _Requirements: 16.1, 16.2, 16.3, 16.4, 16.5, 16.6_

  - [x] 11.2 Implement portfolio rebalancing insights
    - PUT `/api/portfolio/rebalancing/targets` — set target allocations (must sum to 100%)
    - GET `/api/portfolio/rebalancing` — show current vs target, difference, over/under-weight highlights
    - Suggest buy/sell actions based on current prices to reach targets
    - Configurable deviation threshold (default 5pp)
    - _Requirements: 17.1, 17.2, 17.3, 17.4, 17.5_

  - [x] 11.3 Implement risk metrics endpoint
    - GET `/api/portfolio/risk-metrics` — portfolio beta, sector concentration, position concentration, max drawdown
    - Portfolio beta: weighted average of position betas by allocation
    - Sector concentration: % per sector from yfinance data
    - Warnings: sector > 50% of portfolio, single stock > 25% of portfolio
    - Max drawdown: largest peak-to-trough decline from performance snapshots
    - _Requirements: 18.1, 18.2, 18.3, 18.4, 18.5_

  - [x] 11.4 Write property tests for realized P/L and risk metrics
    - **Property 16: Realized P/L Calculation**
    - Generate sell params; verify (sell_price - avg_cost) × qty, classify short/long-term
    - **Property 17: Target Allocation Sum Constraint**
    - Generate target allocations; verify sum = 100%
    - **Property 18: Portfolio Beta Weighted Average**
    - Generate positions with betas; verify Σ(allocation × beta)
    - **Property 19: Concentration Warning Thresholds**
    - Generate portfolios; verify sector >50% triggers warning, stock >25% triggers warning
    - **Property 20: Maximum Drawdown Calculation**
    - Generate value sequences; verify largest peak-to-trough / peak × 100
    - **Validates: Requirements 16.1, 16.5, 17.1, 18.1, 18.3, 18.4, 18.5**

- [x] 12. Checkpoint - Ensure realized P/L, rebalancing, and risk metric tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 13. Implement watchlist, trending, tags, ideas, screener
  - [x] 13.1 Implement watchlist service and endpoints
    - POST `/api/watchlist` — add stock (symbol, optional interested_at_price, optional notes)
    - GET `/api/watchlist` — list with market data, highlight "At Target" (price ≤ interested_at_price)
    - PUT `/api/watchlist/{id}` — update notes/target price
    - DELETE `/api/watchlist/{id}` — remove entry
    - _Requirements: 19.1, 19.2, 19.3, 19.4, 19.5, 19.6, 19.7_

  - [x] 13.2 Implement trending stocks endpoint
    - GET `/api/trending` — fetch trending/gainers/losers/most active from yfinance
    - Cache results in Redis with 15-minute TTL
    - Return: symbol, company_name, current_price, day_change_percent, volume
    - _Requirements: 20.1, 20.2, 20.3, 20.4, 20.5, 20.6_

  - [x] 13.3 Implement stock tags and categories
    - POST `/api/tags` — create custom tag (1–50 chars, unique case-insensitive per user)
    - GET `/api/tags` — list all tags
    - DELETE `/api/tags/{id}` — delete tag (remove from all associated stocks)
    - PUT `/api/stocks/{symbol}/tags` — assign tags to stock
    - GET `/api/tags/{id}/stocks` — stocks with this tag
    - GET `/api/tags/performance` — aggregated performance per tag (total cost, MV, P/L, ROI)
    - _Requirements: 21.1, 21.2, 21.3, 21.4, 21.5, 21.6, 21.7_

  - [x] 13.4 Implement investment ideas (thesis board)
    - POST `/api/ideas` — create idea (symbol, title, thesis, target_entry_price, risk_level, source_link, status)
    - GET `/api/ideas` — list sorted by updated_at desc, filter by status/risk/symbol
    - PUT `/api/ideas/{id}` — update idea, allow linking to transaction when status="Bought"
    - DELETE `/api/ideas/{id}` — delete idea
    - _Requirements: 22.1, 22.2, 22.3, 22.4, 22.5, 22.6, 22.7_

  - [x] 13.5 Implement stock screener
    - POST `/api/screener/search` — execute filter query (PE range, dividend yield range, market cap, sector, industry)
    - GET `/api/screener/presets` — list saved presets
    - POST `/api/screener/presets` — save preset (name 1–100 chars, filter criteria as JSON)
    - DELETE `/api/screener/presets/{id}` — delete preset
    - Limit results to 50 stocks per query
    - _Requirements: 24.1, 24.2, 24.3, 24.4, 24.5, 24.6, 24.7_

  - [x] 13.6 Write property tests for watchlist, tags, and tag filtering
    - **Property 21: Watchlist "At Target" Highlight**
    - Generate watchlist items + prices; verify highlight iff current_price ≤ interested_at_price
    - **Property 22: Tag Filter Correctness**
    - Generate tagged items + tag filter; verify all results have the tag, no tagged items excluded
    - **Property 23: Per-Tag Performance Aggregation**
    - Generate tagged stocks with costs/values; verify aggregated metrics per tag
    - **Validates: Requirements 19.4, 21.4, 21.5**

- [x] 14. Checkpoint - Ensure watchlist, tags, and advanced feature tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 15. Implement frontend pages (core)
  - [x] 15.1 Implement Login page with OAuth buttons
    - Display "Sign in with Google" and "Sign in with Facebook" buttons
    - Initiate OAuth flows on click
    - Handle callback redirect, display errors, show "Pending Approval" message
    - _Requirements: 25.1, 25.2, 25.3, 25.5, 25.7_

  - [x] 15.2 Implement NavigationMenu component
    - Persistent sidebar with links: Dashboard, Trading Log, Money Transfers, Portfolio Summary, Performance History, Trade Journal, Watchlist, Investment Ideas
    - Admin link visible only for admin users
    - Sub-sections: Trending Stocks, Sector Heatmap, Stock Screener, Portfolio Rebalancing, Price Alerts, Dividend Tracker, Realized P/L
    - Display user's name, profile picture, and Logout button
    - Highlight active page, preserve unsaved form data on same-page click
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7, 11.8_

  - [x] 15.3 Implement Dashboard page
    - Display: Total Invested, Total Withdrawn, Net Invested, Total Market Value, Overall P/L, Overall ROI%
    - Capital per broker breakdown
    - Total held positions count, total brokers count
    - Handle empty state (all zeros) and incomplete market data state
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7, 9.8_

  - [x] 15.4 Implement Trading Log page with CRUD forms
    - Transaction table: Date, Symbol, Action, Qty, Price, Gross Value, Fee, VAT, Net Capital Flow, Broker
    - Create/Edit form with validation and auto-calculated Gross Value
    - Delete with confirmation
    - Snapshot import form (bulk entries)
    - Filter panel: date range, symbol, broker, action type
    - Display "(Snapshot)" label for snapshot entries
    - Show confirmation toast on success (3+ seconds)
    - Retain form data on save failure
    - _Requirements: 1.1–1.8, 2.1–2.6, 4.1–4.9, 6.1–6.6, 8.3, 8.5_

  - [x] 15.5 Implement Money Transfers page with CRUD forms
    - Transfer table: Date, Broker, Type, Amount
    - Create/Edit form with validation
    - Delete with confirmation
    - Filter by broker
    - Show confirmation toast on success (3+ seconds)
    - Retain form data on save failure
    - _Requirements: 3.1–3.7, 7.1–7.4, 8.4, 8.6_

  - [x] 15.6 Implement Portfolio Summary page
    - Display positions table with all fields (calculated + market data + sentiment)
    - Total summary row with aggregates
    - Market data refresh button and last-refresh timestamp
    - Sentiment Bear/Bull selector per stock
    - Empty state when no positions
    - Handle missing market data (show "N/A" or "not available")
    - _Requirements: 5.1–5.10, 12.3, 12.5, 12.6, 12.7, 12.8, 12.9_

  - [x] 15.7 Implement Performance History page
    - Snapshots table: Date, Portfolio Value, Total Cost, P/L, Period Return
    - Line chart visualization of portfolio value over time
    - Create/Edit/Delete snapshot forms
    - Cumulative return display
    - Date range filter, monthly/yearly aggregation views
    - Empty state message prompting user to record first snapshot
    - _Requirements: 10.1–10.13_

- [x] 16. Implement frontend pages (advanced features)
  - [x] 16.1 Implement Trade Journal page
    - View notes and tags on transactions
    - Edit notes (up to 1000 chars)
    - Manage tags (predefined + custom)
    - Filter by tag
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5_

  - [x] 16.2 Implement Watchlist page
    - Display watched stocks with market data, "At Target" highlights
    - Add/remove stocks, set interested_at_price, add notes
    - Option to add trending stocks to watchlist
    - _Requirements: 19.1–19.7, 20.5_

  - [x] 16.3 Implement Investment Ideas page
    - Idea cards with status, risk level, target entry, current price
    - Create/Edit/Delete ideas
    - Filter by status, risk level, symbol
    - Link to transaction when status = "Bought"
    - _Requirements: 22.1–22.7_

  - [x] 16.4 Implement Admin page
    - User list: display name, email, profile pic, provider, registration date, status
    - Approve/Block/Status change buttons
    - Admin-only route guard (redirect non-admins)
    - _Requirements: 26.3–26.9_

  - [x] 16.5 Implement sub-section pages: Trending, Heatmap, Screener, Rebalancing, Alerts, Dividends, Realized P/L
    - Trending Stocks: gainers, losers, most active with "Add to Watchlist" action
    - Sector Heatmap: treemap visualization colored by ROI, sized by allocation, hover details
    - Stock Screener: filter form (PE, yield, cap, sector), results table, save/load presets
    - Portfolio Rebalancing: current vs target allocation table, deviation highlights, suggested actions
    - Price Alerts: active alerts list, create/delete alerts, triggered notification display
    - Dividend Tracker: records table, summary by stock/period, projected annual income
    - Realized P/L: records table with term classification, cumulative totals, period filter
    - _Requirements: 14.1–14.6, 15.1–15.6, 16.1–16.6, 17.1–17.5, 18.1–18.5, 20.1–20.6, 23.1–23.5, 24.1–24.7_

  - [x] 16.6 Implement shared UI components
    - ConfirmationToast: success/error messages, visible 3+ seconds, dismissible
    - MarketDataBadge: last refresh timestamp display
    - FilterPanel: reusable date range, symbol, broker, action type controls
    - DataTable: sortable, filterable table component
    - SectorHeatmap: treemap chart (use recharts Treemap)
    - PerformanceChart: line chart for portfolio value over time
    - _Requirements: 8.3, 8.4, 12.5, 23.1–23.5_

- [x] 17. Checkpoint - Ensure frontend builds and renders correctly
  - Ensure all tests pass, ask the user if questions arise.

- [x] 18. Integration wiring and final testing
  - [x] 18.1 Wire frontend to backend API with auth flow
    - Configure API client with session cookie handling
    - Implement login/logout flow end-to-end
    - Add route guards for authenticated pages
    - Add admin route guard for Admin page
    - Handle pending/blocked user states in frontend
    - _Requirements: 25.1–25.10, 26.9, 27.1–27.6_

  - [x] 18.2 Implement sector heatmap backend endpoint
    - GET `/api/portfolio/sector-heatmap` — aggregate positions by sector from yfinance data
    - Return: sector, total_cost, total_market_value, roi_percent, allocation_percent, position_count
    - _Requirements: 23.1–23.5_

  - [x] 18.3 Write integration tests for critical API flows
    - Test full transaction lifecycle: create → list → edit → delete
    - Test portfolio calculation with market data mocked
    - Test admin approval workflow
    - Test multi-user data isolation at API level
    - Test market data caching behavior
    - _Requirements: 1.1–1.8, 5.1–5.10, 26.1–26.9, 27.1–27.6_

- [x] 19. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation at natural break points
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- Backend uses Python (FastAPI + SQLAlchemy + Hypothesis for PBT)
- Frontend uses TypeScript (React + Vite + fast-check for PBT)
- All monetary values are in THB (Thai Baht) with 2 decimal places
- Market data shared across users (cached in Redis); all other data is per-user isolated

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.4"] },
    { "id": 1, "tasks": ["1.2", "1.3", "1.5"] },
    { "id": 2, "tasks": ["2.1", "4.1", "5.1"] },
    { "id": 3, "tasks": ["2.2", "2.3", "4.2", "4.3", "5.2"] },
    { "id": 4, "tasks": ["2.4", "2.5", "4.4", "4.5", "4.6", "4.7", "5.3", "5.4"] },
    { "id": 5, "tasks": ["4.8", "7.1"] },
    { "id": 6, "tasks": ["7.2", "7.3", "8.1", "8.2"] },
    { "id": 7, "tasks": ["7.4", "8.3", "10.1", "10.2", "10.3"] },
    { "id": 8, "tasks": ["8.4", "10.4", "11.1", "11.2", "11.3"] },
    { "id": 9, "tasks": ["11.4", "13.1", "13.2", "13.3", "13.4", "13.5"] },
    { "id": 10, "tasks": ["13.6", "15.1", "15.2"] },
    { "id": 11, "tasks": ["15.3", "15.4", "15.5", "15.6", "15.7"] },
    { "id": 12, "tasks": ["16.1", "16.2", "16.3", "16.4", "16.5", "16.6"] },
    { "id": 13, "tasks": ["18.1", "18.2"] },
    { "id": 14, "tasks": ["18.3"] }
  ]
}
```
