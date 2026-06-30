# Requirements Document

## Introduction

The Investment History feature is a comprehensive stock trading tracker that allows investors to record daily buy/sell transactions, track simple money transfers (deposits/withdrawals) to/from broker accounts, bulk-import existing positions via snapshots, view an aggregated portfolio summary with market data, monitor historical performance over time, and access a dashboard providing a high-level overview of their entire investment activity. Beyond core trading and portfolio management, the system provides advanced capabilities including trade journaling with notes and tags for decision review, price alerts and target notifications, dividend income tracking and projection, automated realized P/L calculation, portfolio rebalancing insights against target allocations, risk metrics and concentration analysis, a watchlist for monitoring prospective investments, trending and popular stock discovery, custom stock tags and categories for portfolio organization, an investment thesis board for research pipeline management, a sector heatmap for visual performance analysis, and a stock screener for discovering opportunities based on financial criteria. The system requires user authentication via Google or Facebook OAuth, with an admin approval workflow ensuring only authorized users can access the platform. Each user's investment data is fully isolated and private. The application provides a complete navigation menu with nine main pages: Dashboard, Trading Log, Money Transfers, Portfolio Summary, Performance History, Trade Journal, Watchlist, Investment Ideas, and Admin (admin-only). All monetary values are displayed in USD ($), except for the Money Transfers page which uses THB (฿). The system tracks brokerage fees (0.15% of gross value) and VAT (7% of brokerage fee) as manually entered values.

## Glossary

- **Trading_Log**: The system component responsible for recording and managing daily stock trading transactions (buys, sells, and snapshot imports)
- **Money_Transfer_Tracker**: The system component responsible for recording deposits and withdrawals to/from broker accounts
- **Portfolio_Summary**: The system component responsible for calculating and displaying aggregated per-stock position data including market data, unrealized P/L, and allocation
- **Dashboard**: The system component responsible for displaying a high-level overview of the user's entire investment portfolio, aggregating data from all other components
- **Performance_Tracker**: The system component responsible for recording and displaying historical portfolio value and returns over time
- **Navigation_Menu**: The system component responsible for providing access to all pages/sections of the application
- **Transaction**: A single trading action (Buy or Sell) for a specific stock on a specific date
- **Snapshot**: A bulk import entry representing an existing stock position imported into the system, marked with a "(Snapshot)" date label
- **Stock_Symbol**: The ticker symbol identifying a traded stock (e.g., "DRAM", "RGNX", "META")
- **Broker**: The brokerage platform used for a transaction (e.g., "Webull", "Dime")
- **Gross_Value**: The product of Quantity multiplied by Price per Share
- **Brokerage_Fee**: A fee equal to 0.15% of Gross Value, manually entered by the user
- **VAT**: Value Added Tax equal to 7% of the Brokerage Fee, manually entered by the user
- **Net_Capital_Flow**: For buys: Gross Value + Brokerage Fee + VAT; For sells: Gross Value - Brokerage Fee - VAT
- **Transfer_Type**: The direction of a money transfer, either "In" (deposit) or "Out" (withdrawal)
- **Email_Alert_Notification**: An automated email sent to the user's registered email address when a price alert triggers, containing alert details in HTML format
- **Sortable_Table_Header**: A clickable column header that cycles through Ascending (▲), Descending (▼), and No sort states
- **Avg_Cost**: The weighted average cost per share across all buy transactions for a given stock
- **Unrealized_PL**: Market Value minus Total Cost for a currently held position
- **ROI_Percent**: Unrealized P/L divided by Total Cost, multiplied by 100
- **Allocation**: Total Cost of a position divided by the sum of all positions' Total Costs, expressed as a percentage
- **Total_Invested**: The sum of all "In" transfer amounts across all brokers
- **Total_Withdrawn**: The sum of all "Out" transfer amounts across all brokers
- **Net_Invested**: Total "In" minus Total "Out" transfer amounts
- **Overall_PL**: Total current Market Value of all positions minus Total Cost of all positions
- **Portfolio_Value_Snapshot**: A point-in-time record of total portfolio market value on a specific date, used for historical performance tracking
- **Period_Return**: The percentage change in portfolio value between two dates, calculated as (End Value minus Start Value) divided by Start Value multiplied by 100
- **Beta**: A measure of a stock's volatility relative to the overall market, auto-fetched from Yahoo Finance
- **Dividend_Yield**: Annual dividend payment divided by the stock price, expressed as a percentage, auto-fetched from Yahoo Finance
- **Price_to_Book**: Market price per share divided by book value per share, auto-fetched from Yahoo Finance
- **Market_Data_Service**: The system component responsible for fetching real-time stock market data from Yahoo Finance (yfinance) including all available Ticker.info fields such as current price, company name, sector, industry, market cap, P/E ratios, 52-week range, beta, dividend yield, price to book, and average volume
- **Trade_Journal**: The system component for attaching notes, reasoning, and tags to transactions
- **Price_Alert**: A user-configured notification trigger when a stock's price crosses a specified threshold
- **Dividend_Record**: A record of dividend income received from a specific stock on a specific date
- **Realized_PL**: The actual profit or loss crystallized when shares are sold, calculated as (Sell Price - Avg Cost) × Quantity
- **Watchlist**: A collection of stocks the user is monitoring but has not yet purchased
- **Investment_Idea**: A structured research card tracking a potential investment from initial interest through to execution or rejection
- **Sector_Heatmap**: A visual representation of portfolio sectors colored by performance and sized by allocation
- **Stock_Screener**: A tool for filtering and discovering stocks based on financial criteria
- **OAuth**: Open Authorization protocol used to authenticate users via third-party providers (Google, Facebook) without handling passwords directly
- **Admin**: The site owner with elevated privileges to approve, block, or manage user accounts via the Admin panel
- **User_Status**: The access state of a registered user, one of "Approved" (full access), "Pending" (awaiting admin approval), or "Blocked" (access revoked)
- **Session**: A secure authenticated connection between the user's browser and the application, maintained via tokens after successful OAuth login

## Requirements

### Requirement 1: Record Daily Trading Transactions

