import { apiClient } from './client';
export { apiClient };
import type {
  User,
  Transaction,
  TransactionCreate,
  TransactionUpdate,
  TransactionFilters,
  SnapshotEntry,
  Transfer,
  TransferCreate,
  TransferUpdate,
  TransferFilters,
  PortfolioSummary,
  DashboardData,
  PerformanceSnapshot,
  PerformanceSnapshotCreate,
  PerformanceSnapshotUpdate,
  PerformanceFilters,
  PerformanceSummary,
  PriceAlert,
  PriceAlertCreate,
  DividendRecord,
  DividendCreate,
  DividendSummary,
  DividendProjection,
  RealizedPLSummary,
  WatchlistItem,
  WatchlistItemCreate,
  WatchlistItemUpdate,
  InvestmentIdea,
  InvestmentIdeaCreate,
  InvestmentIdeaUpdate,
  IdeaFilters,
  ScreenerFilter,
  ScreenerPreset,
  ScreenerPresetCreate,
  Tag,
  TagPerformance,
  TrendingData,
  RebalancingData,
  TargetAllocation,
  RiskMetrics,
  UserStatus,
} from '../types';

// ===== Auth =====

export const authApi = {
  loginGoogle: () => {
    window.location.href = `${apiClient.defaults.baseURL}/api/auth/login/google`;
  },
  loginFacebook: () => {
    window.location.href = `${apiClient.defaults.baseURL}/api/auth/login/facebook`;
  },
  logout: () => apiClient.post('/api/auth/logout'),
  getMe: () => apiClient.get<User>('/api/auth/me').then((r) => r.data),
};

// ===== Transactions =====

export const transactionsApi = {
  list: (filters?: TransactionFilters) => {
    const normalizedFilters = { ...filters } as TransactionFilters & Record<string, unknown>;
    if (normalizedFilters.stock_symbol && !normalizedFilters.symbol) {
      normalizedFilters.symbol = normalizedFilters.stock_symbol;
    }
    if (normalizedFilters.symbol && !normalizedFilters.stock_symbol) {
      normalizedFilters.stock_symbol = normalizedFilters.symbol;
    }
    return apiClient.get('/api/transactions', { params: normalizedFilters }).then((r) => {
      const data = r.data;
      return Array.isArray(data) ? data : data?.transactions ?? data?.records ?? [];
    });
  },
  create: (data: TransactionCreate) =>
    apiClient.post<Transaction>('/api/transactions', data).then((r) => r.data),
  update: (id: string, data: TransactionUpdate) =>
    apiClient.put<Transaction>(`/api/transactions/${id}`, data).then((r) => r.data),
  delete: (id: string) => apiClient.delete(`/api/transactions/${id}`),
  importSnapshot: (entries: SnapshotEntry[]) =>
    apiClient.post('/api/transactions/snapshot', { entries }).then((r) => r.data),
  exportExcel: (filters?: TransactionFilters) => {
    const normalizedFilters = { ...filters } as TransactionFilters & Record<string, unknown>;
    if (normalizedFilters.stock_symbol && !normalizedFilters.symbol) {
      normalizedFilters.symbol = normalizedFilters.stock_symbol;
    }
    if (normalizedFilters.symbol && !normalizedFilters.stock_symbol) {
      normalizedFilters.stock_symbol = normalizedFilters.symbol;
    }
    return apiClient.get('/api/transactions/export-excel', {
      params: normalizedFilters,
      responseType: 'blob',
    }).then((r) => r.data);
  },
  importExcelPreview: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return apiClient.post('/api/transactions/import-excel/preview', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then((r) => r.data);
  },
  importExcel: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return apiClient.post('/api/transactions/import-excel', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then((r) => r.data);
  },
};

// ===== Transfers =====

export const transfersApi = {
  list: (filters?: TransferFilters) =>
    apiClient.get('/api/transfers', { params: filters }).then((r) => {
      const data = r.data;
      return Array.isArray(data) ? data : data?.transfers ?? data?.records ?? [];
    }),
  create: (data: TransferCreate) =>
    apiClient.post<Transfer>('/api/transfers', data).then((r) => r.data),
  update: (id: string, data: TransferUpdate) =>
    apiClient.put<Transfer>(`/api/transfers/${id}`, data).then((r) => r.data),
  delete: (id: string) => apiClient.delete(`/api/transfers/${id}`),
  exportExcel: (filters?: TransferFilters) =>
    apiClient.get('/api/transfers/export-excel', { params: filters, responseType: 'blob' }).then((r) => r.data),
  importExcelPreview: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return apiClient.post('/api/transfers/import-excel/preview', formData, { headers: { 'Content-Type': 'multipart/form-data' } }).then((r) => r.data);
  },
  importExcel: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return apiClient.post('/api/transfers/import-excel', formData, { headers: { 'Content-Type': 'multipart/form-data' } }).then((r) => r.data);
  },
};

// ===== Portfolio =====

