# Requirements Document

## Introduction

The Investment History feature is a comprehensive personal investment management platform named **My Investment**. The system allows investors to record daily buy/sell transactions, track money transfers, import existing positions via snapshots, view portfolio summaries with market data, monitor performance history, maintain trade journals, manage watchlists, track investment ideas, receive alerts, analyze risk, and review portfolio behavior over time.

This revised version upgrades the product direction from a basic investment tracker into a **Premium Personal Investment Cockpit**. The preferred visual direction is the **Dark Trading Dashboard** style: professional, data-dense, modern, and suitable for serious investors. The application should feel closer to a modern Bloomberg-style personal dashboard than a generic admin panel.

The system SHALL continue to use the same major information architecture and feature groups, while adding stronger portfolio intelligence, AI-generated insights, FX-aware performance tracking, benchmark comparison, portfolio attribution, scenario simulation, behavioral analytics, and a premium responsive UI/UX.

All investment data SHALL remain private and isolated per authenticated user. The system SHALL support Google and Facebook OAuth login, admin approval workflow, role-based access, and secure session handling. The admin panel SHALL manage only user account access and SHALL NOT expose other users' investment data.

The application SHALL provide a complete navigation menu with these main pages:

1. Dashboard
2. Portfolio Summary
3. Trading Log
4. Money Transfers
5. Performance History
6. Trade Journal
7. Watchlist
8. Investment Ideas
9. Stock Screener
10. Alerts
11. Dividend Tracker
12. Realized P/L
13. Risk & Rebalancing
14. Reports
15. Admin, admin-only

The system SHALL support light mode and dark mode, but the recommended default premium investor experience is **Dark Trading Dashboard Mode**.


### API and Data Provider Strategy

The system SHALL follow a **Free-First, Provider-Agnostic API Strategy** so that the product can be designed and implemented as a low-cost MVP first, while remaining upgradeable to paid market-data providers for production reliability.

The system SHALL NOT assume that any single free external API can support all premium dashboard features at production scale. Instead, external integrations SHALL be abstracted behind provider interfaces, cached, rate-limited, monitored, and replaceable through configuration.

The recommended MVP provider strategy SHALL be:
- **Market Data Primary:** Financial Modeling Prep free/basic tier, Alpha Vantage free tier, Twelve Data free tier, or EODHD free tier depending on available quotas and endpoint coverage.
- **Market Data Fallback / Prototype Only:** yfinance or Yahoo Finance wrappers MAY be used for personal prototype and research workflows only, but SHALL NOT be treated as a guaranteed production-grade data source.
- **Fundamentals / Financial Statements:** SEC EDGAR APIs SHALL be preferred for free US public-company fundamentals where possible. The system SHALL normalize CIK, ticker, XBRL taxonomy tags, fiscal periods, and units before using the data in analytics.
- **FX Rates:** A free FX provider such as UniRateAPI, ForexRateAPI, CurrencyApi.net, XRates, Alpha Vantage FX, or compatible equivalent SHALL be used for MVP, with daily caching by currency pair and date.
- **Email Notifications:** SMTP, Gmail API/OAuth, SendGrid, Mailgun, Amazon SES, or compatible provider SHALL be supported through a pluggable notification adapter.
- **AI Insights:** AI features SHALL support disabled mode, rule-based/template mode, local LLM mode, and hosted LLM API mode. The MVP SHALL be able to run without paid AI APIs by using rule-based insights.
- **Authentication:** Google OAuth and Facebook OAuth SHALL be integrated directly through standards-compliant OAuth flows.

The system SHALL use the following integration principles:
- All external API calls SHALL be made server-side only. API keys SHALL NOT be exposed to the frontend.
- All external API credentials SHALL be configured through environment variables or a secure secret store.
- The Market_Data_Service SHALL expose a unified internal data contract independent of any vendor-specific response shape.
- The system SHALL cache market data, FX rates, fundamentals, benchmark prices, screener results, and trending data to reduce cost and avoid free-tier rate-limit exhaustion.
- The system SHALL store provider name, fetch timestamp, source timestamp, data status, and raw response reference for auditability where practical.
- The system SHALL retain the last known valid cached value if provider refresh fails.
- The system SHALL show stale-data, missing-data, delayed-data, and low-confidence warnings directly in the UI.
- The system SHALL support manual override or manual entry for critical financial records such as transactions, transfers, dividends, FX rates, and cash adjustments.
- The system SHALL distinguish between **source-of-truth user data** and **supporting market/reference data**. User-entered transactions, transfers, dividends, journals, alerts, and thesis records SHALL remain the authoritative source for portfolio accounting.
- The system SHALL support provider fallback order and feature flags, for example: `MARKET_DATA_PROVIDER=fmp`, `MARKET_DATA_FALLBACK=yfinance`, `AI_PROVIDER=disabled`, and `FX_PROVIDER=unirate`.
- The system SHALL be designed so that a future paid provider can be enabled without changing portfolio accounting, UI components, or database ownership rules.

The system SHALL classify features into three implementation groups:
- **Internal Logic, No External API Required:** trading log, snapshots, transfers, cash ledger, average cost, tax lots, realized P/L, unrealized P/L, allocation, behavioral analytics, rebalancing, position sizing, scenario simulation, reports, admin approval, and per-user isolation.
- **Free API Feasible for MVP:** end-of-day prices, historical benchmark prices, FX rates, basic company profile, sector/industry, 52-week range, limited dividends, basic fundamentals, and basic screener data.
- **Likely Paid or Degraded in Production:** reliable real-time quotes, complete global fundamentals, complete dividend history, earnings calendars, trending stocks, advanced screener data, high-volume alerts, and hosted AI-generated insights.

### Implementation Phasing

Requirements SHALL be implemented in three phases:

**Phase 1 — MVP Core (Requirements 1–6, 9, 35–36, 39–41, 43–44)**
Core portfolio accounting, trading log, transfers, cash ledger, basic dashboard, navigation, dark theme, authentication, admin, per-user isolation, deployment, and non-functional requirements. No external market data required beyond optional FX rates.

**Phase 2 — Market Data & Analytics (Requirements 7–8, 10–12, 15–18, 22–25, 38, 42, 46–47)**
Portfolio summary with market data, performance history, benchmark comparison, attribution, alerts, email notifications, dividend tracker, realized P/L, health score, watchlist, trending stocks, tags, professional tables, reports, provider management, and degradation mode.

**Phase 3 — Premium Intelligence (Requirements 13–14, 19–21, 26–33, 37)**
Trade journal, behavioral analytics, rebalancing, position sizing, risk dashboard, thesis board, thesis break monitoring, sector heatmap, stock screener, scenario simulator, AI weekly memo, AI trade review, one-click portfolio review, import/export, and responsive mobile experience.

### Data Volume Assumptions