**User Story:** As an investor, I want to record my daily buy and sell stock transactions with broker and fee details, so that I have a complete and accurate trading log.

#### Acceptance Criteria

1. WHEN a user submits a buy transaction, THE Trading_Log SHALL store the Date (in YYYY-MM-DD format), Stock Symbol (1 to 20 uppercase alphanumeric characters), Action as "Buy", Quantity (integer greater than zero and no greater than 99,999,999), Price per Share (greater than zero and no greater than 99,999,999.99 in USD), Gross Value (Quantity multiplied by Price per Share), Brokerage Fee (manually entered, greater than or equal to zero, expected to be 0.15% of Gross Value), VAT (manually entered, greater than or equal to zero, expected to be 7% of Brokerage Fee), Net Capital Flow (Gross Value + Brokerage Fee + VAT), and Broker name (1 to 100 characters)
2. WHEN a user submits a sell transaction, THE Trading_Log SHALL store the Date (in YYYY-MM-DD format), Stock Symbol (1 to 20 uppercase alphanumeric characters), Action as "Sell", Quantity (integer greater than zero and no greater than 99,999,999), Price per Share (greater than zero and no greater than 99,999,999.99 in USD), Gross Value (Quantity multiplied by Price per Share), Brokerage Fee (manually entered, greater than or equal to zero), VAT (manually entered, greater than or equal to zero), Net Capital Flow (Gross Value - Brokerage Fee - VAT), and Broker name (1 to 100 characters)
3. WHEN a user enters Quantity and Price per Share, THE Trading_Log SHALL automatically calculate Gross Value as Quantity multiplied by Price per Share
4. IF a required field (Date, Stock Symbol, Action, Quantity, Price per Share, or Broker name) is missing from a transaction submission, THEN THE Trading_Log SHALL reject the transaction and return an error message indicating which specific field is missing
5. IF the Quantity or Price per Share is zero or negative, THEN THE Trading_Log SHALL reject the transaction and return a validation error indicating the value must be greater than zero
6. IF a user submits a sell transaction and the sell Quantity exceeds the total owned quantity of that Stock Symbol (calculated as total bought plus snapshot quantities minus total sold), THEN THE Trading_Log SHALL reject the transaction and return an error indicating insufficient holdings
7. IF the Date field does not conform to YYYY-MM-DD format or represents a future date beyond the current calendar date, THEN THE Trading_Log SHALL reject the transaction and return a validation error indicating the date is invalid
8. IF the Brokerage Fee or VAT is negative, THEN THE Trading_Log SHALL reject the transaction and return a validation error indicating the fee value must be zero or greater

### Requirement 2: Bulk Import Existing Positions via Snapshot

**User Story:** As an investor with existing holdings, I want to bulk-import my current positions as snapshot entries, so that I can start using the system without manually entering every historical transaction.

#### Acceptance Criteria

1. WHEN a user submits a snapshot import, THE Trading_Log SHALL store each entry with a Date labeled as "(Snapshot)", Stock Symbol (1 to 20 characters), Action as "Snapshot", Quantity (greater than zero), Price per Share (average cost, greater than zero in USD), and Broker name
2. WHEN snapshot entries are imported, THE Trading_Log SHALL include the snapshot quantities in the total holdings calculation for each Stock Symbol
3. WHEN displaying transaction history, THE Trading_Log SHALL visually distinguish snapshot entries from regular buy/sell transactions by showing the "(Snapshot)" date label
4. IF a snapshot import contains an entry with zero or negative Quantity or zero or negative Price per Share, THEN THE Trading_Log SHALL reject that entry and return a validation error indicating which field is invalid
5. IF a snapshot import contains multiple entries and one or more entries fail validation, THEN THE Trading_Log SHALL reject the entire import and return validation errors identifying each invalid entry
6. IF a required field (Stock Symbol, Quantity, Price per Share, or Broker name) is missing from a snapshot entry, THEN THE Trading_Log SHALL reject that entry and return an error message indicating which specific field is missing

### Requirement 3: Track Money Transfers

**User Story:** As an investor, I want to manually record simple deposits and withdrawals to broker accounts, so that I can monitor my capital flow across brokers.

#### Acceptance Criteria

1. WHEN a user records a money transfer, THE Money_Transfer_Tracker SHALL store exactly four fields: Date (in YYYY-MM-DD format, not in the future), Broker name (1 to 100 characters, not blank), Transfer Type ("In" or "Out"), and Amount in THB (from 0.01 to 999,999,999.99, up to 2 decimal places). Note: The Money Transfers page is the only page that uses THB (฿) as currency; all other pages use USD ($).
2. WHEN a user requests the transfer history, THE Money_Transfer_Tracker SHALL return all transfer records sorted by date in descending order, returning an empty list if no records exist
3. WHERE a Broker filter is specified, THE Money_Transfer_Tracker SHALL return only transfers matching the specified Broker name using case-insensitive matching
4. IF the Amount is less than 0.01 or greater than 999,999,999.99 or has more than 2 decimal places, THEN THE Money_Transfer_Tracker SHALL reject the transfer record and return a validation error indicating the amount must be between 0.01 and 999,999,999.99 with up to 2 decimal places
5. IF the Transfer Type is not "In" or "Out", THEN THE Money_Transfer_Tracker SHALL reject the transfer record and return a validation error indicating an invalid transfer type
6. IF the Date is not in YYYY-MM-DD format or is a future date, THEN THE Money_Transfer_Tracker SHALL reject the transfer record and return a validation error indicating the date must be a valid date not in the future
7. IF the Broker name is empty or contains only whitespace, THEN THE Money_Transfer_Tracker SHALL reject the transfer record and return a validation error indicating the broker name is required

### Requirement 4: View Trading Log History

**User Story:** As an investor, I want to view my complete trading log, so that I can review past transactions and understand my trading activity.

#### Acceptance Criteria

