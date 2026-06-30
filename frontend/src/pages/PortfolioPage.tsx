import { useCallback, useEffect, useState } from 'react';
import { portfolioApi } from '../api';
import type { PortfolioPosition, PortfolioSummary, SentimentType } from '../types';
import { SentimentType as SentimentEnum } from '../types';
import { formatTHB, formatPercent, formatDateTime, toNum } from '../utils/format';
import { useSortableData } from '../hooks/useSortableData';
import toast from 'react-hot-toast';

/** Format a number or return "N/A" when null/undefined */
function formatNumber(value: number | null | undefined, decimals = 2): string {
  if (value == null) return 'N/A';
  return toNum(value).toLocaleString('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

/** Format currency or return "N/A" */
function formatCurrencyOrNA(value: number | null | undefined): string {
  if (value == null) return 'N/A';
  return formatTHB(value);
}

/** Format percent or return "N/A" */
function formatPercentOrNA(value: number | null | undefined): string {
  if (value == null) return 'N/A';
  return formatPercent(value);
}

/** CSS class for profit/loss coloring */
function plClass(value: number | null | undefined): string {
  if (value == null) return '';
  const n = toNum(value);
  if (n > 0) return 'positive';
  if (n < 0) return 'negative';
  return '';
}

export default function PortfolioPage() {
  const [portfolio, setPortfolio] = useState<PortfolioSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [lastRefresh, setLastRefresh] = useState<string | null>(null);
  const [expandedRow, setExpandedRow] = useState<string | null>(null);

  const fetchPortfolio = useCallback(async () => {
    try {
      const data = await portfolioApi.getSummary();
      setPortfolio(data);
      // Determine the most recent last_refresh from positions
      const refreshTimes = data.positions
        .map((p) => p.last_refresh)
        .filter((t): t is string => t != null);
      if (refreshTimes.length > 0) {
        refreshTimes.sort((a, b) => new Date(b).getTime() - new Date(a).getTime());
        setLastRefresh(refreshTimes[0]);
      }
    } catch {
      // Error handled by axios interceptor
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPortfolio();
  }, [fetchPortfolio]);

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      await portfolioApi.refresh();
      toast.success('Market data refreshed');
      await fetchPortfolio();
    } catch {
      // Error handled by axios interceptor
    } finally {
      setRefreshing(false);
    }
  };

  const handleSentimentChange = async (symbol: string, sentiment: SentimentType | '') => {
    try {
      await portfolioApi.setSentiment(symbol, sentiment);
      // Update local state optimistically
      setPortfolio((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          positions: prev.positions.map((p) =>
            p.stock_symbol === symbol
              ? { ...p, sentiment: sentiment === '' ? null : (sentiment as SentimentType) }
              : p
          ),
        };
      });
    } catch {
      // Error handled by axios interceptor
    }
  };

  const toggleExpandedRow = (symbol: string) => {
    setExpandedRow((prev) => (prev === symbol ? null : symbol));
  };

  if (loading) {
    return (
      <div className="page portfolio-page">
        <h1>Portfolio Summary</h1>
        <p className="loading-text" aria-live="polite">Loading portfolio data...</p>
      </div>
    );
  }

  const positions = portfolio?.positions ?? [];
  const isEmpty = positions.length === 0;

  return (
    <div className="page portfolio-page">
      <div className="portfolio-header">
        <div>
          <h1>Portfolio Summary</h1>
          <p>View your current holdings and market data.</p>
        </div>
        <div className="portfolio-actions">
          {lastRefresh && (
            <span className="last-refresh" aria-label="Last market data refresh time">
              Last refreshed: {formatDateTime(lastRefresh)}
            </span>
          )}
          <button
            className="btn btn-primary"
            onClick={handleRefresh}
            disabled={refreshing}
            aria-label="Refresh market data"
          >
            {refreshing ? 'Refreshing...' : 'Refresh Market Data'}
          </button>
        </div>
      </div>

      {isEmpty ? (
        <EmptyState />
      ) : (
        <PositionsTable
          positions={positions}
          portfolio={portfolio!}
          expandedRow={expandedRow}
          onToggleExpand={toggleExpandedRow}
          onSentimentChange={handleSentimentChange}
        />
      )}
    </div>
  );
}

function EmptyState() {
  return (
    <div className="empty-state" role="status" aria-label="No positions">
      <div className="empty-state-icon">📊</div>
      <h2>No Positions Yet</h2>
      <p>
        You don't have any holdings in your portfolio. Start by adding transactions in
        the Trading Log.
      </p>
    </div>
  );
}

interface PositionsTableProps {
  positions: PortfolioPosition[];
  portfolio: PortfolioSummary;
  expandedRow: string | null;
  onToggleExpand: (symbol: string) => void;
  onSentimentChange: (symbol: string, sentiment: SentimentType | '') => void;
}