- Up to 10,000 transactions per user
- Up to 100 portfolio positions per user
- Up to 3 years of daily performance snapshots
- Up to 50 watchlist symbols
- Up to 200 investment ideas per user
- Up to 500 alert rules per user
- Dashboard SHALL load primary metrics within 2 seconds under normal data volume

### Technology Summary

- **Backend:** FastAPI, Python 3.12+, SQLAlchemy/Alembic, PostgreSQL
- **Frontend:** React 18+, TypeScript, Tailwind CSS, Recharts/Tremor
- **Cache/Queue:** Redis
- **Auth:** Google OAuth 2.0, Facebook OAuth 2.0
- **Deployment:** Docker Compose (dev), Azure Container Apps / App Service (prod)
- **Testing:** pytest (backend), Vitest + React Testing Library (frontend)
- **Market Data:** Provider-agnostic adapter layer (FMP, Alpha Vantage, Twelve Data, EODHD, SEC EDGAR)

## Glossary

- **Trading_Log**: The system component responsible for recording and managing daily stock trading transactions including buys, sells, and snapshot imports.
- **Money_Transfer_Tracker**: The system component responsible for recording deposits and withdrawals to and from broker accounts.
- **Portfolio_Summary**: The system component responsible for calculating and displaying aggregated per-stock position data including market data, unrealized P/L, allocation, and risk indicators.
- **Dashboard**: The high-level overview page showing portfolio value, gains/losses, alerts, recent changes, risk warnings, and recommended actions.
- **Performance_Tracker**: The system component responsible for storing historical portfolio value snapshots and calculating returns over time.
- **Navigation_Menu**: The persistent application navigation component.
- **Transaction**: A single trading action for a specific stock on a specific date.
- **Snapshot**: A bulk import entry representing an existing stock position imported into the system.
- **Stock_Symbol**: The ticker symbol identifying a traded stock.
- **Broker**: The brokerage platform used for a transaction or transfer.
- **Gross_Value**: Quantity multiplied by Price per Share.
- **Brokerage_Fee**: A manually entered trading fee, expected to be 0.15% of Gross Value unless overridden by the user.
- **VAT**: Value Added Tax, expected to be 7% of Brokerage Fee unless overridden by the user.
- **Net_Capital_Flow**: For buys, Gross Value plus Brokerage Fee plus VAT. For sells, Gross Value minus Brokerage Fee minus VAT.
- **Transfer_Type**: The direction of a money transfer, either In or Out.
- **Original_Currency**: Currency used in the original transfer, such as THB or USD.
- **Converted_USD_Amount**: The USD amount calculated from the original transfer amount using the applicable FX rate.
- **FX_Rate**: The exchange rate used to convert a non-USD amount into USD.
- **FX_Fee**: Any broker or bank fee related to currency conversion.
- **Cash_Ledger**: A broker-level cash accounting record calculated from deposits, withdrawals, buys, sells, fees, taxes, and dividends.
- **Avg_Cost**: Weighted average cost per share across buy and snapshot entries.
- **Tax_Lot**: A specific purchase lot used for realized P/L calculation under FIFO, LIFO, Average Cost, or Specific Lot methods.
- **Unrealized_PL**: Market Value minus Total Cost for a currently held position.
- **Realized_PL**: Profit or loss crystallized when shares are sold.
- **ROI_Percent**: Profit or loss divided by cost basis, expressed as a percentage.
- **Allocation**: Position value or cost divided by the total portfolio value or total cost.
- **Benchmark**: A market index, ETF, or custom reference used to compare portfolio performance.
- **Alpha**: Portfolio return minus benchmark return over the same period.
- **Portfolio_Attribution**: The breakdown of performance contribution by stock, sector, tag, broker, strategy, dividend, realized gain, unrealized gain, and FX.
- **Portfolio_Health_Score**: A 0 to 100 score summarizing diversification, return quality, benchmark performance, risk, concentration, data completeness, and thesis discipline.
- **AI_Weekly_Memo**: An AI-generated weekly review summarizing portfolio performance, risk, changes, alerts, and suggested next actions.
- **AI_Trade_Review**: An AI-generated post-trade analysis explaining trade outcome, holding period, journaled reasoning, and behavioral patterns.
- **Thesis_Board**: A structured research board for managing investment ideas from research to execution or rejection.
- **Thesis_Break_Condition**: A user-defined condition that invalidates or weakens the original investment thesis.
- **Scenario_Simulator**: A tool that models portfolio impact if prices, allocations, FX rates, or cash deployment change.
- **Position_Sizing**: A recommendation engine that calculates suggested position size based on portfolio risk, stop loss, volatility, confidence, and target allocation.
- **Smart_Alert**: A notification based on price, risk, allocation, drawdown, valuation, thesis review, earnings date, or data quality condition.
- **What_Changed**: Dashboard section summarizing important portfolio changes since the user's last login.
- **Data_Quality_Score**: A 0 to 100 score indicating whether transactions, market data, notes, theses, snapshots, and FX records are complete and reliable.
- **Market_Data_Service**: The component responsible for fetching and caching public market data such as prices, company profile, valuation, dividend yield, beta, sector, and industry.
- **Stock_Screener**: A tool for discovering stocks based on financial criteria and strategy presets.
- **OAuth**: Third-party authentication protocol used for Google and Facebook login.
- **Admin**: The site owner or authorized administrator who approves, blocks, or manages accounts.
- **User_Status**: The access state of a registered user: Approved, Pending, or Blocked.
- **Dark_Trading_Dashboard_Mode**: The premium dark investor interface selected as the preferred product direction.

## Requirements

### Requirement 1: Record Daily Trading Transactions

**User Story:** As an investor, I want to record daily buy and sell stock transactions with broker, fee, and currency details, so that my trading records and portfolio calculations are accurate.

#### Acceptance Criteria
- WHEN a user submits a buy or sell transaction, THE Trading_Log SHALL store Date, Stock Symbol, Action, Quantity, Price per Share, Gross Value, Brokerage Fee, VAT, Net Capital Flow, Broker, Currency, and optional Note.
- THE system SHALL validate required fields and reject missing or invalid values with clear field-level error messages.
- THE system SHALL automatically calculate Gross Value as Quantity multiplied by Price per Share.
- THE system SHALL calculate Net Capital Flow based on the Action type.
- THE system SHALL reject a sell transaction if the sell Quantity exceeds total owned shares for the Stock Symbol under the selected cost basis method.
- THE system SHALL reject future dates and invalid date formats.
- THE system SHALL assign a unique identifier to each transaction.
- THE system SHALL persist all transaction data across application restarts.

### Requirement 2: Bulk Import Existing Positions via Snapshot

**User Story:** As an investor with existing holdings, I want to bulk-import current positions as snapshots, so that I can start using the system without entering all historical transactions manually.