1. WHEN a user requests the trading log, THE Trading_Log SHALL return all recorded transactions (buys, sells, and snapshots) sorted by Date in descending order, displaying Date, Stock Symbol, Action, Quantity, Price per Share, Gross Value, Brokerage Fee, VAT, Net Capital Flow, and Broker
2. WHERE a date range filter is specified, THE Trading_Log SHALL return only transactions with a Date on or after the start date and on or before the end date (inclusive)
3. WHERE a Stock Symbol filter is specified, THE Trading_Log SHALL return only transactions matching the specified Stock Symbol using case-insensitive exact matching
4. WHERE a Broker filter is specified, THE Trading_Log SHALL return only transactions associated with the specified Broker name using case-insensitive exact matching
5. WHERE an Action filter is specified (Buy, Sell, or Snapshot), THE Trading_Log SHALL return only transactions matching the specified Action type
6. WHERE multiple filters are specified simultaneously, THE Trading_Log SHALL combine all active filters using AND logic, returning only transactions that satisfy every specified filter
7. IF filters are applied and no transactions match, THEN THE Trading_Log SHALL return an empty list with no error
8. IF a date range filter is specified and the start date is after the end date, THEN THE Trading_Log SHALL return a validation error indicating the start date must be on or before the end date
9. IF an Action filter value is specified that is not one of "Buy", "Sell", or "Snapshot", THEN THE Trading_Log SHALL return a validation error indicating the invalid action type

### Requirement 5: View Portfolio Summary

**User Story:** As an investor, I want to see an aggregated portfolio summary on a separate page, so that I can evaluate my current positions, market performance, and allocation at a glance.

#### Acceptance Criteria

1. WHEN a user navigates to the Portfolio Summary page, THE Portfolio_Summary SHALL display each currently held stock with the following fields grouped by source: (a) Calculated from trading data: Stock Symbol (Ticker), Quantity, Avg Cost (in USD to 2 decimal places), Total Cost (Quantity multiplied by Avg Cost, in USD to 2 decimal places), Market Value (Quantity multiplied by Current Price, in USD to 2 decimal places), Unrealized P/L (Market Value minus Total Cost, in USD to 2 decimal places), ROI Percent (Unrealized P/L divided by Total Cost multiplied by 100, to 2 decimal places), and Allocation percentage (Total Cost divided by sum of all Total Costs, to 2 decimal places); (b) Auto-fetched from Yahoo Finance (yfinance Ticker.info): Company Name (longName), Sector (sector), Industry (industry), Current Price (currentPrice or regularMarketPrice), Previous Close (previousClose), Day High (dayHigh), Day Low (dayLow), 52-Week Low (fiftyTwoWeekLow), 52-Week High (fiftyTwoWeekHigh), Market Cap (marketCap), P/E Ratio Trailing (trailingPE), P/E Ratio Forward (forwardPE), Average Volume (averageVolume), Beta (beta), Dividend Yield (dividendYield), and Price to Book (priceToBook); (c) Manually entered by user: Sentiment (Bear or Bull, personal assessment only)
2. WHEN calculating Avg Cost for a stock, THE Portfolio_Summary SHALL compute the weighted average cost as the sum of (Quantity multiplied by Price per Share) across all buy transactions and snapshot entries for that Stock Symbol, divided by the total Quantity from those entries
3. WHEN calculating Allocation for a stock, THE Portfolio_Summary SHALL divide that stock's Total Cost by the sum of all stocks' Total Costs and express the result as a percentage
4. THE Portfolio_Summary SHALL display a Total Summary row showing aggregate Total Cost (sum of all positions' Total Cost), aggregate Market Value (sum of all positions' Market Value), aggregate Unrealized P/L (aggregate Market Value minus aggregate Total Cost), and overall ROI Percent (aggregate Unrealized P/L divided by aggregate Total Cost multiplied by 100)
5. IF a stock's total held Quantity equals zero, THEN THE Portfolio_Summary SHALL exclude that stock from the summary display
6. WHEN market data is refreshed from Yahoo Finance, THE Portfolio_Summary SHALL recalculate Market Value, Unrealized P/L, ROI Percent, and Allocation accordingly
7. THE Portfolio_Summary SHALL allow the user to manually enter or update Sentiment (Bear or Bull) for each stock, which is the only field requiring manual input
8. IF market data has not been fetched yet or the last fetch failed for a stock, THEN THE Portfolio_Summary SHALL display all auto-fetched fields as blank and SHALL display Market Value, Unrealized P/L, and ROI Percent as not available until Current Price is successfully fetched
9. IF no stocks are currently held (all positions have zero Quantity), THEN THE Portfolio_Summary SHALL display an empty state message indicating no positions are available
10. IF Sentiment has not been set for a stock, THEN THE Portfolio_Summary SHALL display the Sentiment field as unset until the user provides a value

### Requirement 6: Delete and Edit Transactions

**User Story:** As an investor, I want to correct or remove erroneous transactions, so that my trading log and portfolio remain accurate.

#### Acceptance Criteria

1. WHEN a user requests to delete a transaction, THE Trading_Log SHALL remove the specified transaction from the history and recalculate portfolio holdings (total held Quantity and Avg Cost per Stock Symbol) to reflect the removal
2. WHEN a user requests to edit a transaction, THE Trading_Log SHALL allow modification of Date, Stock Symbol, Action, Quantity, Price per Share, Brokerage Fee, VAT, and Broker, while preserving any fields not included in the edit request
3. IF deleting or editing a transaction would result in a negative holding quantity for any Stock Symbol, THEN THE Trading_Log SHALL reject the operation and return an error indicating which stock would have insufficient holdings
4. IF a user requests to delete or edit a transaction that does not exist, THEN THE Trading_Log SHALL return an error indicating that the specified transaction was not found
5. WHEN a transaction is successfully edited, THE Trading_Log SHALL recalculate Gross Value (Quantity multiplied by Price per Share), Net Capital Flow based on the Action type, and update portfolio holdings (total held Quantity and Avg Cost per affected Stock Symbol)
6. IF a user submits an edit with values that violate validation rules (Quantity zero or negative, Price per Share zero or negative, or a required field left empty), THEN THE Trading_Log SHALL reject the edit and return a validation error indicating which field is invalid