export const portfolioApi = {
  getSummary: () =>
    apiClient.get<PortfolioSummary>('/api/portfolio/summary').then((r) => r.data),
  refresh: () => apiClient.post('/api/portfolio/refresh'),
  setSentiment: (symbol: string, sentiment: string) =>
    apiClient.put(`/api/portfolio/${symbol}/sentiment`, { sentiment }),
  getRebalancing: () =>
    apiClient.get<RebalancingData>('/api/portfolio/rebalancing').then((r) => r.data),
  setTargetAllocations: (targets: TargetAllocation[]) =>
    apiClient.put('/api/portfolio/rebalancing/targets', { targets }),
  getRiskMetrics: () =>
    apiClient.get<RiskMetrics>('/api/portfolio/risk-metrics').then((r) => r.data),
  getSectorHeatmap: () =>
    apiClient.get('/api/portfolio/sector-heatmap').then((r) => r.data?.sectors ?? r.data ?? []),
};

// ===== Performance =====

export const performanceApi = {
  list: (filters?: PerformanceFilters) =>
    apiClient
      .get<PerformanceSummary>('/api/performance/snapshots', { params: filters })
      .then((r) => r.data),
  create: (data: PerformanceSnapshotCreate) =>
    apiClient.post<PerformanceSnapshot>('/api/performance/snapshots', data).then((r) => r.data),
  update: (id: string, data: PerformanceSnapshotUpdate) =>
    apiClient
      .put<PerformanceSnapshot>(`/api/performance/snapshots/${id}`, data)
      .then((r) => r.data),
  delete: (id: string) => apiClient.delete(`/api/performance/snapshots/${id}`),
};

// ===== Dashboard =====

export const dashboardApi = {
  get: () => apiClient.get<DashboardData>('/api/dashboard').then((r) => r.data),
};

// ===== Journal =====

export const journalApi = {
  updateNote: (transactionId: string, note: string) =>
    apiClient.put(`/api/transactions/${transactionId}/notes`, { note }),
  updateTags: (transactionId: string, tagIds: string[]) =>
    apiClient.put(`/api/transactions/${transactionId}/tags`, { tag_ids: tagIds }),
  listTags: () =>
    apiClient.get<{ tags: Tag[] }>('/api/journal/tags').then((r) => r.data.tags),
  createTag: (name: string) =>
    apiClient.post<Tag>('/api/journal/tags', { name }).then((r) => r.data),
  deleteTag: (id: string) => apiClient.delete(`/api/journal/tags/${id}`),
};

// ===== Price Alerts =====

export const alertsApi = {
  list: () => apiClient.get('/api/alerts').then((r) => {
    const data = r.data;
    return Array.isArray(data) ? data : data?.alerts ?? data?.records ?? [];
  }),
  create: (data: PriceAlertCreate) =>
    apiClient.post<PriceAlert>('/api/alerts', data).then((r) => r.data),
  delete: (id: string) => apiClient.delete(`/api/alerts/${id}`),
};

// ===== Dividends =====

export const dividendsApi = {
  list: () => apiClient.get('/api/dividends').then((r) => {
    const data = r.data;
    return Array.isArray(data) ? data : data?.records ?? data?.dividends ?? [];
  }),
  create: (data: DividendCreate) =>
    apiClient.post<DividendRecord>('/api/dividends', data).then((r) => r.data),
  getSummary: (groupBy?: 'stock' | 'monthly' | 'yearly') =>
    apiClient
      .get<DividendSummary>('/api/dividends/summary', { params: { group_by: groupBy } })
      .then((r) => r.data),
  getProjection: () =>
    apiClient.get<DividendProjection>('/api/dividends/projection').then((r) => r.data),
};

// ===== Realized P/L =====

export const realizedPlApi = {
  list: (params?: { date_from?: string; date_to?: string; stock_symbol?: string; term_type?: string }) =>
    apiClient.get('/api/realized-pl', { params }).then((r) => {
      const data = r.data;
      return Array.isArray(data) ? data : data?.records ?? [];
    }),
  getSummary: (group_by?: string) =>
    apiClient.get<RealizedPLSummary>('/api/realized-pl/summary', { params: { group_by } }).then((r) => r.data),
};

// ===== Watchlist =====

export const watchlistApi = {
  list: () => apiClient.get('/api/watchlist').then((r) => r.data?.items ?? r.data ?? []),
  create: (data: WatchlistItemCreate) =>
    apiClient.post<WatchlistItem>('/api/watchlist', data).then((r) => r.data),
  update: (id: string, data: WatchlistItemUpdate) =>
    apiClient.put<WatchlistItem>(`/api/watchlist/${id}`, data).then((r) => r.data),
  delete: (id: string) => apiClient.delete(`/api/watchlist/${id}`),
};

// ===== Investment Ideas =====

export const ideasApi = {
  list: (filters?: IdeaFilters) =>
    apiClient.get('/api/ideas', { params: filters }).then((r) => r.data?.ideas ?? r.data ?? []),
  create: (data: InvestmentIdeaCreate) =>
    apiClient.post<InvestmentIdea>('/api/ideas', data).then((r) => r.data),
  update: (id: string, data: InvestmentIdeaUpdate) =>
    apiClient.put<InvestmentIdea>(`/api/ideas/${id}`, data).then((r) => r.data),
  delete: (id: string) => apiClient.delete(`/api/ideas/${id}`),
};

