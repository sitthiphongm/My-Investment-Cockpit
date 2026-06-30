import { useCallback, useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { apiClient } from '../api';
import { formatTHB, formatPercent, toNum } from '../utils/format';
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Area, AreaChart, Cell,
} from 'recharts';

type TabKey = 'overview' | 'financials' | 'statistics' | 'dividends' | 'insider' | 'profile' | 'chart';
type ChartPeriod = '1d' | '5d' | '1mo' | '3mo' | '6mo' | '1y' | '5y' | 'max';

interface StockData {
  profile: Record<string, any>;
  price: Record<string, any>;
  valuation: Record<string, any>;
  dividends: Record<string, any>;
  short_info: Record<string, any>;
  profitability: Record<string, any>;
  financials: {
    income_statement: Record<string, any>[];
    balance_sheet: Record<string, any>[];
    cash_flow: Record<string, any>[];
  };
  analysts: Record<string, any>;
  dividend_history: { date: string; amount: number }[];
}

interface PricePoint {
  date: string;
  close: number | null;
  volume: number;
}

export default function StockDetailPage() {
  const { symbol } = useParams<{ symbol: string }>();
  const [data, setData] = useState<StockData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabKey>('overview');
  const [chartPeriod, setChartPeriod] = useState<ChartPeriod>('1y');
  const [chartData, setChartData] = useState<PricePoint[]>([]);
  const [chartLoading, setChartLoading] = useState(false);

  const fetchData = useCallback(async () => {
    if (!symbol) return;
    setLoading(true);
    setError(null);
    try {
      const res = await apiClient.get(`/api/stocks/${symbol}/info`);
      setData(res.data);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to load stock data');
    } finally {
      setLoading(false);
    }
  }, [symbol]);

  const fetchChart = useCallback(async () => {
    if (!symbol) return;
    setChartLoading(true);
    try {
      const interval = chartPeriod === '1d' ? '5m' : chartPeriod === '5d' ? '15m' : '1d';
      const res = await apiClient.get(`/api/stocks/${symbol}/history`, {
        params: { period: chartPeriod, interval },
      });
      setChartData(res.data.prices ?? []);
    } catch {
      setChartData([]);
    } finally {
      setChartLoading(false);
    }
  }, [symbol, chartPeriod]);

  useEffect(() => { fetchData(); }, [fetchData]);
  useEffect(() => { fetchChart(); }, [fetchChart]);

  if (loading) {
    return (
      <div className="page stock-detail-page">
        <h1>{symbol?.toUpperCase()}</h1>
        <p className="loading-text" aria-live="polite">Loading stock data...</p>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="page stock-detail-page">
        <h1>{symbol?.toUpperCase()}</h1>
        <div className="empty-state" role="alert">
          <div className="empty-state-icon">⚠️</div>
          <h2>Unable to Load Data</h2>
          <p>{error || 'No data available for this symbol.'}</p>
          <Link to="/watchlist" className="btn btn-secondary">← Back to Watchlist</Link>
        </div>
      </div>
    );
  }

  const { profile, price, valuation, dividends, short_info, profitability, financials, analysts, dividend_history } = data;
  const priceChange = price.current_price && price.previous_close
    ? price.current_price - price.previous_close : null;
  const priceChangePercent = priceChange && price.previous_close
    ? (priceChange / price.previous_close) * 100 : null;

  return (
    <div className="page stock-detail-page">
      {/* Header */}
      <div className="stock-header">
        <div>
          <h1>{profile.symbol} <span className="stock-company-name">{profile.company_name}</span></h1>
          <p className="stock-meta">{profile.sector} • {profile.industry} • {profile.exchange}</p>
        </div>
        <div className="stock-price-header">
          <span className="stock-current-price">{price.current_price != null ? `$${price.current_price.toFixed(2)}` : 'N/A'}</span>
          {priceChange != null && (
            <span className={`stock-price-change ${priceChange >= 0 ? 'text-positive' : 'text-negative'}`}>
              {priceChange >= 0 ? '+' : ''}{priceChange.toFixed(2)} ({priceChangePercent?.toFixed(2)}%)
            </span>
          )}
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="tab-bar">
        <button className={`tab-btn ${activeTab === 'overview' ? 'active' : ''}`} onClick={() => setActiveTab('overview')}>Overview</button>
        <button className={`tab-btn ${activeTab === 'financials' ? 'active' : ''}`} onClick={() => setActiveTab('financials')}>Financials</button>
        <button className={`tab-btn ${activeTab === 'statistics' ? 'active' : ''}`} onClick={() => setActiveTab('statistics')}>Statistics</button>
        <button className={`tab-btn ${activeTab === 'dividends' ? 'active' : ''}`} onClick={() => setActiveTab('dividends')}>Dividends</button>
        <button className={`tab-btn ${activeTab === 'insider' ? 'active' : ''}`} onClick={() => setActiveTab('insider')}>Insider & Earnings</button>
        <button className={`tab-btn ${activeTab === 'profile' ? 'active' : ''}`} onClick={() => setActiveTab('profile')}>Profile</button>
        <button className={`tab-btn ${activeTab === 'chart' ? 'active' : ''}`} onClick={() => setActiveTab('chart')}>Chart →</button>
      </div>

      {/* ===== Overview Tab ===== */}
      {activeTab === 'overview' && (
        <div className="stock-overview">
          <div className="stock-overview-layout">
            {/* Left: Key Metrics Table */}
            <div className="stock-key-metrics">
              <table className="metrics-table">
                <tbody>
                  <tr><td>Market Cap</td><td>{price.market_cap ? `$${(price.market_cap / 1e9).toFixed(2)}B` : 'N/A'}</td><td>Volume</td><td>{price.volume?.toLocaleString() ?? 'N/A'}</td></tr>
                  <tr><td>Revenue (ttm)</td><td>{price.total_revenue ? `$${(price.total_revenue / 1e9).toFixed(2)}B` : 'N/A'}</td><td>Open</td><td>{price.open ? `$${price.open.toFixed(2)}` : 'N/A'}</td></tr>
                  <tr><td>Net Income</td><td>{price.net_income ? `$${(price.net_income / 1e9).toFixed(2)}B` : 'N/A'}</td><td>Previous Close</td><td>{price.previous_close ? `$${price.previous_close.toFixed(2)}` : 'N/A'}</td></tr>
                  <tr><td>EPS</td><td>{valuation.trailing_eps?.toFixed(2) ?? 'N/A'}</td><td>Day Range</td><td>{price.day_low && price.day_high ? `${price.day_low.toFixed(2)} - ${price.day_high.toFixed(2)}` : 'N/A'}</td></tr>
                  <tr><td>Shares Out</td><td>{price.shares_outstanding ? `${(price.shares_outstanding / 1e9).toFixed(2)}B` : 'N/A'}</td><td>52-Week Range</td><td>{price.fifty_two_week_low && price.fifty_two_week_high ? `${price.fifty_two_week_low.toFixed(2)} - ${price.fifty_two_week_high.toFixed(2)}` : 'N/A'}</td></tr>
                  <tr><td>PE Ratio</td><td>{valuation.pe_trailing?.toFixed(2) ?? 'N/A'}</td><td>Beta</td><td>{price.beta?.toFixed(2) ?? 'N/A'}</td></tr>
                  <tr><td>Forward PE</td><td>{valuation.pe_forward?.toFixed(2) ?? 'N/A'}</td><td>Analysts</td><td><span className={`recommendation-badge rec-${(analysts?.recommendation ?? '').toLowerCase()}`}>{analysts?.recommendation?.toUpperCase() ?? 'N/A'}</span></td></tr>
                  <tr><td>Dividend</td><td>{dividends.dividend_rate ? `$${dividends.dividend_rate.toFixed(2)}` : 'N/A'}</td><td>Price Target</td><td>{analysts?.target_mean_price ? <span className={analysts.target_mean_price > (price.current_price ?? 0) ? 'text-positive' : 'text-negative'}>${analysts.target_mean_price.toFixed(2)} ({((analysts.target_mean_price / (price.current_price || 1) - 1) * 100).toFixed(1)}%)</span> : 'N/A'}</td></tr>
                </tbody>
              </table>
            </div>
            {/* Right: Mini Chart */}
            <div className="stock-mini-chart">
              {chartData.length > 0 ? (
                <ResponsiveContainer width="100%" height={200}>
                  <AreaChart data={chartData.slice(-60)}>
                    <defs>
                      <linearGradient id="colorClose" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#22c55e" stopOpacity={0.3}/>
                        <stop offset="95%" stopColor="#22c55e" stopOpacity={0}/>
                      </linearGradient>
                    </defs>
                    <XAxis dataKey="date" hide />
                    <YAxis domain={['auto', 'auto']} hide />
                    <Tooltip formatter={(v: any) => [`$${Number(v).toFixed(2)}`, 'Price']} />
                    <Area type="monotone" dataKey="close" stroke="#22c55e" fill="url(#colorClose)" strokeWidth={2} />
                  </AreaChart>
                </ResponsiveContainer>
              ) : <p className="loading-text">Loading chart...</p>}
            </div>
          </div>
        </div>
      )}

      {/* ===== Financials Tab ===== */}
      {activeTab === 'financials' && (
        <FinancialsTab financials={financials} />
      )}

      {/* ===== Statistics Tab ===== */}
      {activeTab === 'statistics' && (
        <div className="stock-statistics">
          <div className="stock-section">
            <h3>Valuation Ratios</h3>
            <div className="stock-stats-grid">
              <StatCard label="P/E (Trailing)" value={valuation.pe_trailing?.toFixed(2) ?? 'N/A'} />
              <StatCard label="P/E (Forward)" value={valuation.pe_forward?.toFixed(2) ?? 'N/A'} />
              <StatCard label="PEG Ratio" value={valuation.peg_ratio?.toFixed(2) ?? 'N/A'} />
              <StatCard label="Price/Book" value={valuation.price_to_book?.toFixed(2) ?? 'N/A'} />
              <StatCard label="Price/Sales" value={valuation.price_to_sales?.toFixed(2) ?? 'N/A'} />
              <StatCard label="EV/Revenue" value={valuation.ev_to_revenue?.toFixed(2) ?? 'N/A'} />
              <StatCard label="EV/EBITDA" value={valuation.ev_to_ebitda?.toFixed(2) ?? 'N/A'} />
            </div>
          </div>
          <div className="stock-section">
            <h3>Profitability & Growth</h3>
            <div className="stock-stats-grid">
              <StatCard label="Profit Margin" value={profitability.profit_margins != null ? `${(profitability.profit_margins * 100).toFixed(2)}%` : 'N/A'} />
              <StatCard label="Operating Margin" value={profitability.operating_margins != null ? `${(profitability.operating_margins * 100).toFixed(2)}%` : 'N/A'} />
              <StatCard label="Gross Margin" value={profitability.gross_margins != null ? `${(profitability.gross_margins * 100).toFixed(2)}%` : 'N/A'} />
              <StatCard label="ROE" value={profitability.return_on_equity != null ? `${(profitability.return_on_equity * 100).toFixed(2)}%` : 'N/A'} />
              <StatCard label="ROA" value={profitability.return_on_assets != null ? `${(profitability.return_on_assets * 100).toFixed(2)}%` : 'N/A'} />
              <StatCard label="Revenue Growth" value={profitability.revenue_growth != null ? `${(profitability.revenue_growth * 100).toFixed(2)}%` : 'N/A'} />
              <StatCard label="Earnings Growth" value={profitability.earnings_growth != null ? `${(profitability.earnings_growth * 100).toFixed(2)}%` : 'N/A'} />
            </div>
          </div>
          <div className="stock-section">
            <h3>Short Selling Information</h3>
            <div className="stock-stats-grid">
              <StatCard label="Short Ratio" value={short_info.short_ratio?.toFixed(2) ?? 'N/A'} />
              <StatCard label="Short % of Float" value={short_info.short_percent_of_float != null ? `${(short_info.short_percent_of_float * 100).toFixed(2)}%` : 'N/A'} />
              <StatCard label="Shares Short" value={short_info.shares_short?.toLocaleString() ?? 'N/A'} />
            </div>
          </div>
          <div className="stock-section">
            <h3>Price Statistics</h3>
            <div className="stock-stats-grid">
              <StatCard label="52W High" value={price.fifty_two_week_high ? `$${price.fifty_two_week_high.toFixed(2)}` : 'N/A'} />
              <StatCard label="52W Low" value={price.fifty_two_week_low ? `$${price.fifty_two_week_low.toFixed(2)}` : 'N/A'} />
              <StatCard label="50-Day Avg" value={price.fifty_day_average ? `$${price.fifty_day_average.toFixed(2)}` : 'N/A'} />
              <StatCard label="200-Day Avg" value={price.two_hundred_day_average ? `$${price.two_hundred_day_average.toFixed(2)}` : 'N/A'} />
              <StatCard label="Avg Volume" value={price.average_volume?.toLocaleString() ?? 'N/A'} />
            </div>
          </div>
        </div>
      )}

      {/* ===== Dividends Tab ===== */}
      {activeTab === 'dividends' && (
        <div className="stock-dividends-tab">
          <div className="stock-section">
            <h3>Dividend Summary</h3>
            <div className="stock-stats-grid">
              <StatCard label="Dividend Rate" value={dividends.dividend_rate ? `$${dividends.dividend_rate.toFixed(2)}` : 'N/A'} />
              <StatCard label="Dividend Yield" value={dividends.dividend_yield != null ? `${dividends.dividend_yield.toFixed(2)}%` : 'N/A'} />
              <StatCard label="Payout Ratio" value={dividends.payout_ratio != null ? `${(dividends.payout_ratio * 100).toFixed(1)}%` : 'N/A'} />
            </div>
          </div>
          {dividend_history.length > 0 && (
            <>
              <div className="financial-chart-section">
                <h4>Dividend History</h4>
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={dividend_history}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                    <XAxis dataKey="date" tickFormatter={(v: string) => v?.slice(0, 7)} stroke="#94a3b8" fontSize={11} />
                    <YAxis stroke="#94a3b8" />
                    <Tooltip formatter={(v: any) => [`$${Number(v).toFixed(4)}`, 'Dividend']} />
                    <Bar dataKey="amount" fill="#22c55e" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <div className="table-container">
                <table className="data-table" aria-label="Dividend history">
                  <thead><tr><th scope="col">Date</th><th scope="col" className="number-col">Amount per Share</th></tr></thead>
                  <tbody>
                    {dividend_history.slice().reverse().map((d, i) => (
                      <tr key={i}><td>{d.date}</td><td className="number-cell">${d.amount?.toFixed(4) ?? '—'}</td></tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
          {dividend_history.length === 0 && (
            <div className="empty-state"><p>No dividend history available for this stock.</p></div>
          )}
        </div>
      )}

      {/* ===== Profile Tab ===== */}
      {activeTab === 'profile' && (
        <div className="stock-profile-tab">
          <div className="stock-description">
            <h3>About {profile.company_name}</h3>
            <p>{profile.description || 'No description available.'}</p>
          </div>
          <div className="stock-stats-grid" style={{ marginTop: '1rem' }}>
            <StatCard label="Sector" value={profile.sector ?? 'N/A'} />
            <StatCard label="Industry" value={profile.industry ?? 'N/A'} />
            <StatCard label="Country" value={profile.country ?? 'N/A'} />
            <StatCard label="Employees" value={profile.employees?.toLocaleString() ?? 'N/A'} />
            <StatCard label="Exchange" value={profile.exchange ?? 'N/A'} />
            <StatCard label="Currency" value={profile.currency ?? 'N/A'} />
          </div>
          {profile.website && (
            <p style={{ marginTop: '1rem' }}><a href={profile.website} target="_blank" rel="noopener noreferrer" className="text-primary">{profile.website}</a></p>
          )}

          {/* Analyst Recommendations */}
          {((analysts?.upgrades_downgrades?.length > 0) || (analysts?.recommendations?.length > 0)) && (() => {
            const rawRecs = analysts.upgrades_downgrades?.length > 0 ? analysts.upgrades_downgrades : analysts.recommendations;
            // Remove duplicates (same date + firm) and sort by date desc
            const seen = new Set<string>();
            const deduped = rawRecs.filter((r: any) => {
              const key = `${r.date}|${r.firm}|${r.to_grade}`;
              if (seen.has(key)) return false;
              seen.add(key);
              return true;
            });
            const sorted = deduped.slice().sort((a: any, b: any) => (b.date || '').localeCompare(a.date || ''));
            return (
              <div className="stock-section" style={{ marginTop: '1.5rem' }}>
                <h3>Analyst Recommendations — {profile.symbol} ({profile.company_name})</h3>
                <div className="stock-stats-grid">
                  <StatCard label="Consensus" value={analysts.recommendation ?? 'N/A'} />
                  <StatCard label="Target (Mean)" value={analysts.target_mean_price ? `$${analysts.target_mean_price.toFixed(2)}` : 'N/A'} />
                  <StatCard label="Target (High)" value={analysts.target_high_price ? `$${analysts.target_high_price.toFixed(2)}` : 'N/A'} />
                  <StatCard label="Target (Low)" value={analysts.target_low_price ? `$${analysts.target_low_price.toFixed(2)}` : 'N/A'} />
                  <StatCard label="# of Analysts" value={analysts.number_of_analysts?.toString() ?? 'N/A'} />
                </div>
                <div className="table-container" style={{ marginTop: '1rem' }}>
                  <table className="data-table" aria-label="Analyst recommendations">
                    <thead><tr><th>Date</th><th>Firm</th><th>Action</th><th>To Grade</th><th>From Grade</th></tr></thead>
                    <tbody>
                      {sorted.map((r: any, i: number) => (
                        <tr key={i}>
                          <td>{r.date}</td>
                          <td>{r.firm || '—'}</td>
                          <td><span className={`badge ${getActionBadgeClass(r.action)}`}>{r.action || '—'}</span></td>
                          <td><span className={`badge ${getGradeBadgeClass(r.to_grade)}`}>{r.to_grade || '—'}</span></td>
                          <td><span className={`badge ${getGradeBadgeClass(r.from_grade)}`}>{r.from_grade || '—'}</span></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            );
          })()}
        </div>
      )}

      {/* ===== Insider & Earnings Tab ===== */}
      {activeTab === 'insider' && (
        <div className="stock-insider-tab">
          {/* Earnings */}
          {data.earnings?.earnings_dates?.length > 0 && (
            <div className="stock-section">
              <h3>Earnings History & Upcoming</h3>
              <div className="table-container">
                <table className="data-table" aria-label="Earnings dates">
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th className="number-col">EPS Estimate</th>
                      <th className="number-col">Reported EPS</th>
                      <th className="number-col">Surprise %</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.earnings.earnings_dates.map((e: any, i: number) => (
                      <tr key={i}>
                        <td>{e.date}</td>
                        <td className="number-cell">{e.eps_estimate != null ? `$${e.eps_estimate.toFixed(2)}` : '—'}</td>
                        <td className="number-cell">{e.reported_eps != null ? `$${e.reported_eps.toFixed(2)}` : '—'}</td>
                        <td className="number-cell">
                          {e.surprise_pct != null ? (
                            <span className={e.surprise_pct >= 0 ? 'text-positive' : 'text-negative'}>
                              {e.surprise_pct >= 0 ? '+' : ''}{e.surprise_pct.toFixed(2)}%
                            </span>
                          ) : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Major Holders */}
          {data.insider?.major_holders?.length > 0 && (
            <div className="stock-section">
              <h3>Major Holders</h3>
              <div className="stock-stats-grid">
                {data.insider.major_holders.map((h: any, i: number) => (
                  <StatCard key={i} label={h.label} value={h.value} />
                ))}
              </div>
            </div>
          )}

          {/* Institutional Holders */}
          {data.insider?.institutional_holders?.length > 0 && (
            <div className="stock-section">
              <h3>Top Institutional Holders</h3>
              <div className="table-container">
                <table className="data-table" aria-label="Institutional holders">
                  <thead>
                    <tr>
                      <th>Holder</th>
                      <th className="number-col">Shares</th>
                      <th className="number-col">% Out</th>
                      <th className="number-col">Value</th>
                      <th>Date Reported</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.insider.institutional_holders.map((h: any, i: number) => (
                      <tr key={i}>
                        <td>{h.holder}</td>
                        <td className="number-cell">{h.shares ? Math.round(h.shares).toLocaleString() : '—'}</td>
                        <td className="number-cell">{h.pct_out != null ? `${(h.pct_out * 100).toFixed(2)}%` : '—'}</td>
                        <td className="number-cell">{h.value ? `$${(h.value / 1e6).toFixed(0)}M` : '—'}</td>
                        <td>{h.date_reported || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Insider Transactions */}
          {data.insider?.insider_transactions?.length > 0 && (
            <div className="stock-section">
              <h3>Recent Insider Transactions</h3>
              <div className="table-container">
                <table className="data-table" aria-label="Insider transactions">
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th>Insider</th>
                      <th>Position</th>
                      <th>Transaction</th>
                      <th className="number-col">Shares</th>
                      <th className="number-col">Value</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.insider.insider_transactions.map((t: any, i: number) => {
                      const txType = (t.transaction || '').toLowerCase();
                      const isSale = txType.includes('sale') || txType.includes('sell') || txType.includes('disposition');
                      const isPurchase = txType.includes('purchase') || txType.includes('buy') || txType.includes('acquisition') || txType.includes('exercise');
                      const badgeClass = isSale ? 'badge-grade-sell' : isPurchase ? 'badge-grade-buy' : 'badge-muted';
                      const label = t.transaction || (isSale ? 'Sale' : isPurchase ? 'Purchase' : '—');
                      return (
                        <tr key={i}>
                          <td>{t.date || '—'}</td>
                          <td>{t.insider || '—'}</td>
                          <td>{t.position || '—'}</td>
                          <td><span className={`badge ${badgeClass}`}>{label}</span></td>
                          <td className="number-cell">{t.shares ? Math.round(t.shares).toLocaleString() : '—'}</td>
                          <td className="number-cell">{t.value ? `$${(t.value / 1e6).toFixed(2)}M` : '—'}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Empty state */}
          {!data.earnings?.earnings_dates?.length && !data.insider?.major_holders?.length && !data.insider?.institutional_holders?.length && !data.insider?.insider_transactions?.length && (
            <div className="empty-state"><p>No insider or earnings data available for this stock.</p></div>
          )}
        </div>
      )}

      {/* ===== Chart Tab ===== */}
      {activeTab === 'chart' && (
        <div className="stock-chart-tab">
          <div className="chart-period-selector">
            {(['1d', '5d', '1mo', '3mo', '6mo', '1y', '5y', 'max'] as ChartPeriod[]).map((p) => (
              <button
                key={p}
                className={`btn btn-sm ${chartPeriod === p ? 'btn-primary' : 'btn-secondary'}`}
                onClick={() => setChartPeriod(p)}
              >
                {p.toUpperCase()}
              </button>
            ))}
          </div>
          {chartLoading ? (
            <p className="loading-text">Loading chart data...</p>
          ) : chartData.length > 0 ? (
            <div className="stock-full-chart">
              <ResponsiveContainer width="100%" height={400}>
                <AreaChart data={chartData}>
                  <defs>
                    <linearGradient id="colorPrice" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis dataKey="date" tickFormatter={(v: string) => v?.slice(5, 10)} stroke="#94a3b8" fontSize={11} />
                  <YAxis domain={['auto', 'auto']} stroke="#94a3b8" tickFormatter={(v: number) => `$${v.toFixed(0)}`} />
                  <Tooltip formatter={(v: any) => [`$${Number(v).toFixed(2)}`, 'Price']} labelFormatter={(l) => `Date: ${l}`} />
                  <Area type="monotone" dataKey="close" stroke="#3b82f6" fill="url(#colorPrice)" strokeWidth={2} />
                </AreaChart>
              </ResponsiveContainer>
              {/* Volume chart below */}
              <ResponsiveContainer width="100%" height={100}>
                <BarChart data={chartData}>
                  <XAxis dataKey="date" hide />
                  <YAxis hide />
                  <Tooltip formatter={(v: any) => [Number(v).toLocaleString(), 'Volume']} />
                  <Bar dataKey="volume" fill="#475569" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="empty-state"><p>No chart data available for this period.</p></div>
          )}
        </div>
      )}

    </div>
  );
}

// ===== Financials Tab Component =====

type FinSubTab = 'income' | 'balance' | 'cashflow';
type FinPeriod = 'annual' | 'quarterly';

function FinancialsTab({ financials }: { financials: StockData['financials'] }) {
  const [subTab, setSubTab] = useState<FinSubTab>('income');
  const [period, setPeriod] = useState<FinPeriod>('annual');

  const getData = () => {
    if (period === 'quarterly') {
      if (subTab === 'income') return (financials as any).quarterly_income ?? [];
      if (subTab === 'balance') return (financials as any).quarterly_balance ?? [];
      return (financials as any).quarterly_cashflow ?? [];
    }
    if (subTab === 'income') return financials.income_statement;
    if (subTab === 'balance') return financials.balance_sheet;
    return financials.cash_flow;
  };

  const data = getData();
  const chartItems = data.slice().reverse();

  const fmtNum = (v: number): string => {
    if (Math.abs(v) >= 1e9) return `$${(v / 1e9).toFixed(1)}B`;
    if (Math.abs(v) >= 1e6) return `$${(v / 1e6).toFixed(0)}M`;
    return `$${(v / 1e3).toFixed(0)}K`;
  };

  return (
    <div className="stock-financials">
      <div className="financials-controls">
        <div className="tab-bar tab-bar-secondary">
          <button className={`tab-btn ${subTab === 'income' ? 'active' : ''}`} onClick={() => setSubTab('income')}>Income Statement</button>
          <button className={`tab-btn ${subTab === 'balance' ? 'active' : ''}`} onClick={() => setSubTab('balance')}>Balance Sheet</button>
          <button className={`tab-btn ${subTab === 'cashflow' ? 'active' : ''}`} onClick={() => setSubTab('cashflow')}>Cash Flow</button>
        </div>
        <div className="period-toggle">
          <button className={`btn btn-sm ${period === 'annual' ? 'btn-primary' : 'btn-secondary'}`} onClick={() => setPeriod('annual')}>Annual</button>
          <button className={`btn btn-sm ${period === 'quarterly' ? 'btn-primary' : 'btn-secondary'}`} onClick={() => setPeriod('quarterly')}>Quarterly</button>
        </div>
      </div>

      {/* Chart */}
      {subTab === 'income' && chartItems.length > 0 && (
        <div className="financial-chart-section">
          <h4>Revenue & Net Income ({period === 'quarterly' ? 'Quarterly' : 'Annual'})</h4>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={chartItems} margin={{ top: 10, right: 30, left: 20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="period" tickFormatter={(v: string) => period === 'quarterly' ? v?.slice(2, 7) : v?.slice(0, 4)} stroke="#94a3b8" fontSize={11} />
              <YAxis tickFormatter={(v: number) => fmtNum(v)} stroke="#94a3b8" fontSize={11} />
              <Tooltip formatter={(v: any, name: string) => [fmtNum(Number(v)), name]} labelFormatter={(l) => `Period: ${l}`} />
              <Bar dataKey="Total Revenue" name="Revenue" radius={[4, 4, 0, 0]} fill="#3b82f6" />
              <Bar dataKey="Net Income" name="Net Income" radius={[4, 4, 0, 0]}>
                {chartItems.map((entry: any, idx: number) => (
                  <Cell key={idx} fill={(entry['Net Income'] ?? 0) >= 0 ? '#22c55e' : '#ef4444'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {subTab === 'cashflow' && chartItems.length > 0 && (
        <div className="financial-chart-section">
          <h4>Cash Flow ({period === 'quarterly' ? 'Quarterly' : 'Annual'})</h4>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={chartItems} margin={{ top: 10, right: 30, left: 20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="period" tickFormatter={(v: string) => period === 'quarterly' ? v?.slice(2, 7) : v?.slice(0, 4)} stroke="#94a3b8" fontSize={11} />
              <YAxis tickFormatter={(v: number) => fmtNum(v)} stroke="#94a3b8" fontSize={11} />
              <Tooltip formatter={(v: any, name: string) => [fmtNum(Number(v)), name]} />
              <Bar dataKey="Operating Cash Flow" name="Operating" radius={[4, 4, 0, 0]} fill="#3b82f6" />
              <Bar dataKey="Free Cash Flow" name="Free Cash Flow" radius={[4, 4, 0, 0]}>
                {chartItems.map((entry: any, idx: number) => (
                  <Cell key={idx} fill={(entry['Free Cash Flow'] ?? 0) >= 0 ? '#22c55e' : '#ef4444'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Table */}
      <FinancialTable title={`${subTab === 'income' ? 'Income Statement' : subTab === 'balance' ? 'Balance Sheet' : 'Cash Flow'} (${period})`} data={data} />
    </div>
  );
}

// ===== Helper Functions =====

function getGradeBadgeClass(grade: string | undefined): string {
  if (!grade || grade === '—') return 'badge-muted';
  const g = grade.toLowerCase();
  if (g.includes('buy') || g.includes('outperform') || g.includes('overweight') || g.includes('positive') || g.includes('accumulate')) return 'badge-grade-buy';
  if (g.includes('sell') || g.includes('underperform') || g.includes('underweight') || g.includes('negative') || g.includes('reduce')) return 'badge-grade-sell';
  if (g.includes('hold') || g.includes('neutral') || g.includes('equal') || g.includes('market perform') || g.includes('peer perform') || g.includes('sector perform')) return 'badge-grade-hold';
  return 'badge-muted';
}

function getActionBadgeClass(action: string | undefined): string {
  if (!action || action === '—') return 'badge-muted';
  const a = action.toLowerCase();
  if (a.includes('up') || a.includes('init') || a.includes('reiterate')) return 'badge-action-up';
  if (a.includes('down')) return 'badge-action-down';
  if (a.includes('main')) return 'badge-action-maintain';
  return 'badge-muted';
}

// ===== Helper Components =====

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="stat-card">
      <span className="stat-label">{label}</span>
      <span className="stat-value">{value}</span>
    </div>
  );
}

function FinancialTable({ title, data }: { title: string; data: Record<string, any>[] }) {
  if (!data || data.length === 0) {
    return <div className="empty-state"><p>No {title.toLowerCase()} data available.</p></div>;
  }

  const allKeys = new Set<string>();
  for (const period of data) {
    for (const key of Object.keys(period)) {
      if (key !== 'period') allKeys.add(key);
    }
  }
  const rowKeys = Array.from(allKeys);

  const formatValue = (val: any): string => {
    if (val == null) return '—';
    const num = Number(val);
    if (isNaN(num)) return String(val);
    if (Math.abs(num) >= 1e9) return `$${(num / 1e9).toFixed(2)}B`;
    if (Math.abs(num) >= 1e6) return `$${(num / 1e6).toFixed(2)}M`;
    if (Math.abs(num) >= 1e3) return `$${(num / 1e3).toFixed(2)}K`;
    return `$${num.toFixed(2)}`;
  };

  const getValueColor = (val: any): string => {
    if (val == null) return '';
    const num = Number(val);
    if (isNaN(num) || num === 0) return '';
    return num > 0 ? 'text-positive' : 'text-negative';
  };

  return (
    <div className="table-container">
      <table className="data-table" aria-label={title}>
        <thead>
          <tr>
            <th scope="col">Item</th>
            {data.map((period) => (
              <th key={period.period} scope="col" className="number-col">{period.period?.slice(0, 4) ?? ''}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rowKeys.slice(0, 25).map((key) => (
            <tr key={key}>
              <td>{key.replace(/([A-Z])/g, ' $1').replace(/^./, s => s.toUpperCase())}</td>
              {data.map((period) => (
                <td key={period.period} className={`number-cell ${getValueColor(period[key])}`}>{formatValue(period[key])}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