#### Acceptance Criteria
- THE Trading_Log SHALL support snapshot entries with Stock Symbol, Quantity, Avg Cost, Broker, Currency, and optional Acquisition Date.
- Snapshot entries SHALL be included in holdings, cost basis, allocation, and performance calculations.
- Snapshot rows SHALL be visually distinguished from normal buy/sell transactions.
- THE system SHALL reject the entire import if one or more snapshot rows fail validation.
- THE system SHALL report all row-level validation errors.

### Requirement 3: Track Money Transfers with FX Support

**User Story:** As an investor, I want to record deposits, withdrawals, and currency conversions, so that I can understand real invested capital in both THB and USD.

#### Acceptance Criteria
- THE Money_Transfer_Tracker SHALL store Date, Broker, Transfer Type, Original Currency, Original Amount, FX Rate, Converted USD Amount, FX Fee, and optional Note.
- THE system SHALL support THB, USD, and future extensible currencies.
- WHEN Original Currency is not USD, THE system SHALL require FX Rate or automatically fetch/apply a rate if configured.
- THE system SHALL calculate Converted USD Amount as Original Amount divided by FX Rate for THB-to-USD conversion unless a different currency convention is configured.
- THE system SHALL preserve both original currency amount and converted USD value.
- THE Dashboard SHALL use Converted USD Amount for Net Invested, Total Invested, and Total Withdrawn.
- THE system SHALL allow users to edit transfer and FX details while preserving audit history.
- THE system SHALL cache FX rates by currency pair and date to minimize free API usage.
- THE system SHALL support manual FX rate entry when no free provider is configured or when provider data is unavailable.
- THE system SHALL store FX provider name, source timestamp, and fetch timestamp for auditability.
- THE system SHALL classify FX data as stale when no valid rate is available for the selected transaction or transfer date.

### Requirement 4: Cash Ledger by Broker

**User Story:** As an investor, I want to see cash balance per broker, so that I know how much capital is idle, deployed, or available for future trades.

#### Acceptance Criteria
- THE system SHALL calculate broker-level cash using deposits, withdrawals, buys, sells, fees, taxes, dividends, and FX conversion records.
- THE Cash_Ledger SHALL show Starting Cash, Deposits, Withdrawals, Buy Outflows, Sell Inflows, Fees, Dividends, FX Adjustments, and Ending Cash.
- THE system SHALL display Cash Available by Broker and Total Cash Available on Dashboard and Portfolio Summary.
- THE system SHALL warn when calculated cash balance becomes negative.
- THE system SHALL support manual cash adjustment entries with notes and audit trail.

### Requirement 5: View Trading Log History

**User Story:** As an investor, I want to view, filter, sort, and export my complete trading log, so that I can review all investment activity.

#### Acceptance Criteria
- THE Trading_Log SHALL display transactions sorted by Date descending by default.
- THE Trading_Log SHALL support filters by date range, symbol, broker, action, tag, strategy, and realized/unrealized status.
- THE Trading_Log SHALL support sortable table headers and sticky table headers.
- THE Trading_Log SHALL support client-side pagination with configurable items per page (10, 20, 50, 100) and page navigation controls including Previous, page numbers, and Next buttons with "Showing X to Y of Z entries" status text.
- THE Trading_Log table SHALL use fixed column widths with table-layout: fixed to ensure header and body columns are perfectly aligned. Numeric columns (Qty, Price, Gross Value, Fee, VAT, Net Capital Flow) SHALL be right-aligned in both header and data cells.
- THE Trading_Log SHALL support row actions: View Details, Edit, Delete, Add Note, Create Thesis, Set Alert.
- THE Trading_Log SHALL support CSV export.
- THE Trading_Log SHALL support Excel (.xlsx) export of all visible/filtered transactions with proper column headers matching the table display.
- THE Trading_Log SHALL support Excel (.xlsx) import with the following rules:
  - THE import SHALL accept an Excel file matching the exported column format (Date, Symbol, Action, Qty, Price, Fee, VAT, Broker).
  - THE system SHALL validate each row for required fields, valid data types, valid date format, and positive numeric values.
  - THE system SHALL detect duplicate transactions by matching Date + Symbol + Action + Quantity + Price per Share. If a duplicate is found, that row SHALL be rejected and reported as a duplicate.
  - THE system SHALL report all validation errors and duplicate rejections with row numbers before committing any import.
  - THE system SHALL NOT import any rows if one or more rows fail validation (atomic import — all or nothing).
  - THE system SHALL display a preview/summary of rows to be imported before the user confirms the import.
  - THE system SHALL show a success message with the count of imported transactions after a successful import.
- THE Trading_Log SHALL display Snapshot, Buy, Sell, Dividend, and Adjustment entries with clear visual badges.

### Requirement 6: Edit and Delete Transactions Safely

**User Story:** As an investor, I want to correct or remove erroneous transactions, so that my portfolio remains accurate.

#### Acceptance Criteria
- THE system SHALL allow editing transaction fields while preserving transaction ID and audit history.
- THE system SHALL reject edits or deletes that cause negative holdings or invalid cash ledger states unless explicitly handled by an adjustment.
- THE system SHALL recalculate holdings, average cost, tax lots, realized P/L, unrealized P/L, allocation, cash ledger, and dashboard metrics after successful edits or deletes.
- THE system SHALL confirm destructive actions through a confirmation modal.

### Requirement 7: Portfolio Summary

**User Story:** As an investor, I want a professional portfolio summary, so that I can evaluate positions, P/L, allocation, market data, and risk at a glance.

#### Acceptance Criteria
- THE Portfolio_Summary SHALL display Stock Symbol, Company Name, Quantity, Avg Cost, Total Cost, Current Price, Market Value, Unrealized P/L, ROI, Allocation, Sector, Industry, Beta, P/E, Dividend Yield, Price to Book, 52-week range, and user Sentiment.
- THE Portfolio_Summary SHALL show aggregate Total Cost, Market Value, Unrealized P/L, Overall ROI, Cash, Net Invested, and Total Portfolio Value.
- THE Portfolio_Summary SHALL support position-level badges: Winner, Loser, Overweight, Underweight, High Beta, Dividend, Speculative, Data Warning.
- THE Portfolio_Summary SHALL allow row actions: Add Note, Set Alert, Create Thesis, Rebalance, Simulate.
- THE Portfolio_Summary SHALL exclude zero-quantity positions by default but allow viewing closed positions.

### Requirement 8: Market Data Integration, API Abstraction, and Data Quality

**User Story:** As an investor, I want reliable market data and clear data quality indicators, so that portfolio calculations are trustworthy.