function PositionsTable({
  positions,
  portfolio,
  expandedRow,
  onToggleExpand,
  onSentimentChange,
}: PositionsTableProps) {
  const { sortedItems, requestSort, getSortIndicator } = useSortableData(positions);

  return (
    <div className="portfolio-table-container" role="region" aria-label="Portfolio positions">
      <table className="portfolio-table" aria-label="Portfolio positions table">
        <thead>
          <tr>
            <th scope="col" className="col-expand"></th>
            <th scope="col" className="col-symbol sortable-th" onClick={() => requestSort('stock_symbol')}>Symbol{getSortIndicator('stock_symbol')}</th>
            <th scope="col" className="col-name">Company</th>
            <th scope="col" className="col-qty sortable-th" onClick={() => requestSort('quantity')}>Qty{getSortIndicator('quantity')}</th>
            <th scope="col" className="col-cost sortable-th" onClick={() => requestSort('avg_cost')}>Avg Cost{getSortIndicator('avg_cost')}</th>
            <th scope="col" className="col-total-cost sortable-th" onClick={() => requestSort('total_cost')}>Total Cost{getSortIndicator('total_cost')}</th>
            <th scope="col" className="col-price sortable-th" onClick={() => requestSort('current_price')}>Current Price{getSortIndicator('current_price')}</th>
            <th scope="col" className="col-market-value sortable-th" onClick={() => requestSort('market_value')}>Market Value{getSortIndicator('market_value')}</th>
            <th scope="col" className="col-pl sortable-th" onClick={() => requestSort('unrealized_pl')}>Unrealized P/L{getSortIndicator('unrealized_pl')}</th>
            <th scope="col" className="col-roi sortable-th" onClick={() => requestSort('roi_percent')}>ROI%{getSortIndicator('roi_percent')}</th>
            <th scope="col" className="col-alloc sortable-th" onClick={() => requestSort('allocation_percent')}>Alloc%{getSortIndicator('allocation_percent')}</th>
            <th scope="col" className="col-sentiment">Sentiment</th>
          </tr>
        </thead>
        <tbody>
          {sortedItems.map((position) => (
            <PositionRow
              key={position.stock_symbol}
              position={position}
              isExpanded={expandedRow === position.stock_symbol}
              onToggleExpand={onToggleExpand}
              onSentimentChange={onSentimentChange}
            />
          ))}
        </tbody>
        <tfoot>
          <SummaryRow portfolio={portfolio} />
        </tfoot>
      </table>
    </div>
  );
}

interface PositionRowProps {
  position: PortfolioPosition;
  isExpanded: boolean;
  onToggleExpand: (symbol: string) => void;
  onSentimentChange: (symbol: string, sentiment: SentimentType | '') => void;
}

function PositionRow({
  position,
  isExpanded,
  onToggleExpand,
  onSentimentChange,
}: PositionRowProps) {
  return (
    <>
      <tr className={isExpanded ? 'row-expanded' : ''}>
        <td className="col-expand">
          <button
            className="expand-btn"
            onClick={() => onToggleExpand(position.stock_symbol)}
            aria-expanded={isExpanded}
            aria-label={`${isExpanded ? 'Collapse' : 'Expand'} details for ${position.stock_symbol}`}
          >
            {isExpanded ? '▾' : '▸'}
          </button>
        </td>
        <td className="col-symbol">
          <strong>{position.stock_symbol}</strong>
        </td>
        <td className="col-name">{position.company_name ?? 'N/A'}</td>
        <td className="col-qty">{toNum(position.quantity) % 1 === 0 ? toNum(position.quantity).toLocaleString() : toNum(position.quantity).toFixed(4)}</td>
        <td className="col-cost">{formatTHB(position.avg_cost)}</td>
        <td className="col-total-cost">{formatTHB(position.total_cost)}</td>
        <td className="col-price">{formatCurrencyOrNA(position.current_price)}</td>
        <td className="col-market-value">{formatCurrencyOrNA(position.market_value)}</td>
        <td className={`col-pl ${plClass(position.unrealized_pl)}`}>
          {formatCurrencyOrNA(position.unrealized_pl)}
        </td>
        <td className={`col-roi ${plClass(position.roi_percent)}`}>
          {formatPercentOrNA(position.roi_percent)}
        </td>
        <td className="col-alloc">{formatPercent(position.allocation_percent)}</td>
        <td className="col-sentiment">
          <select
            value={position.sentiment ?? ''}
            onChange={(e) =>
              onSentimentChange(
                position.stock_symbol,
                e.target.value as SentimentType | ''
              )
            }
            aria-label={`Sentiment for ${position.stock_symbol}`}
            className={`sentiment-select ${position.sentiment === SentimentEnum.BULL ? 'bull' : ''} ${position.sentiment === SentimentEnum.BEAR ? 'bear' : ''}`}
          >
            <option value="">--</option>
            <option value={SentimentEnum.BULL}>🐂 Bull</option>
            <option value={SentimentEnum.BEAR}>🐻 Bear</option>
          </select>
        </td>
      </tr>
      {isExpanded && <ExpandedDetails position={position} />}
    </>
  );
}

