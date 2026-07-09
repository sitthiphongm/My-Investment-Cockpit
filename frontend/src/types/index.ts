// ===== Enums (as const objects for erasableSyntaxOnly compatibility) =====

export const ActionType = {
  BUY: 'Buy',
  SELL: 'Sell',
  SNAPSHOT: 'Snapshot',
} as const;
export type ActionType = (typeof ActionType)[keyof typeof ActionType];

export const TransferType = {
  IN: 'In',
  OUT: 'Out',
} as const;
export type TransferType = (typeof TransferType)[keyof typeof TransferType];

export const AlertType = {
  ABOVE: 'Above',
  BELOW: 'Below',
} as const;
export type AlertType = (typeof AlertType)[keyof typeof AlertType];

export const RiskLevel = {
  LOW: 'Low',
  MEDIUM: 'Medium',
  HIGH: 'High',
} as const;
export type RiskLevel = (typeof RiskLevel)[keyof typeof RiskLevel];

export const IdeaStatus = {
  RESEARCHING: 'Researching',
  WATCHING: 'Watching',
  BOUGHT: 'Bought',
  PASSED: 'Passed',
  CLOSED: 'Closed',
} as const;
export type IdeaStatus = (typeof IdeaStatus)[keyof typeof IdeaStatus];

export const UserStatus = {
  APPROVED: 'Approved',
  PENDING: 'Pending',
  BLOCKED: 'Blocked',
} as const;
export type UserStatus = (typeof UserStatus)[keyof typeof UserStatus];

export const SentimentType = {
  BEAR: 'Bear',
  BULL: 'Bull',
} as const;
export type SentimentType = (typeof SentimentType)[keyof typeof SentimentType];

// ===== User & Auth =====

export interface User {
  id: string;
  display_name: string;
  email: string;
  profile_picture_url: string | null;
  oauth_provider: string;
  status: UserStatus;
  is_admin: boolean;
  registered_at: string;
  last_login_at: string | null;
}

// ===== Transactions =====

export interface Transaction {
  id: string;
  date: string;
  stock_symbol: string;
  action: ActionType;
  quantity: number;
  price_per_share: number;
  gross_value: number;
  brokerage_fee: number;
  vat: number;
  net_capital_flow: number;
  broker: string;
  note: string | null;
  tags: string[];
  created_at: string;
  updated_at: string;
}

export interface TransactionCreate {
  date: string;
  stock_symbol: string;
  action: ActionType;
  quantity: number;
  price_per_share: number;
  brokerage_fee: number;
  vat: number;
  broker: string;
  note?: string | null;
}

export interface TransactionUpdate {
  date?: string;
  stock_symbol?: string;
  action?: ActionType;
  quantity?: number;
  price_per_share?: number;
  brokerage_fee?: number;
  vat?: number;
  broker?: string;
  note?: string | null;
}

export interface SnapshotEntry {
  stock_symbol: string;
  quantity: number;
  price_per_share: number;
  broker: string;
}

// ===== Transfers =====

export const Currency = {
  THB: 'THB',
  USD: 'USD',
} as const;
export type Currency = (typeof Currency)[keyof typeof Currency];

export interface Transfer {
  id: string;
  date: string;
  broker: string;
  transfer_type: TransferType;
  amount: number;
  original_currency: Currency | null;
  original_amount: number | null;
  fx_rate: number | null;
  converted_usd_amount: number | null;
  fx_fee: number | null;
  note: string | null;
  created_at: string;
  updated_at: string;
}

export interface TransferCreate {
  date: string;
  broker: string;
  transfer_type: TransferType;
  amount: number;
  original_currency?: Currency;
  original_amount?: number | null;
  fx_rate?: number | null;
  fx_fee?: number | null;
  note?: string | null;
}

export interface TransferUpdate {
  date?: string;
  broker?: string;
  transfer_type?: TransferType;
  amount?: number;
  original_currency?: Currency;
  original_amount?: number | null;
  fx_rate?: number | null;
  fx_fee?: number | null;
  note?: string | null;
}

// ===== Portfolio =====