#### Acceptance Criteria
- THE Market_Data_Service SHALL fetch price, company profile, sector, industry, valuation, dividend, beta, volume, and 52-week range data for portfolio and watchlist stocks.
- THE service SHALL cache market data and show last refreshed timestamp.
- THE system SHALL retain previously cached data if a refresh fails.
- THE system SHALL show N/A for unavailable fields.
- THE system SHALL flag suspicious data, such as extremely high dividend yield, missing sector, missing price, or stale data.
- THE system SHALL calculate a Data_Quality_Score for each portfolio and display missing or questionable data items.
- THE Market_Data_Service SHALL use a provider-agnostic adapter pattern so that FMP, Alpha Vantage, Twelve Data, EODHD, SEC EDGAR, yfinance fallback, or future paid providers can be swapped by configuration.
- THE system SHALL support free-tier rate-limit protection through Redis/database caching, request deduplication, batch refresh jobs, exponential backoff, and provider-level circuit breakers.
- THE system SHALL treat user-entered transactions and transfers as source-of-truth data, while market data SHALL be treated as supporting reference data.
- THE system SHALL store provider name, source timestamp, last fetched timestamp, stale status, and confidence status for each cached market-data item.
- THE system SHALL continue using the most recent valid cached data if external refresh fails, while clearly showing stale-data warnings.
- THE system SHALL allow manual refresh by user action, but SHALL prevent repeated calls that violate provider free-tier limits.
- THE system SHALL support a fallback provider order such as Primary Provider, Secondary Provider, Last Valid Cache, and Manual/N/A.
- THE system SHALL separate end-of-day MVP data from real-time production data in the UI through a clear data freshness label.

### Requirement 9: Dashboard / Overview Page

**User Story:** As an investor, I want a premium dashboard that tells me what happened, what matters, and what I should do next.

#### Acceptance Criteria
- THE Dashboard SHALL display Total Portfolio Value, Net Invested, Total Gain/Loss, Overall ROI, Cash Available, Daily Change, and Benchmark Comparison.
- THE Dashboard SHALL include a What_Changed section showing important changes since last login.
- THE Dashboard SHALL include an Action_Needed section for overdue thesis reviews, triggered alerts, concentration warnings, stale data, and rebalance opportunities.
- THE Dashboard SHALL include cards for Top Contributors, Top Detractors, Risk Warnings, Upcoming Earnings, Watchlist Near Target, and Recent Transactions.
- THE Dashboard SHALL include an AI Insight Card summarizing current portfolio condition in plain language.
- THE Dashboard SHALL support dark trading dashboard layout by default.

### Requirement 10: Performance History

**User Story:** As an investor, I want to track performance over time, so that I can understand portfolio trends and return quality.

#### Acceptance Criteria
- THE Performance_Tracker SHALL store portfolio value snapshots with Date, Total Market Value, Total Cost, Cash, Net Invested, FX Rate Snapshot, and Notes.
- THE system SHALL calculate Period Return, Cumulative Return, Monthly Return, Yearly Return, and Maximum Drawdown.
- THE system SHALL show performance chart with selectable ranges: 1D, 1W, 1M, 3M, YTD, 1Y, All.
- THE system SHALL support monthly and yearly aggregation.
- THE system SHALL allow editing and deleting snapshots with recalculation.
- THE system SHALL prompt the user to record a snapshot if performance data is stale.

### Requirement 11: Benchmark Comparison

**User Story:** As an investor, I want to compare my portfolio with benchmarks, so that I know whether I am outperforming or underperforming the market.

#### Acceptance Criteria
- THE system SHALL allow users to select one or more benchmarks such as S&P 500, Nasdaq 100, QQQ, SPY, VT, or a custom ticker.
- THE system SHALL calculate Portfolio Return, Benchmark Return, Alpha, Relative Performance, Tracking Difference, and Win/Loss months.
- THE Performance page SHALL show portfolio and benchmark lines on the same chart.
- THE Dashboard SHALL show whether the portfolio is outperforming or underperforming the selected benchmark over YTD, 1M, 3M, 1Y, and All periods.

### Requirement 12: Portfolio Attribution

**User Story:** As an investor, I want to know what drove my gains or losses, so that I can understand performance sources.

#### Acceptance Criteria
- THE system SHALL calculate attribution by Stock, Sector, Broker, Tag, Strategy, Currency/FX, Dividend, Realized P/L, and Unrealized P/L.
- THE system SHALL show top contributors and detractors over selected time periods.
- THE system SHALL display attribution as cards, bar charts, and drill-down tables.
- THE AI Insight Card SHALL summarize the largest drivers of portfolio performance.

### Requirement 13: Trade Journal / Notes

**User Story:** As an investor, I want to attach notes, tags, and reasoning to transactions, so that I can improve decision quality over time.

#### Acceptance Criteria
- THE system SHALL allow optional notes up to 2,000 characters per transaction.
- THE system SHALL support predefined and custom tags.
- THE system SHALL allow tagging trades by strategy, thesis, catalyst, risk level, and confidence.
- THE Trading Log and Trade Journal SHALL support filtering by tag, strategy, sentiment, and outcome.
- THE system SHALL use journal data in AI Trade Review and Behavioral Analytics.

### Requirement 14: Behavioral Analytics

**User Story:** As an investor, I want to understand my investment behavior, so that I can improve my process and avoid repeated mistakes.

#### Acceptance Criteria
- THE system SHALL calculate win rate, average winner, average loser, payoff ratio, holding period, best/worst tag, best/worst sector, and best/worst strategy.
- THE system SHALL identify patterns such as selling winners too early, holding losers too long, overtrading, or concentration in losing themes.
- THE system SHALL present behavioral insights using plain language and charts.
- THE behavior analytics SHALL use realized trades, journal tags, and holding periods.

### Requirement 15: Price Alerts and Smart Alerts

**User Story:** As an investor, I want intelligent alerts, so that I can react to important market and portfolio events.

#### Acceptance Criteria
- THE system SHALL support price alerts using Above and Below target prices.
- THE system SHALL support smart alerts for concentration, drawdown, overweight, underweight, high beta, stale data, thesis review overdue, upcoming earnings, dividend change, 52-week high/low, and watchlist target zone.
- THE system SHALL support in-app and email notifications.
- THE system SHALL allow alerts to be enabled, disabled, snoozed, deleted, and grouped by urgency.
- THE Alert Center SHALL display active, triggered, snoozed, and resolved alerts.
- THE system SHALL evaluate smart alerts primarily from internal portfolio data and cached market data, avoiding unnecessary external API calls.
- THE system SHALL degrade gracefully if market data is stale by showing alert confidence and data freshness indicators.

### Requirement 16: Email Alert Notifications

**User Story:** As an investor, I want to receive email notifications when important alerts trigger, so that I stay informed outside the application.

#### Acceptance Criteria
- THE system SHALL send HTML-formatted email notifications for triggered alerts when email alerts are enabled.
- SMTP configuration SHALL be controlled by environment variables.
- IF email sending fails, THE system SHALL log the error and continue in-app notification flow.
- THE system SHALL allow users to opt in or opt out of email alert categories.
- THE Email_Notification_Service SHALL use a pluggable provider adapter supporting SMTP, Gmail API/OAuth, SendGrid, Mailgun, Amazon SES, or compatible providers.
- THE system SHALL support development mode where email notifications are written to logs instead of sent externally.