// ===== Stock Screener =====

export const screenerApi = {
  search: (filter: ScreenerFilter) =>
    apiClient.post('/api/screener/search', filter).then((r) => {
      const data = r.data;
      return Array.isArray(data) ? data : data?.results ?? [];
    }),
  listPresets: () =>
    apiClient.get('/api/screener/presets').then((r) => {
      const data = r.data;
      return Array.isArray(data) ? data : data?.presets ?? [];
    }),
  savePreset: (data: ScreenerPresetCreate) =>
    apiClient.post<ScreenerPreset>('/api/screener/presets', data).then((r) => r.data),
  deletePreset: (id: string) => apiClient.delete(`/api/screener/presets/${id}`),
};

// ===== Trending =====

export const trendingApi = {
  get: () => apiClient.get<TrendingData>('/api/trending').then((r) => r.data),
};

// ===== Tags =====

export const tagsApi = {
  list: () => apiClient.get('/api/tags').then((r) => {
    const data = r.data;
    return Array.isArray(data) ? data : data?.tags ?? [];
  }),
  create: (name: string) => apiClient.post<Tag>('/api/tags', { name }).then((r) => r.data),
  delete: (id: string) => apiClient.delete(`/api/tags/${id}`),
  getStocks: (tagId: string) =>
    apiClient.get<string[]>(`/api/tags/${tagId}/stocks`).then((r) => r.data),
  assignToStock: (symbol: string, tagIds: string[]) =>
    apiClient.put(`/api/stocks/${symbol}/tags`, { tag_ids: tagIds }),
  getPerformance: () =>
    apiClient.get<TagPerformance[]>('/api/tags/performance').then((r) => r.data),
};

// ===== Admin =====

export const adminApi = {
  listUsers: () => apiClient.get('/api/admin/users').then((r) => {
    const data = r.data;
    return Array.isArray(data) ? data : data?.users ?? [];
  }),
  approveUser: (userId: string) => apiClient.post(`/api/admin/users/${userId}/approve`),
  blockUser: (userId: string) => apiClient.post(`/api/admin/users/${userId}/block`),
  setUserStatus: (userId: string, status: UserStatus) =>
    apiClient.put(`/api/admin/users/${userId}/status`, { status }),
};

// ===== Behavioral Analytics =====

export const behavioralApi = {
  getStats: () =>
    apiClient.get('/api/behavioral/stats').then((r) => r.data),
  getPatterns: () =>
    apiClient.get('/api/behavioral/patterns').then((r) => r.data),
};

// ===== AI Insights =====

export const aiInsightsApi = {
  getWeeklyMemo: () =>
    apiClient.get('/api/ai/weekly-memo').then((r) => r.data),
  generateWeeklyMemo: () =>
    apiClient.post('/api/ai/weekly-memo/generate').then((r) => r.data),
  getTradeReview: (transactionId: string) =>
    apiClient.get(`/api/ai/trade-review/${transactionId}`).then((r) => r.data),
  generateTradeReview: (transactionId: string) =>
    apiClient.post('/api/ai/trade-review/generate', null, { params: { transaction_id: transactionId } }).then((r) => r.data),
  getSettings: () =>
    apiClient.get('/api/ai/settings').then((r) => r.data),
};

// ===== Scenario Simulator =====

export const simulatorApi = {
  run: (scenario: {
    price_changes?: Record<string, number>;
    simulated_buys?: Array<{ symbol: string; quantity: number; price: number }>;
    simulated_sells?: Array<{ symbol: string; quantity: number; price: number }>;
    cash_deposit?: number;
    fx_rate_change?: number;
  }) => apiClient.post('/api/simulator/run', scenario).then((r) => r.data),
};

// ===== Import/Export =====

export const importExportApi = {
  previewImport: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return apiClient.post('/api/import-export/import/preview', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then((r) => r.data);
  },
  importTransactions: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return apiClient.post('/api/import-export/import', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then((r) => r.data);
  },
  exportTransactionsCsv: () =>
    apiClient.get('/api/import-export/export/transactions', { responseType: 'blob' })
      .then((r) => r.data),
  exportFullBackup: () =>
    apiClient.get('/api/import-export/export/backup', { responseType: 'blob' })
      .then((r) => r.data),
};

// ===== Position Sizing =====

export const positionSizingApi = {
  calculate: (params: {
    portfolio_value: number;
    max_risk_per_trade: number;
    entry_price: number;
    stop_loss_price: number;
    confidence_score?: number;
    target_allocation?: number;
  }) => apiClient.post('/api/rebalancing/position-size', params).then((r) => r.data),
};

// ===== Cash Ledger =====

export const cashLedgerApi = {
  get: () => apiClient.get('/api/cash-ledger').then((r) => r.data),
  getSummary: () => apiClient.get('/api/cash-ledger/summary').then((r) => r.data),
  createAdjustment: (data: { date: string; broker: string; amount: number; reason: string; note?: string }) =>
    apiClient.post('/api/cash-ledger/adjustments', data).then((r) => r.data),
};