### Requirement 7: Delete and Edit Money Transfers

**User Story:** As an investor, I want to correct or remove erroneous transfer records, so that my capital flow tracking remains accurate.

#### Acceptance Criteria

1. WHEN a user requests to delete a money transfer record, THE Money_Transfer_Tracker SHALL remove the specified record from the transfer history
2. WHEN a user requests to edit a money transfer record, THE Money_Transfer_Tracker SHALL allow modification of Date, Broker name, Transfer Type, and Amount, while preserving any fields not included in the edit request
3. IF a user requests to delete or edit a transfer record that does not exist, THEN THE Money_Transfer_Tracker SHALL return an error indicating that the specified record was not found
4. IF an edited Amount is zero or negative, or an edited Transfer Type is not "In" or "Out", THEN THE Money_Transfer_Tracker SHALL reject the edit and return a validation error indicating the invalid field

### Requirement 8: Data Persistence and Integrity

**User Story:** As an investor, I want my trading data to be reliably stored, so that I do not lose my records.

#### Acceptance Criteria

1. THE Trading_Log SHALL persist all transaction data so it is available across application restarts without data loss
2. THE Money_Transfer_Tracker SHALL persist all transfer records so they are available across application restarts without data loss
3. WHEN a transaction is successfully recorded, THE Trading_Log SHALL display a confirmation message on-screen indicating the record has been saved, visible for at least 3 seconds or until dismissed by the user
4. WHEN a transfer is successfully recorded, THE Money_Transfer_Tracker SHALL display a confirmation message on-screen indicating the record has been saved, visible for at least 3 seconds or until dismissed by the user
5. IF a save operation fails in the Trading_Log, THEN THE Trading_Log SHALL display an error message indicating the failure reason and retain the unsaved data in memory until the user either retries the save successfully or explicitly discards the data
6. IF a save operation fails in the Money_Transfer_Tracker, THEN THE Money_Transfer_Tracker SHALL display an error message indicating the failure reason and retain the unsaved data in memory until the user either retries the save successfully or explicitly discards the data
7. THE Trading_Log SHALL assign a unique identifier to each transaction upon creation such that no two transactions share the same identifier within the system
8. THE Money_Transfer_Tracker SHALL assign a unique identifier to each transfer record upon creation such that no two records share the same identifier within the system

### Requirement 9: Dashboard / Overview Page

**User Story:** As an investor, I want a dashboard that provides a high-level summary of my entire investment activity, so that I can quickly understand my overall financial position without navigating to individual pages.

#### Acceptance Criteria

1. WHEN a user navigates to the Dashboard page, THE Dashboard SHALL display Total Invested (sum of all "In" transfer amounts across all brokers, in USD to 2 decimal places), Total Withdrawn (sum of all "Out" transfer amounts across all brokers, in USD to 2 decimal places), and Net Invested (Total Invested minus Total Withdrawn, in USD to 2 decimal places)
2. WHEN a user navigates to the Dashboard page, THE Dashboard SHALL display Total Current Market Value (sum of Quantity multiplied by Current Price for all held positions, in USD to 2 decimal places) and Overall P/L (Total Current Market Value minus Total Cost of all positions, in USD to 2 decimal places)
3. WHEN a user navigates to the Dashboard page, THE Dashboard SHALL display Overall ROI Percent (Overall P/L divided by Total Cost of all positions multiplied by 100, to 2 decimal places)
4. WHEN a user navigates to the Dashboard page, THE Dashboard SHALL display a Capital Deployed per Broker breakdown showing each Broker name and its net transfer balance (total "In" minus total "Out" for that broker, in USD to 2 decimal places)
5. WHEN a user navigates to the Dashboard page, THE Dashboard SHALL display the total number of currently held positions (stocks with Quantity greater than zero) and total number of distinct brokers with recorded transfers
6. IF no transactions or transfers have been recorded, THEN THE Dashboard SHALL display all monetary values as 0.00 and counts as 0
7. IF market data has not been fetched yet for one or more held positions, THEN THE Dashboard SHALL display Total Current Market Value and Overall P/L as not available, with a message indicating that market data is incomplete
8. WHEN underlying data changes (new transactions, transfers, edits, or deletions), THE Dashboard SHALL reflect the updated values the next time the user navigates to or refreshes the Dashboard page

### Requirement 10: Performance History

**User Story:** As an investor, I want to track my portfolio value and returns over time, so that I can understand how my investments have performed historically and identify trends.

#### Acceptance Criteria