### Requirement 17: Dividend Tracker

**User Story:** As an investor, I want to track dividends, so that I can monitor passive income and yield on cost.

#### Acceptance Criteria
- THE Dividend Tracker SHALL record Date, Stock Symbol, Amount per Share, Shares Held, Total Amount, Currency, Tax Withheld, and Broker.
- THE system SHALL calculate Yield on Cost and projected annual dividend income.
- THE system SHALL show dividend income by stock, broker, month, year, and portfolio percentage.
- THE system SHALL include dividends in cash ledger and total return calculations.
- THE system SHALL support manual dividend entry as the authoritative source for dividend accounting.
- External dividend APIs SHALL be used only for prefill, validation, projection, or missing-data warnings unless the user explicitly imports dividend records.
- THE system SHALL show data-source labels for API-derived dividend estimates.

### Requirement 18: Realized P/L and Tax Lot Accounting

**User Story:** As an investor, I want accurate realized gain/loss tracking, so that I can review performance and support tax planning.

#### Acceptance Criteria
- THE system SHALL support FIFO, LIFO, Average Cost, and Specific Lot Selection methods.
- THE default method SHALL be configurable by user.
- WHEN a sell transaction is recorded, THE system SHALL calculate realized P/L using the selected cost basis method.
- THE Realized P/L page SHALL show Date, Symbol, Quantity Sold, Sell Price, Cost Basis, Realized P/L, Holding Duration, Tax Lot Method, and Short-term/Long-term classification.
- THE system SHALL support export of realized P/L reports.

### Requirement 19: Portfolio Rebalancing Insights

**User Story:** As an investor, I want to compare actual allocation with target allocation, so that I can manage portfolio drift.

#### Acceptance Criteria
- THE system SHALL allow target allocation by stock, sector, tag, and asset class.
- THE system SHALL show current allocation, target allocation, difference, and status.
- THE system SHALL highlight deviations above a configurable threshold.
- THE system SHALL recommend buy/sell amounts or share quantities to rebalance.
- THE system SHALL allow scenario simulation before executing rebalancing actions.

### Requirement 20: Position Sizing Recommendation

**User Story:** As an investor, I want the system to suggest position size, so that I can size trades based on risk instead of emotion.

#### Acceptance Criteria
- THE system SHALL calculate suggested position size using portfolio value, max risk per trade, entry price, stop loss, confidence score, volatility, beta, and target allocation.
- THE system SHALL display recommended shares, capital required, portfolio allocation, and expected downside if stop loss is reached.
- THE system SHALL warn if proposed position causes concentration or sector limit violations.

### Requirement 21: Risk Metrics Dashboard

**User Story:** As an investor, I want to see risk metrics, so that I understand portfolio exposure and concentration.

#### Acceptance Criteria
- THE system SHALL display Portfolio Beta, Sector Concentration, Position Concentration, Maximum Drawdown, Volatility, Cash Ratio, and Risk Alerts.
- THE system SHALL warn if any single stock exceeds 25% of portfolio value.
- THE system SHALL warn if any sector exceeds 50% of portfolio value.
- THE system SHALL calculate risk metrics using current market value and historical snapshots.
- THE Risk page SHALL include a Portfolio_Health_Score.

### Requirement 22: Portfolio Health Score

**User Story:** As an investor, I want a single portfolio health score, so that I can quickly understand whether my portfolio needs attention.

#### Acceptance Criteria
- THE system SHALL calculate a Health Score from 0 to 100.
- THE score SHALL consider diversification, concentration, drawdown, benchmark relative performance, cash drag, data quality, thesis completeness, journal discipline, and risk-adjusted return.
- THE system SHALL explain score drivers in Strengths and Risks sections.
- THE system SHALL provide suggested next actions based on the score.

### Requirement 23: Watchlist

**User Story:** As an investor, I want to monitor stocks before buying, so that I can act when prices reach attractive levels.

#### Acceptance Criteria
- THE Watchlist SHALL store Symbol, Interested At Price, Notes, Tags, Risk Level, Target Entry, Target Exit, and optional Thesis link.
- THE system SHALL fetch market data for watchlist symbols.
- THE system SHALL highlight stocks at or near target price.
- THE Watchlist SHALL support row actions: Set Alert, Create Thesis, Add to Portfolio, Remove, Simulate.
- THE Watchlist page SHALL include a summary of opportunities near buy zone.

### Requirement 24: Trending and Popular Stocks

**User Story:** As an investor, I want to see trending stocks and market movers, so that I can discover new opportunities.

#### Acceptance Criteria
- THE system SHALL display Trending Stocks, Top Gainers, Top Losers, and Most Active names.
- THE system SHALL display up to 50 items per category (Gainers, Losers, Most Active).
- THE system SHALL cache trending data and refresh no more frequently than once per 15 minutes.
- THE system SHALL allow adding any trending stock to Watchlist or Investment Ideas.
- THE system SHALL show data source and last refreshed timestamp.
- THE Trending and Popular Stocks feature MAY be disabled or degraded in MVP when no free provider quota is available.
- THE system SHALL cache trending data for at least 15 minutes and SHALL NOT repeatedly call external providers within the cache window.
- THE system SHALL show an unavailable state rather than blocking the rest of the application when trending data cannot be fetched.
- THE Trending page SHALL default to showing 50 items per page with pagination options (10, 20, 50, 100).

### Requirement 25: Stock Tags and Categories

**User Story:** As an investor, I want to categorize stocks by custom tags, so that I can analyze strategies and themes.

#### Acceptance Criteria
- THE system SHALL allow unique custom tags.
- THE system SHALL allow assigning multiple tags to portfolio stocks, watchlist stocks, transactions, and ideas.
- THE system SHALL show performance by tag including cost, market value, unrealized P/L, realized P/L, dividends, and ROI.
- THE system SHALL allow tag deletion and reassignment.

### Requirement 26: Investment Thesis Board

**User Story:** As an investor, I want to track investment ideas like a research pipeline, so that I can make better buy/sell decisions.

#### Acceptance Criteria
- THE system SHALL support idea fields: Symbol, Title, Thesis, Bull Case, Bear Case, Target Entry, Target Exit, Risk Level, Source/Link, Status, Confidence Score, Expected Timeline, Catalyst Date, and Review Date.
- THE system SHALL support statuses: Researching, Watching, Near Entry, Bought, Passed, Closed.
- THE Investment Ideas page SHALL support Board, List, and Calendar views.
- WHEN status changes to Bought, THE system SHALL allow linking the idea to a transaction.
- THE system SHALL show ideas near target entry price.

### Requirement 27: Thesis Break Monitoring

**User Story:** As an investor, I want to define what would invalidate my thesis, so that I know when to review or exit a position.

#### Acceptance Criteria
- THE system SHALL allow users to define Thesis Break Conditions for each portfolio position or idea.
- THE system SHALL track Review Date and show overdue thesis reviews.
- THE system SHALL trigger alerts when price, drawdown, time, or user-defined conditions require thesis review.
- THE AI Weekly Memo SHALL include thesis review warnings.