function ExpandedDetails({ position }: { position: PortfolioPosition }) {
  return (
    <tr className="expanded-details-row">
      <td colSpan={12}>
        <div className="expanded-details" aria-label={`Additional details for ${position.stock_symbol}`}>
          <div className="detail-group">
            <h4>Market Data</h4>
            <dl className="detail-list">
              <div className="detail-item">
                <dt>Sector</dt>
                <dd>{position.sector ?? 'N/A'}</dd>
              </div>
              <div className="detail-item">
                <dt>Industry</dt>
                <dd>{position.industry ?? 'N/A'}</dd>
              </div>
              <div className="detail-item">
                <dt>P/E (Trailing)</dt>
                <dd>{formatNumber(position.pe_trailing)}</dd>
              </div>
              <div className="detail-item">
                <dt>P/E (Forward)</dt>
                <dd>{formatNumber(position.pe_forward)}</dd>
              </div>
              <div className="detail-item">
                <dt>Beta</dt>
                <dd>{formatNumber(position.beta)}</dd>
              </div>
              <div className="detail-item">
                <dt>Dividend Yield</dt>
                <dd>{position.dividend_yield != null ? formatPercent(toNum(position.dividend_yield)) : 'N/A'}</dd>
              </div>
            </dl>
          </div>
          <div className="detail-group">
            <h4>Price Range</h4>
            <dl className="detail-list">
              <div className="detail-item">
                <dt>Previous Close</dt>
                <dd>{formatCurrencyOrNA(position.previous_close)}</dd>
              </div>
              <div className="detail-item">
                <dt>Day High</dt>
                <dd>{formatCurrencyOrNA(position.day_high)}</dd>
              </div>
              <div className="detail-item">
                <dt>Day Low</dt>
                <dd>{formatCurrencyOrNA(position.day_low)}</dd>
              </div>
              <div className="detail-item">
                <dt>52-Week Low</dt>
                <dd>{formatCurrencyOrNA(position.fifty_two_week_low)}</dd>
              </div>
              <div className="detail-item">
                <dt>52-Week High</dt>
                <dd>{formatCurrencyOrNA(position.fifty_two_week_high)}</dd>
              </div>
            </dl>
          </div>
          <div className="detail-group">
            <h4>Fundamentals</h4>
            <dl className="detail-list">
              <div className="detail-item">
                <dt>Market Cap</dt>
                <dd>{position.market_cap != null ? `฿${(toNum(position.market_cap) / 1_000_000).toFixed(1)}M` : 'N/A'}</dd>
              </div>
              <div className="detail-item">
                <dt>Price/Book</dt>
                <dd>{formatNumber(position.price_to_book)}</dd>
              </div>
              <div className="detail-item">
                <dt>Avg Volume</dt>
                <dd>{position.average_volume != null ? toNum(position.average_volume).toLocaleString('en-US') : 'N/A'}</dd>
              </div>
              <div className="detail-item">
                <dt>Last Refresh</dt>
                <dd>{formatDateTime(position.last_refresh)}</dd>
              </div>
            </dl>
          </div>
        </div>
      </td>
    </tr>
  );
}

function SummaryRow({ portfolio }: { portfolio: PortfolioSummary }) {
  return (
    <tr className="summary-row">
      <td></td>
      <td colSpan={4} className="summary-label">
        <strong>Total ({portfolio.positions.length} positions)</strong>
      </td>
      <td className="col-total-cost">
        <strong>{formatTHB(portfolio.total_cost)}</strong>
      </td>
      <td></td>
      <td className="col-market-value">
        <strong>{formatCurrencyOrNA(portfolio.total_market_value)}</strong>
      </td>
      <td className={`col-pl ${plClass(portfolio.total_unrealized_pl)}`}>
        <strong>{formatCurrencyOrNA(portfolio.total_unrealized_pl)}</strong>
      </td>
      <td className={`col-roi ${plClass(portfolio.total_roi_percent)}`}>
        <strong>{formatPercentOrNA(portfolio.total_roi_percent)}</strong>
      </td>
      <td className="col-alloc">
        <strong>100.00%</strong>
      </td>
      <td></td>
    </tr>
  );
}