1. WHEN a user manually records a portfolio value snapshot, THE Performance_Tracker SHALL store the Date (in YYYY-MM-DD format, not in the future), Total Portfolio Value in USD (from 0.00 to 999,999,999.99, up to 2 decimal places), and Total Cost at that date (sum of all positions' cost basis at that point, in USD to 2 decimal places)
2. WHEN a user views the Performance History page, THE Performance_Tracker SHALL display all recorded portfolio value snapshots sorted by Date in ascending order, showing Date, Total Portfolio Value, Total Cost, P/L (Portfolio Value minus Total Cost), and Period Return percentage
3. WHEN calculating Period Return between two consecutive snapshots, THE Performance_Tracker SHALL compute the percentage as (Current Snapshot Value minus Previous Snapshot Value) divided by Previous Snapshot Value multiplied by 100, to 2 decimal places
4. WHEN a user views the Performance History page, THE Performance_Tracker SHALL display a cumulative return from the earliest snapshot to the latest snapshot, calculated as (Latest Value minus Earliest Value) divided by Earliest Value multiplied by 100, to 2 decimal places
5. WHERE a date range filter is specified, THE Performance_Tracker SHALL return only snapshots with a Date on or after the start date and on or before the end date (inclusive)
6. WHERE a monthly aggregation view is selected, THE Performance_Tracker SHALL display one entry per month using the last recorded snapshot value of each month, showing month (YYYY-MM format), ending Portfolio Value, and monthly return percentage
7. WHERE a yearly aggregation view is selected, THE Performance_Tracker SHALL display one entry per year using the last recorded snapshot value of each year, showing year (YYYY format), ending Portfolio Value, and yearly return percentage
8. IF no portfolio value snapshots have been recorded, THEN THE Performance_Tracker SHALL display an empty state message indicating no performance data is available and prompt the user to record a snapshot
9. IF only one snapshot exists, THEN THE Performance_Tracker SHALL display the snapshot data with Period Return shown as not applicable (first entry)
10. IF a user requests to delete a portfolio value snapshot, THE Performance_Tracker SHALL remove the specified record and recalculate Period Returns for adjacent snapshots
11. IF a user requests to edit a portfolio value snapshot, THE Performance_Tracker SHALL allow modification of Date, Total Portfolio Value, and Total Cost, and recalculate Period Returns for adjacent snapshots
12. THE Performance_Tracker SHALL persist all portfolio value snapshots so they are available across application restarts without data loss
13. THE Performance_Tracker SHALL assign a unique identifier to each snapshot upon creation such that no two snapshots share the same identifier within the system

### Requirement 11: Application Navigation

**User Story:** As an investor, I want a complete navigation menu that gives me access to all pages of the system, so that I can easily find and access any information I need.

#### Acceptance Criteria

1. THE Navigation_Menu SHALL provide persistent navigation links to all main pages: Dashboard, Trading Log, Money Transfers, Portfolio Summary, Performance History, Trade Journal, Watchlist, and Investment Ideas
2. THE Navigation_Menu SHALL be visible on every page of the application without requiring scrolling to access it
3. WHEN a user clicks a navigation link, THE Navigation_Menu SHALL navigate the user to the selected page and visually indicate the currently active page
4. THE Navigation_Menu SHALL display page names in a clear and consistent order: Dashboard, Trading Log, Money Transfers, Portfolio Summary, Performance History, Trade Journal, Watchlist, Investment Ideas
5. IF the user is already on the selected page, THEN THE Navigation_Menu SHALL remain on the current page without reloading or losing any unsaved data in form fields
6. THE Navigation_Menu SHALL provide access to Trending Stocks, Sector Heatmap, Stock Screener, Portfolio Rebalancing, Price Alerts, Dividend Tracker, and Realized P/L as sub-sections or tabs within the relevant main pages
7. WHERE the authenticated user has Admin role, THE Navigation_Menu SHALL display an "Admin" navigation link leading to the Admin panel; this link SHALL be hidden for non-admin users
8. THE Navigation_Menu SHALL display the authenticated user's display name and profile picture, along with a "Logout" button that terminates the session and redirects to the login page

### Requirement 12: Market Data Integration

**User Story:** As an investor, I want my portfolio to automatically fetch current market data from Yahoo Finance, so that I can see up-to-date prices and metrics without manually entering them.

#### Acceptance Criteria

1. THE Market_Data_Service SHALL use the Yahoo Finance Python library (yfinance) to fetch market data for each Stock Symbol held in the portfolio
2. WHEN fetching market data for a stock, THE Market_Data_Service SHALL retrieve all of the following fields from the yfinance Ticker.info dictionary: Company Name (longName), Current Price (currentPrice or regularMarketPrice), Previous Close (previousClose), Day High (dayHigh), Day Low (dayLow), 52-Week Low (fiftyTwoWeekLow), 52-Week High (fiftyTwoWeekHigh), Market Cap (marketCap), P/E Ratio Trailing (trailingPE), P/E Ratio Forward (forwardPE), Average Volume (averageVolume), Beta (beta), Dividend Yield (dividendYield), Price to Book (priceToBook), Sector (sector), and Industry (industry)
3. WHEN a user triggers a manual refresh, THE Market_Data_Service SHALL fetch updated market data for all currently held positions and update the Portfolio Summary accordingly
4. THE Market_Data_Service SHALL cache fetched market data locally to avoid excessive API calls to Yahoo Finance
5. THE Market_Data_Service SHALL display the last refresh timestamp for market data so users know how current the displayed data is
6. IF a Stock Symbol is not found on Yahoo Finance, THEN THE Market_Data_Service SHALL display an error message for that stock indicating the symbol was not found and display all market data fields as not available
7. IF a network failure or rate limiting error occurs during data fetching, THEN THE Market_Data_Service SHALL display a descriptive error message indicating the failure reason and retain any previously cached data without crashing the application
8. THE Market_Data_Service SHALL require no manual input for any market data field; all market data fields are auto-fetched from Yahoo Finance
9. IF a specific field is not available for a ticker from Yahoo Finance (for example dividendYield is None for a non-dividend stock), THEN THE Market_Data_Service SHALL display that field as "N/A" in the Portfolio Summary
10. WHEN a user opens the Portfolio Summary page and the cached market data is older than a configurable threshold (default 1 hour), THE Market_Data_Service SHALL automatically fetch updated market data for all currently held positions before displaying the page

### Requirement 13: Trade Journal / Notes

**User Story:** As an investor, I want to attach notes and reasoning to my transactions, so that I can review my decision-making process and learn from past trades.

#### Acceptance Criteria

1. WHEN a user creates or edits a transaction, THE Trading_Log SHALL allow attaching an optional text note (up to 1000 characters) explaining the trade reasoning
2. WHEN a user views a transaction, THE Trading_Log SHALL display any attached note alongside the transaction details
3. THE Trading_Log SHALL allow the user to tag each note with one or more categories from a predefined list: "Earnings Play", "Momentum", "Value", "Dividend", "Speculative", "Technical", or a custom tag (1 to 50 characters)
4. WHERE a tag filter is specified in the trading log view, THE Trading_Log SHALL return only transactions with notes matching the specified tag
5. WHEN a user views transaction details, THE Trading_Log SHALL display all associated tags alongside the note

### Requirement 14: Price Alerts & Targets

**User Story:** As an investor, I want to set target buy and sell prices for stocks, so that I can be notified when a stock reaches a price I'm interested in.

#### Acceptance Criteria

1. WHEN a user sets a price alert, THE system SHALL store the Stock Symbol, Alert Type ("Above" or "Below"), Target Price (greater than zero in USD), and an optional note (up to 500 characters)
2. WHEN the Market_Data_Service refreshes market data and a stock's Current Price crosses a set Target Price, THE system SHALL display a visual notification on-screen indicating which alert was triggered
3. THE system SHALL allow the user to view all active alerts, sorted by Stock Symbol
4. WHEN a user deletes a price alert, THE system SHALL remove the specified alert
5. THE system SHALL allow the user to set multiple alerts per Stock Symbol (e.g., one "Above" and one "Below")
6. THE system SHALL persist all price alerts across application restarts

### Requirement 15: Dividend Tracker

**User Story:** As an investor, I want to track dividend income received from my stocks, so that I can monitor passive income and project future dividend earnings.

#### Acceptance Criteria

1. WHEN a user records a dividend payment, THE system SHALL store the Date (YYYY-MM-DD format, not in the future), Stock Symbol, Amount per Share (in USD, greater than zero), and Total Amount (quantity held at ex-date multiplied by Amount per Share)
2. WHEN a user views the Dividend Tracker page, THE system SHALL display all dividend records sorted by Date in descending order, showing Date, Stock Symbol, Amount per Share, Shares Held, and Total Amount
3. THE system SHALL display Dividend Yield on Cost (total annual dividends for a stock divided by Total Cost of that stock, expressed as a percentage to 2 decimal places)
4. THE system SHALL display projected annual dividend income based on the most recent dividend rate multiplied by current Quantity held for each stock
5. WHEN a user requests a summary by stock, THE system SHALL display total dividends received per Stock Symbol
6. WHEN a user requests a summary by time period (monthly or yearly), THE system SHALL display total dividends received per month or year

### Requirement 16: Realized P/L History

**User Story:** As an investor, I want to automatically track my realized gains and losses when I sell stocks, so that I can understand my true trading performance and plan for taxes.

#### Acceptance Criteria

1. WHEN a sell transaction is recorded, THE system SHALL automatically calculate the Realized P/L as (Sell Price per Share minus Average Cost per Share) multiplied by Sell Quantity
2. THE system SHALL store each realized P/L record with: Date, Stock Symbol, Sell Quantity, Sell Price, Avg Cost at time of sale, Realized P/L amount, and Hold Duration (days between weighted average buy date and sell date)
3. WHEN a user views the Realized P/L page, THE system SHALL display all realized P/L records sorted by Date in descending order
4. THE system SHALL display cumulative realized P/L totals: monthly, yearly, and all-time
5. THE system SHALL classify each realized P/L record as "Short-term" (held less than 365 days) or "Long-term" (held 365 days or more)
6. WHERE a time period filter is specified (monthly or yearly), THE system SHALL display only realized P/L records within that period with a subtotal

### Requirement 17: Portfolio Rebalancing Insights

**User Story:** As an investor, I want to compare my actual portfolio allocation against my target allocation, so that I can identify when positions are over- or under-weight and take corrective action.

#### Acceptance Criteria

1. THE system SHALL allow the user to set a target allocation percentage for each Stock Symbol or Sector, where all target allocations sum to 100%
2. WHEN a user views the Rebalancing page, THE system SHALL display each position showing: Stock Symbol, Current Allocation percentage, Target Allocation percentage, and Difference (Current minus Target)
3. IF a position's Current Allocation deviates from its Target Allocation by more than a user-configurable threshold (default 5 percentage points), THEN THE system SHALL visually highlight that position as "Over-weight" or "Under-weight"
4. THE system SHALL suggest rebalancing actions: how many shares to buy or sell for each over/under-weight position to reach target allocation, based on current prices
5. THE system SHALL persist all target allocations across application restarts

### Requirement 18: Risk Metrics Dashboard

**User Story:** As an investor, I want to see risk-related metrics for my portfolio, so that I can understand my exposure and concentration risk.

#### Acceptance Criteria

1. WHEN a user views the Risk Metrics section, THE system SHALL display Portfolio Beta (weighted average of each position's Beta by allocation)
2. WHEN a user views the Risk Metrics section, THE system SHALL display Sector Concentration showing the percentage of Total Cost allocated to each Sector (auto-fetched from Yahoo Finance)
3. IF any single Sector accounts for more than 50% of total portfolio value, THEN THE system SHALL display a concentration warning
4. IF any single Stock accounts for more than 25% of total portfolio value, THEN THE system SHALL display a position concentration warning
5. THE system SHALL calculate and display Maximum Drawdown: the largest peak-to-trough decline in portfolio value based on recorded Performance History snapshots, expressed as a percentage

### Requirement 19: Watchlist

**User Story:** As an investor, I want to track stocks I'm interested in but haven't bought yet, so that I can monitor their prices and decide when to invest.

#### Acceptance Criteria

1. WHEN a user adds a stock to the Watchlist, THE system SHALL store the Stock Symbol and an optional "Interested At" target price (in USD, greater than zero)
2. THE Market_Data_Service SHALL auto-fetch market data (all 16 yfinance fields) for all Watchlist stocks alongside portfolio stocks
3. WHEN a user views the Watchlist page, THE system SHALL display each watched stock with: Stock Symbol, Company Name, Current Price, Day Change (percentage), 52-Week Low, 52-Week High, P/E Trailing, and the user's "Interested At" price
4. IF a Watchlist stock's Current Price drops to or below the user's "Interested At" price, THEN THE system SHALL visually highlight that stock as "At Target"
5. WHEN a user removes a stock from the Watchlist, THE system SHALL delete that entry
6. THE system SHALL persist the Watchlist across application restarts
7. THE system SHALL allow the user to add optional notes (up to 500 characters) per Watchlist entry

### Requirement 20: Trending & Popular Stocks

**User Story:** As an investor, I want to see trending stocks and market movers, so that I can discover new investment opportunities and stay informed about market activity.

#### Acceptance Criteria

1. WHEN a user views the Trending Stocks section, THE system SHALL fetch and display currently trending tickers from Yahoo Finance
2. THE system SHALL display Top Gainers (stocks with highest percentage price increase of the day) with Stock Symbol, Company Name, Current Price, and Day Change percentage
3. THE system SHALL display Top Losers (stocks with highest percentage price decline of the day) with Stock Symbol, Company Name, Current Price, and Day Change percentage
4. THE system SHALL display Most Active (stocks with highest trading volume of the day) with Stock Symbol, Company Name, Current Price, Volume, and Average Volume
5. WHEN a user clicks on a trending stock, THE system SHALL offer the option to add it to the Watchlist
6. THE system SHALL cache trending data and refresh it no more frequently than once per 15 minutes

### Requirement 21: Stock Tags & Categories

**User Story:** As an investor, I want to categorize my stocks with custom tags, so that I can organize and filter my portfolio and watchlist by investment strategy or theme.

#### Acceptance Criteria

1. THE system SHALL allow the user to create custom tags (1 to 50 characters each, unique, case-insensitive)
2. THE system SHALL allow the user to assign one or more tags to any stock in their portfolio or watchlist
3. WHEN a user views the Portfolio Summary or Watchlist, THE system SHALL display assigned tags for each stock
4. WHERE a tag filter is applied, THE system SHALL display only stocks matching the selected tag(s)
5. THE system SHALL display aggregated performance metrics per tag: total cost, total market value, unrealized P/L, and ROI percent for all stocks sharing that tag
6. WHEN a user deletes a tag, THE system SHALL remove that tag from all associated stocks
7. THE system SHALL persist all tags and tag assignments across application restarts

### Requirement 22: Investment Thesis Board

**User Story:** As an investor, I want to create and manage investment idea cards, so that I can track my research pipeline from initial interest through to execution or rejection.

#### Acceptance Criteria

1. WHEN a user creates an investment idea, THE system SHALL store: Stock Symbol, Title (1 to 200 characters), Thesis (why interested, up to 2000 characters), Target Entry Price (in USD, greater than zero), Risk Level ("Low", "Medium", or "High"), Source/Link (optional, up to 500 characters), and Status
2. THE system SHALL support the following statuses for an idea: "Researching", "Watching", "Bought", "Passed", "Closed"
3. WHEN a user views the Investment Ideas page, THE system SHALL display all ideas sorted by most recently updated, showing Title, Stock Symbol, Status, Risk Level, Target Entry Price, and Current Price (auto-fetched)
4. THE system SHALL allow the user to filter ideas by Status, Risk Level, or Stock Symbol
5. WHEN a user changes an idea's status to "Bought", THE system SHALL allow linking it to an actual transaction in the Trading Log
6. THE system SHALL persist all investment ideas across application restarts
7. THE system SHALL assign a unique identifier to each idea upon creation

### Requirement 23: Sector Heatmap

**User Story:** As an investor, I want a visual sector heatmap of my portfolio, so that I can quickly see which sectors are performing well and which are underperforming.

#### Acceptance Criteria

1. WHEN a user views the Sector Heatmap, THE system SHALL display each Sector (auto-fetched from Yahoo Finance) as a colored block sized proportionally to its allocation in the portfolio
2. THE system SHALL color-code each Sector block based on its aggregate ROI Percent: green shades for positive returns and red shades for negative returns
3. WHEN a user hovers over or clicks on a Sector block, THE system SHALL display: Sector name, number of positions, total cost, total market value, unrealized P/L, and ROI Percent for that sector
4. IF a sector has no current holdings, THEN THE system SHALL not display a block for that sector
5. THE system SHALL update the heatmap whenever market data is refreshed

### Requirement 24: Stock Screener

**User Story:** As an investor, I want to filter and discover stocks based on financial criteria, so that I can find new investment opportunities matching my strategy.

#### Acceptance Criteria

1. THE system SHALL allow the user to define filter criteria including: P/E Ratio range (min/max), Dividend Yield range (min/max), Market Cap tier (Micro, Small, Mid, Large, Mega), Sector, and Industry
2. WHEN a user applies screener filters, THE system SHALL query Yahoo Finance for stocks matching all specified criteria and display results showing Stock Symbol, Company Name, Current Price, P/E, Dividend Yield, Market Cap, and Sector
3. THE system SHALL allow the user to save filter presets with a name (1 to 100 characters) for repeated use
4. THE system SHALL allow the user to load a saved filter preset and apply it
5. WHEN viewing screener results, THE system SHALL allow the user to add any stock to the Watchlist with one click
6. THE system SHALL limit screener results to a maximum of 50 stocks per query
7. THE system SHALL persist saved filter presets across application restarts

### Requirement 25: User Authentication (OAuth Login/Logout)

**User Story:** As a user, I want to log in using my Gmail or Facebook account, so that I can securely access the investment tracker without creating a separate password.

#### Acceptance Criteria

1. WHEN a user navigates to the application without being authenticated, THE system SHALL display a login page with two options: "Sign in with Google" and "Sign in with Facebook"
2. WHEN a user clicks "Sign in with Google", THE system SHALL initiate the Google OAuth 2.0 authentication flow and redirect the user to Google's consent screen
3. WHEN a user clicks "Sign in with Facebook", THE system SHALL initiate the Facebook OAuth 2.0 authentication flow and redirect the user to Facebook's consent screen
4. WHEN a user successfully completes OAuth authentication, THE system SHALL create a session, store the user's display name, email address, and profile picture URL, and redirect to the Dashboard page
5. IF a user's account has not been approved by an admin, THEN THE system SHALL display a "Pending Approval" message after login and deny access to all application features until approved
6. WHEN a user clicks "Logout", THE system SHALL terminate the current session, clear all session data, and redirect the user to the login page
7. IF an OAuth authentication fails (user cancels, provider error, or network failure), THEN THE system SHALL display an error message on the login page indicating the failure reason and allow the user to retry
8. THE system SHALL maintain the user's session across page refreshes using a secure session token (HTTP-only, secure cookie or equivalent)
9. IF a session token expires or becomes invalid, THEN THE system SHALL redirect the user to the login page and require re-authentication
10. THE system SHALL prevent access to any application page or API endpoint for unauthenticated users, redirecting them to the login page

### Requirement 26: Admin User Management & Approval

**User Story:** As the site owner (admin), I want to approve or deny access for friends who register on my investment website, so that only people I trust can use the system.

#### Acceptance Criteria

1. THE system SHALL designate the first registered user as the "Admin" by default, with full access to all features plus the Admin panel
2. WHEN a new user logs in for the first time via OAuth, THE system SHALL create their account with status "Pending Approval" and notify the admin that a new user is awaiting approval
3. WHEN an admin navigates to the Admin panel, THE system SHALL display a list of all registered users showing: display name, email, profile picture, login provider (Google or Facebook), registration date, and status ("Approved", "Pending", or "Blocked")
4. WHEN an admin approves a user, THE system SHALL change that user's status to "Approved" and grant them full access to all non-admin features
5. WHEN an admin blocks a user, THE system SHALL change that user's status to "Blocked" and immediately revoke their access to all application features
6. IF a blocked user attempts to log in, THEN THE system SHALL display a message indicating their access has been revoked and prevent them from accessing any application features
7. THE system SHALL allow the admin to change a user's status at any time (Approve, Block, or revert to Pending)
8. THE system SHALL persist all user accounts and their statuses across application restarts
9. THE system SHALL prevent non-admin users from accessing the Admin panel; if attempted, THE system SHALL return an access denied error

### Requirement 27: Per-User Data Isolation

**User Story:** As a user, I want my investment data to be private and separate from other users' data, so that only I can see my own transactions, portfolio, and settings.

#### Acceptance Criteria

1. THE system SHALL associate all data (transactions, money transfers, portfolio settings, watchlist, tags, alerts, ideas, performance snapshots, dividend records, and screener presets) with the authenticated user who created it
2. WHEN a user queries any data (trading log, transfers, portfolio summary, etc.), THE system SHALL return only data belonging to the currently authenticated user
3. THE system SHALL prevent any user from viewing, editing, or deleting another user's data
4. IF a user attempts to access a resource that does not belong to them, THEN THE system SHALL return an access denied error without revealing the existence of the resource
5. THE admin user SHALL only see their own investment data in the main application; the Admin panel shows user account information only (not other users' investment data)
6. THE system SHALL ensure that market data cache and trending stocks data are shared across all users (not duplicated per user) since they are public information


### Requirement 28: Email Alert Notifications

**User Story:** As an investor, I want to receive email notifications when my price alerts trigger, so that I am informed of important price movements even when I'm not actively using the application.

#### Acceptance Criteria

1. WHEN a price alert triggers (stock price crosses the target threshold), THE system SHALL send an HTML-formatted email notification to the user's registered email address containing: Stock Symbol, Alert Type (Above/Below), Target Price, and Current Price at time of trigger
2. THE system SHALL configure SMTP settings via environment variables: SMTP_HOST, SMTP_PORT, SMTP_USER, and SMTP_PASSWORD
3. THE system SHALL allow email notifications to be enabled or disabled via the ALERT_EMAIL_ENABLED environment variable (default: disabled)
4. IF ALERT_EMAIL_ENABLED is set to false or SMTP configuration is incomplete, THEN THE system SHALL skip email sending without causing errors and continue to show in-app notifications
5. IF an email send fails (SMTP error, network failure), THEN THE system SHALL log the error and continue operation without affecting the price alert trigger status or in-app notification

### Requirement 29: Sortable Table Headers

**User Story:** As an investor, I want to click on table column headers to sort data, so that I can quickly organize and find information in any table view.

#### Acceptance Criteria

1. THE system SHALL provide clickable sortable headers on all data tables across all pages (Trading Log, Money Transfers, Portfolio Summary, Performance History, Watchlist, Dividend Tracker, Realized P/L, etc.)
2. WHEN a user clicks a column header, THE system SHALL cycle through sort states: first click sorts Ascending (▲), second click sorts Descending (▼), third click removes sorting (returns to default order)
3. THE system SHALL display a visual indicator (▲ or ▼) next to the currently sorted column header
4. THE system SHALL support sorting for string values (alphabetical), numeric values (numerical), and percentage values (numerical by underlying value)
5. THE system SHALL implement sorting via a reusable `useSortableData` hook that can be applied to any table component
6. WHEN sorting is active, THE system SHALL sort the entire dataset (not just the visible page if paginated)

### Requirement 30: UI/UX Theme & Branding

**User Story:** As a user, I want the application to have a professional, consistent visual design with clear branding, so that the interface is pleasant to use and easy to navigate.

#### Acceptance Criteria

1. THE system SHALL display the branding name "My Investment" with a custom logo in the navigation sidebar
2. THE system SHALL use a royal blue (#0052FF) primary color throughout the application for buttons, active states, and accent elements
3. THE system SHALL use #F4F6F9 as the content area background color with white cards (#FFFFFF) featuring soft shadows for content containers
4. THE Navigation_Menu sidebar SHALL have a white background with blue pill-shaped active state indicators, emoji icons for each page, and section labels grouping related pages
5. THE Dashboard cards SHALL use a flat white style with 16px rounded corners and centered text for key metrics
6. THE system SHALL use a full-width layout utilizing the entire screen width, with the sidebar as the only fixed-width element
7. THE system SHALL apply consistent spacing, typography, and color usage across all pages

### Requirement 31: Deployment & Infrastructure

**User Story:** As a developer/operator, I want the application to be containerized and deployable to cloud infrastructure, so that it can be reliably hosted and scaled.

#### Acceptance Criteria

1. THE system SHALL provide a Docker Compose configuration with 4 services: PostgreSQL (database), Redis (cache), Backend (FastAPI), and Frontend (React/nginx)
2. THE Backend service SHALL use Python 3.12-slim as the base image and run via uvicorn
3. THE Frontend service SHALL use a multi-stage build with Node 20 for building and nginx for serving the static assets
4. THE system SHALL provide Azure deployment documentation covering Container Apps and App Service deployment options
5. THE system SHALL support OAuth setup for both Google and Facebook providers via environment variables
6. THE system SHALL document all required environment variables for production deployment including database connection, Redis connection, SMTP settings, OAuth credentials, and application secrets