### Requirement 28: Sector Heatmap

**User Story:** As an investor, I want a visual sector heatmap, so that I can see allocation and performance quickly.

#### Acceptance Criteria
- THE heatmap SHALL display sectors sized by allocation and colored by performance.
- THE heatmap SHALL support drill-down into sector positions.
- THE heatmap SHALL update after market data refresh and transaction changes.
- THE heatmap SHALL support dark mode colors optimized for investor dashboards.

### Requirement 29: Stock Screener

**User Story:** As an investor, I want a premium stock screener, so that I can discover opportunities using financial filters and strategy presets.

#### Acceptance Criteria
- THE Stock Screener SHALL support filters for P/E range, Dividend Yield, Market Cap, Sector, Industry, Beta, Price to Book, 52-week range, Volume, and custom preset strategy.
- THE Stock Screener SHALL only return stocks that are tradeable on major US exchanges (NYSE, NASDAQ, AMEX). OTC stocks, pink sheet stocks, preferred shares, warrants, and other non-tradeable or illiquid instruments SHALL be excluded from results.
- THE system SHALL filter results by exchange code (NMS, NYQ, NGM, NCM, ASE, PCX) and quote type (EQUITY only) to ensure only common stocks listed on major exchanges appear.
- THE page SHALL use a professional layout with compact filters, quick strategy chips, result summary cards, AI Insight Card, and premium data table.
- THE system SHALL provide quick strategy chips such as High Dividend, Low P/E, Mega Cap, Tech Growth, Value Banks, Near 52-Week Low, and High Quality.
- THE result summary SHALL show Result Count, Median P/E, Highest Dividend Yield, Top Sector, and Data Warning Count.
- THE table SHALL include sticky header, sortable columns, badges, row actions, and pagination.
- Row actions SHALL include Add to Watchlist, Set Alert, Create Thesis, View Details, and Simulate.
- THE system SHALL warn when screener results contain suspicious or incomplete data.
- THE system SHALL allow saving, loading, editing, deleting, and sharing screener presets.
- THE Stock Screener SHALL support an MVP implementation using cached provider data and/or internally normalized fundamentals from SEC EDGAR.
- THE system SHALL clearly label screener results as delayed, incomplete, cached, or provider-limited when using free data sources.
- THE system SHALL allow screeners to run against a local normalized stock universe to reduce external API calls.
- THE system SHALL support provider-based screener adapters where available, but SHALL NOT make provider-specific API shape part of the frontend contract.

### Requirement 30: Scenario Simulator

**User Story:** As an investor, I want to simulate portfolio changes before acting, so that I understand potential outcomes.

#### Acceptance Criteria
- THE simulator SHALL model price changes, buy/sell actions, new cash deposit, FX rate change, dividend change, and rebalancing actions.
- THE simulator SHALL show impact on Total Portfolio Value, P/L, Allocation, Beta, Cash, Concentration, and Health Score.
- THE simulator SHALL allow users to compare Current Portfolio vs Simulated Portfolio.
- THE simulator SHALL not modify real portfolio data unless the user explicitly creates transactions from the simulation.

### Requirement 31: AI Weekly Portfolio Memo

**User Story:** As an investor, I want a weekly memo, so that I can quickly understand portfolio performance, risks, and next actions.

#### Acceptance Criteria
- THE system SHALL generate a weekly portfolio memo summarizing performance, contributors, detractors, risk alerts, watchlist opportunities, thesis review reminders, and recommended actions.
- THE memo SHALL use portfolio data, market data, performance history, journal notes, alerts, and thesis board data.
- THE memo SHALL clearly state when data is incomplete or stale.
- THE user SHALL be able to view historical memos.
- THE system SHALL allow enabling or disabling email delivery of weekly memo.
- THE AI Weekly Memo SHALL support four modes: Disabled, Rule-Based Template, Local LLM, and Hosted LLM API.
- THE MVP SHALL provide rule-based weekly memo generation without requiring a paid AI API.
- THE system SHALL store generated memos and SHALL avoid regenerating them unnecessarily to reduce AI cost.

### Requirement 32: AI Trade Review

**User Story:** As an investor, I want AI to review completed trades, so that I can learn from outcomes.

#### Acceptance Criteria
- WHEN a position is partially or fully sold, THE system SHALL generate a trade review using realized P/L, holding period, original note, tags, thesis, and market context.
- THE review SHALL summarize whether the original thesis was followed, whether exit timing matched plan, and what patterns were observed.
- THE review SHALL be stored with the trade journal.
- THE system SHALL avoid guaranteeing future performance or giving personalized financial advice beyond analytical insights.
- THE AI Trade Review SHALL support rule-based review generation when no hosted AI provider is configured.
- THE system SHALL clearly disclose whether each review was generated by rules, local LLM, or hosted LLM.

### Requirement 33: One-click Portfolio Review

**User Story:** As an investor, I want a one-click portfolio review, so that I can get a complete overview without manually checking every page.

#### Acceptance Criteria
- THE system SHALL provide a Review Portfolio button on Dashboard.
- THE review SHALL include Performance, Benchmark, Attribution, Contributors, Detractors, Concentration, Risk, Cash, Watchlist, Thesis Status, Alerts, and Suggested Next Actions.
- THE review SHALL be exportable as PDF or Markdown.

### Requirement 34: Import and Export

**User Story:** As an investor, I want to import and export data, so that migration, backup, and reporting are easy.

#### Acceptance Criteria
- THE system SHALL support importing transactions, transfers, dividends, watchlist, ideas, and snapshots from CSV.
- THE system SHALL validate imported files and preview changes before commit.
- THE system SHALL support exporting Trading Log, Portfolio Summary, Cash Ledger, Dividend Records, Realized P/L, Performance History, Watchlist, Investment Ideas, and Full Account Backup.
- THE system SHALL support JSON backup and restore for the authenticated user's data.

### Requirement 35: Application Navigation

**User Story:** As an investor, I want clear navigation, so that I can access all major features quickly.

#### Acceptance Criteria
- THE Navigation_Menu SHALL be persistent, collapsible, and responsive.
- THE sidebar SHALL use Lucide-style line icons instead of emoji icons.
- THE sidebar SHALL group pages into Portfolio, Markets, Research, Tools, Reports, and Settings.
- THE active page SHALL be clearly highlighted.
- THE sidebar SHALL show user profile, logout, theme toggle, and optional collapsed icon-only mode.
- THE Admin link SHALL be visible only to admin users.

### Requirement 36: Premium Dark Trading Dashboard UI Theme

**User Story:** As a user, I want the application to look premium and professional, so that I enjoy using it and trust the experience.