export interface PortfolioPosition {
  stock_symbol: string;
  quantity: number;
  avg_cost: number;
  total_cost: number;
  market_value: number | null;
  unrealized_pl: number | null;
  roi_percent: number | null;
  allocation_percent: number;
  sentiment: SentimentType | null;
  company_name: string | null;
  sector: string | null;
  industry: string | null;
  current_price: number | null;
  previous_close: number | null;
  day_high: number | null;
  day_low: number | null;
  fifty_two_week_low: number | null;
  fifty_two_week_high: number | null;
  market_cap: number | null;
  pe_trailing: number | null;
  pe_forward: number | null;
  average_volume: number | null;
  beta: number | null;
  dividend_yield: number | null;
  price_to_book: number | null;
  last_refresh: string | null;
}

export interface PortfolioSummary {
  positions: PortfolioPosition[];
  total_cost: number;
  total_market_value: number | null;
  total_unrealized_pl: number | null;
  total_roi_percent: number | null;
  market_data_complete: boolean;
}

// ===== Dashboard =====

export interface BrokerCapital {
  broker: string;
  total_in: number;
  total_out: number;
  net_capital: number;
}

export interface DashboardData {
  total_invested: number;
  total_withdrawn: number;
  net_invested: number;
  total_market_value: number | null;
  overall_pl: number | null;
  overall_roi_percent: number | null;
  total_positions: number;
  total_brokers: number;
  capital_per_broker: BrokerCapital[];
  market_data_complete: boolean;
}

// ===== Performance =====

export interface PerformanceSnapshot {
  id: string;
  date: string;
  total_portfolio_value: number;
  total_cost: number;
  pl: number;
  period_return: number | null;
  created_at: string;
  updated_at: string;
}

export interface PerformanceSnapshotCreate {
  date: string;
  total_portfolio_value: number;
  total_cost: number;
}

export interface PerformanceSnapshotUpdate {
  date?: string;
  total_portfolio_value?: number;
  total_cost?: number;
}

export interface PerformanceSummary {
  snapshots: PerformanceSnapshot[];
  cumulative_return: number | null;
}

// ===== Price Alerts =====

export interface PriceAlert {
  id: string;
  stock_symbol: string;
  alert_type: AlertType;
  target_price: number;
  note: string | null;
  triggered: boolean;
  created_at: string;
}

export interface PriceAlertCreate {
  stock_symbol: string;
  alert_type: AlertType;
  target_price: number;
  note?: string | null;
}

// ===== Dividends =====

export interface DividendRecord {
  id: string;
  date: string;
  stock_symbol: string;
  amount_per_share: number;
  shares_held: number;
  total_amount: number;
  created_at: string;
}

export interface DividendCreate {
  date: string;
  stock_symbol: string;
  amount_per_share: number;
  shares_held: number;
  total_amount: number;
}

export interface DividendSummary {
  by_stock: Record<string, number>;
  by_period: Record<string, number>;
  total: number;
}

export interface DividendProjection {
  projected_annual_income: number;
  by_stock: Record<string, number>;
}

// ===== Realized P/L =====

export interface RealizedPL {
  id: string;
  date: string;
  stock_symbol: string;
  sell_quantity: number;
  sell_price: number;
  avg_cost_at_sale: number;
  realized_pl: number;
  hold_duration_days: number;
  term_type: 'Short-term' | 'Long-term';
  transaction_id: string;
  created_at: string;
}

export interface RealizedPLSummaryEntry {
  period: string;
  total_realized_pl: number;
  total_short_term: number;
  total_long_term: number;
  record_count: number;
}

export interface RealizedPLSummary {
  entries: RealizedPLSummaryEntry[];
  all_time_total: number;
  all_time_short_term: number;
  all_time_long_term: number;
}

// ===== Watchlist =====

export interface WatchlistItem {
  id: string;
  stock_symbol: string;
  interested_at_price: number | null;
  notes: string | null;
  at_target: boolean;
  current_price: number | null;
  company_name: string | null;
  day_change_percent: number | null;
  created_at: string;
  updated_at: string;
}

export interface WatchlistItemCreate {
  stock_symbol: string;
  interested_at_price?: number | null;
  notes?: string | null;
}

export interface WatchlistItemUpdate {
  interested_at_price?: number | null;
  notes?: string | null;
}

// ===== Investment Ideas =====