#### Acceptance Criteria
- THE system SHALL provide Dark Trading Dashboard Mode as the preferred visual style.
- THE UI SHALL use a dark navy/black background, elevated dark cards, subtle borders, electric blue primary accents, green positive indicators, red negative indicators, and amber warnings.
- THE system SHALL support light mode as an option.
- THE UI SHALL use Inter or Geist font.
- THE UI SHALL use professional iconography and avoid casual emoji icons in the main navigation.
- THE UI SHALL have consistent spacing, card radius, typography, chart styling, button hierarchy, and table density.
- THE UI SHALL include smooth hover states, focus states, loading skeletons, empty states, and error states.
- ALL data tables SHALL use `table-layout: fixed` with consistent column widths to ensure header and body columns are perfectly aligned across all pages.
- ALL numeric columns in data tables (quantities, prices, amounts, percentages, ratios) SHALL be right-aligned in both header and body cells using `text-align: right` and `font-variant-numeric: tabular-nums`.
- ALL data tables with more than a handful of rows SHALL include client-side pagination with configurable items per page (10, 20, 50, 100), Previous/Next navigation buttons, page number buttons, and "Showing X to Y of Z entries" status text.

#### Design Tokens

```text
Dark Mode:
Background: #020617
Surface: #0F172A
Surface Elevated: #111827
Border: #1E293B
Text Primary: #F8FAFC
Text Secondary: #94A3B8
Primary: #3B82F6
Positive: #22C55E
Negative: #EF4444
Warning: #F59E0B
Info: #38BDF8

Light Mode:
Background: #F6F8FB
Surface: #FFFFFF
Border: #E2E8F0
Text Primary: #0F172A
Text Secondary: #64748B
Primary: #0052FF
Positive: #16A34A
Negative: #DC2626
Warning: #F59E0B
Info: #2563EB

Typography:
Font: Inter or Geist
Page Title: 28px to 32px, weight 700
Section Title: 18px, weight 600
Metric Value: 24px to 32px, weight 700
Table Text: 13px to 14px
Label: 12px uppercase, weight 600

Radius:
Card: 16px
Button: 10px to 12px
Input: 10px
Badge: 999px
```

### Requirement 37: Responsive and Mobile Experience

**User Story:** As a user, I want to use the system on desktop, tablet, and mobile, so that I can check my portfolio anywhere.

#### Acceptance Criteria
- THE system SHALL provide responsive layouts for desktop, tablet, and mobile.
- On mobile, THE sidebar SHALL collapse into bottom navigation or drawer navigation.
- Mobile dashboard SHALL prioritize Portfolio Value, Daily Change, Alerts, Watchlist Near Target, and Action Needed.
- Wide tables SHALL transform into card rows or horizontally scrollable tables on small screens.
- Critical actions SHALL remain reachable within one or two taps.

### Requirement 38: Sortable and Professional Data Tables

**User Story:** As an investor, I want tables to be easy to scan, sort, and act on, so that I can work efficiently with financial data.

#### Acceptance Criteria
- All major tables SHALL support sortable headers, sticky headers, pagination, column visibility, density toggle, and row actions.
- Numeric columns SHALL align right.
- Positive and negative values SHALL be color-coded consistently.
- Symbols, sectors, strategies, and statuses SHALL use badges.
- Tables SHALL support loading skeletons, empty state, error state, and export action where applicable.

### Requirement 39: User Authentication and Session Management

**User Story:** As a user, I want secure login using Google or Facebook, so that I can access the system without a separate password.

#### Acceptance Criteria
- THE system SHALL support Google OAuth and Facebook OAuth.
- THE system SHALL create a secure session after successful authentication.
- THE system SHALL maintain session through secure HTTP-only cookies or equivalent tokens.
- THE system SHALL redirect unauthenticated users to the login page.
- THE system SHALL handle OAuth failure gracefully.

### Requirement 40: Admin User Management and Approval

**User Story:** As the site owner, I want to approve or block users, so that only trusted users can access the platform.

#### Acceptance Criteria
- THE first registered user SHALL become Admin by default.
- New users SHALL be Pending until approved by Admin.
- Admin SHALL be able to approve, block, or revert users to pending.
- Blocked users SHALL be denied access.
- Non-admin users SHALL NOT access the Admin panel.

### Requirement 41: Per-User Data Isolation

**User Story:** As a user, I want my investment data to be private, so that no other user can see or modify my records.

#### Acceptance Criteria
- All transactions, transfers, settings, watchlists, ideas, alerts, snapshots, dividends, and reports SHALL be associated with the authenticated user.
- Users SHALL only access their own investment data.
- Attempted access to another user's resource SHALL return access denied without revealing resource details.
- Shared public market data caches MAY be used across users.

### Requirement 42: Reports

**User Story:** As an investor, I want professional reports, so that I can review and share investment performance.

#### Acceptance Criteria
- THE system SHALL provide reports for Portfolio Summary, Performance, Realized P/L, Dividend Income, Cash Ledger, Tax Lots, Benchmark Comparison, and AI Portfolio Review.
- Reports SHALL be exportable as PDF, CSV, and Markdown where applicable.
- Reports SHALL include date range filters and generated timestamp.

### Requirement 43: Deployment and Infrastructure

**User Story:** As a developer/operator, I want the application to be deployable reliably, so that it can run in production.

#### Acceptance Criteria
- THE system SHALL provide Docker Compose configuration with PostgreSQL, Redis, Backend, and Frontend services.
- Backend SHALL use FastAPI and Python 3.12 or newer.
- Frontend SHALL use React with a production web server such as nginx.
- THE system SHALL document Azure Container Apps and Azure App Service deployment options.
- THE system SHALL support environment variables for database, Redis, SMTP, OAuth, secrets, and market data settings.
- THE system SHALL support environment variables for provider selection, fallback order, provider API keys, provider rate limits, cache TTLs, and AI provider mode.
- THE system SHALL allow deployment with AI_PROVIDER=disabled and MARKET_DATA_PROVIDER configured to a free-tier provider for MVP.
- THE system SHALL support database migrations and backup procedures.

### Requirement 44: Non-Functional Requirements

**User Story:** As a user, I want the system to be fast, reliable, and secure, so that I can trust it with my investment records.

#### Acceptance Criteria
- THE Dashboard SHALL load primary portfolio metrics within an acceptable interactive timeframe under normal data volume.
- THE system SHALL cache market data to reduce external API calls.
- THE system SHALL validate all user input on both frontend and backend.
- THE system SHALL log important errors without exposing sensitive data to users.
- THE system SHALL protect against unauthorized access, CSRF, XSS, and common web vulnerabilities.
- THE system SHALL maintain audit history for destructive or financially significant edits.

### Requirement 45: AI Safety and Disclosure

**User Story:** As a user, I want AI insights to be useful but transparent, so that I understand they are analytical support and not guaranteed investment advice.

#### Acceptance Criteria
- AI-generated content SHALL clearly indicate when it is based on incomplete or stale data.
- AI-generated insights SHALL avoid guaranteeing future returns.
- AI-generated recommendations SHALL be framed as analytical observations or suggested review items, not instructions to buy or sell.
- THE user SHALL be able to disable AI insights in settings.
- THE system SHALL not expose one user's data to another user through AI outputs.


### Requirement 46: External API Provider Management

**User Story:** As a developer/operator, I want external API providers to be configurable, cached, and replaceable, so that the system can start with free APIs and upgrade to paid providers without redesigning the product.

#### Acceptance Criteria
- THE system SHALL define provider adapters for Market Data, Fundamentals, FX Rates, Email Notifications, and AI Insights.
- THE system SHALL expose stable internal service interfaces independent of vendor-specific response formats.
- THE system SHALL support provider priority order, fallback behavior, timeout settings, retry policy, and circuit breaker state.
- THE system SHALL track provider usage counts, success rate, failure rate, cache hit rate, and last error message.
- THE system SHALL prevent excessive external API usage through server-side rate limiting and scheduled batch refresh.
- THE system SHALL allow individual provider features to be disabled through environment variables.
- THE system SHALL display provider data freshness and data source labels where the user depends on external data.
- THE system SHALL maintain a provider compatibility matrix documenting which providers support price, historical price, fundamentals, dividend, FX, screener, trending, earnings, news, and AI features.
- THE system SHALL never expose API keys, OAuth secrets, SMTP passwords, or provider tokens to the frontend.

### Requirement 47: MVP Degradation and Free-Tier Operating Mode

**User Story:** As a product owner, I want the application to remain useful even when free API limits are reached, so that users can continue managing their portfolio without paid data subscriptions.

#### Acceptance Criteria
- THE system SHALL support a Free-Tier MVP Mode.
- In Free-Tier MVP Mode, THE system SHALL prioritize internal accounting features over external market-data features.
- THE system SHALL allow portfolio tracking, trading logs, transfers, cash ledger, realized P/L, tax lots, journal, watchlist, ideas, manual dividends, manual FX, reports, and admin workflows without external market-data availability.
- THE system SHALL show cached or manually entered market data when external providers are unavailable.
- THE system SHALL show clear degraded-state UI messages for unavailable data such as real-time prices, earnings calendar, trending stocks, complete screener data, and hosted AI insights.
- THE system SHALL avoid blocking page load solely because an external provider fails.
- THE system SHALL provide action guidance such as Retry Later, Use Cached Data, Add Manual Price, Configure Provider, or Upgrade Provider.
- THE system SHALL record data quality impact when free-tier limitations reduce completeness or freshness.


### Requirement 48: Advanced Stock Screener with Multi-Provider Intelligence

**User Story:** As a serious investor, I want an advanced stock screener that combines data from multiple market data providers and offers intelligent strategy presets, so that I can discover high-quality investment opportunities with deep fundamental analysis.

#### Acceptance Criteria

##### Multi-Provider Data Strategy
- THE system SHALL use FMP (Financial Modeling Prep) as the primary screener engine for bulk filtering by Sector, Market Cap, Beta, P/E, Dividend Yield, and other fundamental criteria via server-side API queries.
- THE system SHALL use EODHD for technical market signals including 50-day and 200-day New High/New Low detection, volume anomalies, and Wall Street consensus signals.
- THE system SHALL use Alpha Vantage for cross-checking company financial ratios (Company Overview endpoint) on a limited basis due to tight free-tier quotas.
- THE system SHALL use Twelve Data for real-time price verification of stocks that pass fundamental screening criteria.
- THE system SHALL use yfinance as a fallback and for historical financials data to calculate growth rates and additional ratios not available from other providers.
- THE system SHALL implement a provider priority chain with automatic fallback: FMP → EODHD → Alpha Vantage → Twelve Data → yfinance.
- THE system SHALL cache all provider responses in Redis with appropriate TTLs to minimize API usage.
- THE system SHALL track API quota usage per provider and display remaining quota warnings to the user.

##### Strategy Presets (System + Custom)
- THE system SHALL provide the following built-in strategy presets that auto-populate filter values:
  - **GARP (Growth At Reasonable Price):** PEG 0.5-1.5, P/E 10-25, EPS Growth > 15%, Revenue Growth > 10%
  - **Deep Value:** P/E < 12, P/B < 1.5, Dividend Yield > 3%, Debt/Equity < 0.5
  - **Turnaround (หุ้นฟื้นตัว):** EPS Growth > 5%, Net Income > 0 (พลิกกำไร), Price > 50-Day MA, not in 200d New Low zone (EODHD signal)
  - **Cash Cow (หุ้นผลิตเงินสด):** Dividend Yield > 4.5%, Free Cash Flow > 0, Debt/Equity < 0.8, P/E < 15
  - **Wall Street Consensus (นักวิเคราะห์เชียร์):** Current Price < Analyst Target Price by at least 20%, uses wallstreet_hi signal from EODHD
  - **High Dividend:** Dividend Yield > 3%, Payout Ratio < 80%
  - **Low P/E Value:** P/E 5-15, Market Cap > 1B
  - **Mega Cap Growth:** Market Cap > 100B, Revenue Growth > 10%
- WHEN a user selects a preset, THE system SHALL immediately populate all corresponding filter Min/Max values into the active filter fields visually on screen, allowing the user to further adjust.
- THE system SHALL allow users to save their custom filter combinations as named presets.

##### Dynamic Filter UI
- THE system SHALL NOT display all filter inputs at once. Instead, it SHALL provide an [+ Add Filter] button that opens a dropdown of available metrics.
- WHEN the user selects a metric from the dropdown, THE system SHALL add that specific filter input to the active filter panel.
- Each numeric filter SHALL provide BOTH a range slider (for quick adjustment) AND text input fields (for precise values), synchronized bidirectionally.
- THE system SHALL allow removing individual filters with a close/remove button per filter.
- Active preset tags SHALL be displayed above the filters showing which preset is active and its criteria.

##### Available Filter Metrics
- P/E Ratio (Trailing, Forward)
- PEG Ratio
- Price/Book
- Price/Sales
- EV/EBITDA
- Dividend Yield
- Market Cap
- Beta
- Revenue Growth (YoY)
- EPS Growth (YoY)
- Net Income Margin
- ROE (Return on Equity)
- ROA (Return on Assets)
- Debt/Equity Ratio
- Free Cash Flow
- Current Ratio
- Sector
- Industry
- Country/Region

##### Results Display
- THE system SHALL return up to 100 results per query.
- Results SHALL display: Symbol (link to stockanalysis.com), Company Name, Sector, Price, P/E, PEG, Div Yield, Market Cap, P/B, Beta, and a "Data Source" indicator showing which provider supplied the data.
- THE system SHALL show a provider status bar indicating which APIs were consulted and their response status (success/cached/fallback/failed).
- THE system SHALL filter results to only tradeable stocks on major US exchanges (NYSE, NASDAQ, AMEX).