export interface InvestmentIdea {
  id: string;
  stock_symbol: string;
  title: string;
  thesis: string;
  target_entry_price: number | null;
  risk_level: RiskLevel;
  source_link: string | null;
  status: IdeaStatus;
  linked_transaction_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface InvestmentIdeaCreate {
  stock_symbol: string;
  title: string;
  thesis: string;
  target_entry_price?: number | null;
  risk_level: RiskLevel;
  source_link?: string | null;
  status: IdeaStatus;
}

export interface InvestmentIdeaUpdate {
  stock_symbol?: string;
  title?: string;
  thesis?: string;
  target_entry_price?: number | null;
  risk_level?: RiskLevel;
  source_link?: string | null;
  status?: IdeaStatus;
  linked_transaction_id?: string | null;
}

// ===== Stock Screener =====

export interface ScreenerFilter {
  pe_min?: number | null;
  pe_max?: number | null;
  dividend_yield_min?: number | null;
  dividend_yield_max?: number | null;
  market_cap_min?: number | null;
  market_cap_max?: number | null;
  sector?: string | null;
  industry?: string | null;
  peg_ratio_min?: number | null;
  peg_ratio_max?: number | null;
  price_to_book_min?: number | null;
  price_to_book_max?: number | null;
  price_to_sales_min?: number | null;
  price_to_sales_max?: number | null;
  revenue_growth_min?: number | null;
  revenue_growth_max?: number | null;
  short_percent_min?: number | null;
  short_percent_max?: number | null;
}

export interface ScreenerPreset {
  id: string;
  name: string;
  filter_criteria: ScreenerFilter;
  created_at: string;
}

export interface ScreenerPresetCreate {
  name: string;
  filter_criteria: ScreenerFilter;
}

export interface ScreenerResult {
  stock_symbol: string;
  company_name: string | null;
  sector: string | null;
  industry: string | null;
  current_price: number | null;
  pe_trailing: number | null;
  peg_ratio: number | null;
  dividend_yield: number | null;
  market_cap: number | null;
  price_to_book: number | null;
  price_to_sales: number | null;
  revenue_growth: number | null;
  short_percent_of_float: number | null;
  beta: number | null;
}

// ===== Tags =====

export interface Tag {
  id: string;
  name: string;
  created_at: string;
}

export interface TagPerformance {
  tag: Tag;
  total_cost: number;
  total_market_value: number | null;
  unrealized_pl: number | null;
  roi_percent: number | null;
}

// ===== Trending =====

export interface TrendingStock {
  symbol: string;
  stock_symbol?: string;
  company_name: string | null;
  current_price: number | null;
  day_change_percent: number | null;
  volume: number | null;
}

export interface TrendingData {
  gainers: TrendingStock[];
  losers: TrendingStock[];
  most_active: TrendingStock[];
}

// ===== Sector Heatmap =====

export interface SectorHeatmapEntry {
  sector: string;
  total_cost: number;
  total_market_value: number;
  roi_percent: number;
  allocation_percent: number;
  position_count: number;
}

// ===== Rebalancing =====

export interface RebalancingPosition {
  target_key: string;
  target_type: 'Symbol' | 'Sector';
  current_allocation: number;
  target_allocation: number;
  difference: number;
  is_overweight: boolean;
  is_underweight: boolean;
  suggested_action: string | null;
}

export interface RebalancingData {
  positions: RebalancingPosition[];
  deviation_threshold: number;
}

export interface TargetAllocation {
  target_key: string;
  target_type: 'Symbol' | 'Sector';
  target_percentage: number;
}

// ===== Risk Metrics =====

export interface RiskMetrics {
  portfolio_beta: number | null;
  sector_concentration: Record<string, number>;
  position_concentration: Record<string, number>;
  max_drawdown: number | null;
  warnings: string[];
}

// ===== Admin =====

export interface AdminUser {
  id: string;
  display_name: string;
  email: string;
  profile_picture_url: string | null;
  oauth_provider: string;
  status: UserStatus;
  is_admin: boolean;
  registered_at: string;
  last_login_at: string | null;
}

// ===== Common =====

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface ApiError {
  detail: string;
  field?: string;
  errors?: Array<{ field: string; message: string }>;
}

// ===== Filter Types =====

export interface TransactionFilters {
  date_from?: string;
  date_to?: string;
  stock_symbol?: string;
  // Backend expects `symbol` as query param; keep both for compatibility
  symbol?: string;
  broker?: string;
  action?: ActionType;
  tag?: string;
}

export interface TransferFilters {
  broker?: string;
}

export interface PerformanceFilters {
  date_from?: string;
  date_to?: string;
  aggregation?: 'monthly' | 'yearly';
}

export interface IdeaFilters {
  status?: IdeaStatus;
  risk_level?: RiskLevel;
  stock_symbol?: string;
}
