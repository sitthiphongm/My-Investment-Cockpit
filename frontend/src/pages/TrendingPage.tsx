import { useCallback, useEffect, useState } from 'react';
import { trendingApi, watchlistApi } from '../api';
import type { TrendingStock, TrendingData } from '../types';
import { formatTHB, formatPercent, toNum } from '../utils/format';
import { useSortableData } from '../hooks/useSortableData';
import { usePagination } from '../hooks/usePagination';
import Pagination from '../components/Pagination';
import toast from 'react-hot-toast';

type Category = 'gainers' | 'losers' | 'most_active';

export default function TrendingPage() {
  const [data, setData] = useState<TrendingData | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<Category>('gainers');
  const [watchedSymbols, setWatchedSymbols] = useState<string[]>([]);

  const fetchData = useCallback(async () => {
    try {
      const [trending, watchlist] = await Promise.all([
        trendingApi.get(),
        watchlistApi.list(),
      ]);
      setData(trending);
      setWatchedSymbols((watchlist ?? []).map((w: { stock_symbol: string }) => w.stock_symbol));
    } catch { /* */ } finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const addToWatchlist = async (stock: TrendingStock) => {
    const sym = stock.symbol || stock.stock_symbol || '';
    try {
      await watchlistApi.create({ stock_symbol: sym });
      toast.success(`${sym} added to watchlist`, { duration: 4000 });
      setWatchedSymbols((prev) => [...prev, sym]);
    } catch { /* */ }
  };

  const stocks = data ? (data[activeTab] || []) : [];
  const { sortedItems, requestSort, getSortIndicator } = useSortableData(stocks);
  const { paginatedItems, currentPage, totalItems, itemsPerPage, setPage, setPerPage } = usePagination(sortedItems, { defaultPerPage: 20 });

  if (loading) {
    return (<div className="page trending-page"><h1>Trending Stocks</h1><p className="loading-text">Loading...</p></div>);
  }

  return (
    <div className="page trending-page">
      <h1>Trending Stocks</h1>
      <p>Discover top gainers, losers, and most active stocks.</p>

      <div className="tab-bar">
        <button className={`tab-btn ${activeTab === 'gainers' ? 'active' : ''}`} onClick={() => setActiveTab('gainers')}>📈 Gainers</button>
        <button className={`tab-btn ${activeTab === 'losers' ? 'active' : ''}`} onClick={() => setActiveTab('losers')}>📉 Losers</button>
        <button className={`tab-btn ${activeTab === 'most_active' ? 'active' : ''}`} onClick={() => setActiveTab('most_active')}>🔥 Most Active</button>
      </div>

      {sortedItems.length === 0 ? (
        <div className="empty-state"><div className="empty-state-icon">📊</div><h2>No Trending Data</h2><p>Try refreshing later.</p></div>
      ) : (
        <div className="table-container">
          <table className="data-table trending-table" aria-label={`Trending ${activeTab} stocks`}>
            <colgroup>
              <col style={{ width: '18%' }} />
              <col style={{ width: '10%' }} />
              <col style={{ width: '8%' }} />
              <col style={{ width: '8%' }} />
              <col style={{ width: '10%' }} />
              <col style={{ width: '8%' }} />
              <col style={{ width: '30%' }} />
              <col style={{ width: '8%' }} />
            </colgroup>
            <thead>
              <tr>
                <th scope="col" className="sortable-th" onClick={() => requestSort('symbol')}>Stock{getSortIndicator('symbol')}</th>
                <th scope="col">Sector</th>
                <th scope="col" className="sortable-th number-col" onClick={() => requestSort('current_price')}>Price{getSortIndicator('current_price')}</th>
                <th scope="col" className="sortable-th number-col" onClick={() => requestSort('day_change_percent')}>Change{getSortIndicator('day_change_percent')}</th>
                <th scope="col" className="sortable-th number-col" onClick={() => requestSort('volume')}>Volume{getSortIndicator('volume')}</th>
                <th scope="col" className="sortable-th number-col" onClick={() => requestSort('market_cap')}>Mkt Cap{getSortIndicator('market_cap')}</th>
                <th scope="col">Reason</th>
                <th scope="col">Action</th>
              </tr>
            </thead>
            <tbody>
              {paginatedItems.map((stock) => {
                const sym = stock.symbol || stock.stock_symbol || '';
                const alreadyWatched = watchedSymbols.includes(sym);
                const pct = toNum(stock.day_change_percent);
                const vol = toNum(stock.volume);
                const reason = (stock as any).reason || '';
                const sector = (stock as any).sector || '';
                const mktCap = toNum((stock as any).market_cap);

                // Parse reason into tag + text
                const { tag, text } = parseReason(reason);

                return (
                  <tr key={sym}>
                    {/* Symbol + Company stacked */}
                    <td className="stock-name-cell">
                      <a href={`https://stockanalysis.com/stocks/${sym.toLowerCase()}/`} target="_blank" rel="noopener noreferrer" className="stock-symbol-link">{sym}</a>
                      <span className="stock-company-sub">{stock.company_name || ''}</span>
                    </td>
                    {/* Sector tag */}
                    <td>{sector ? <span className="sector-tag">{sector}</span> : <span className="na-text">—</span>}</td>
                    {/* Price */}
                    <td className="number-cell">{stock.current_price != null ? `$${toNum(stock.current_price).toFixed(2)}` : 'N/A'}</td>
                    {/* Day Change badge */}
                    <td className="number-cell">
                      <span className={`change-badge ${pct >= 0 ? 'change-positive' : 'change-negative'}`}>
                        {pct >= 0 ? '+' : ''}{pct.toFixed(2)}%
                      </span>
                    </td>
                    {/* Volume with ratio */}
                    <td className="number-cell">
                      <span className="vol-primary">{formatVolume(vol)}</span>
                      {reason.includes('x avg') && (
                        <span className="vol-ratio">{extractVolRatio(reason)}</span>
                      )}
                    </td>
                    {/* Market Cap */}
                    <td className="number-cell">{mktCap > 0 ? formatMarketCap(mktCap) : 'N/A'}</td>
                    {/* Reason with tag */}
                    <td className="reason-cell-v2">
                      {tag && <span className="reason-tag">{tag}</span>}
                      <span className="reason-text">{text}</span>
                    </td>
                    {/* Action */}
                    <td>
                      {alreadyWatched ? (
                        <span className="badge badge-muted">On Watchlist</span>
                      ) : (
                        <button className="btn btn-sm btn-primary" onClick={() => addToWatchlist(stock)} aria-label={`Add ${sym}`}>+ Watchlist</button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <Pagination currentPage={currentPage} totalItems={totalItems} itemsPerPage={itemsPerPage} onPageChange={setPage} onItemsPerPageChange={setPerPage} />
        </div>
      )}
    </div>
  );
}


// ===== Helper Functions =====

function formatVolume(vol: number): string {
  if (vol >= 1e9) return `${(vol / 1e9).toFixed(1)}B`;
  if (vol >= 1e6) return `${(vol / 1e6).toFixed(1)}M`;
  if (vol >= 1e3) return `${(vol / 1e3).toFixed(0)}K`;
  return vol.toLocaleString();
}

function formatMarketCap(cap: number): string {
  if (cap >= 1e12) return `$${(cap / 1e12).toFixed(1)}T`;
  if (cap >= 1e9) return `$${(cap / 1e9).toFixed(1)}B`;
  if (cap >= 1e6) return `$${(cap / 1e6).toFixed(0)}M`;
  return `$${cap.toLocaleString()}`;
}

function extractVolRatio(reason: string): string {
  const match = reason.match(/(\d+\.?\d*)x avg/);
  return match ? `${match[1]}x` : '';
}

function parseReason(reason: string): { tag: string; text: string } {
  // Extract emoji tag prefix and remaining text
  const emojiPatterns = [
    { prefix: '📈 Breakout Rally:', tag: '⚡ Breakout' },
    { prefix: '📈 Strong Momentum:', tag: '🚀 Momentum' },
    { prefix: '📈 Rally:', tag: '📊 Rally' },
    { prefix: '📈 Solid Gain:', tag: '📈 Gain' },
    { prefix: '📈 Up', tag: '📈 Up' },
    { prefix: '📉 Crash Alert:', tag: '🔴 Crash' },
    { prefix: '📉 Sharp Decline:', tag: '⚠️ Decline' },
    { prefix: '💸 Heavy Selling:', tag: '💸 Sell-off' },
    { prefix: '⚠️ Sell-off:', tag: '⚠️ Sell-off' },
    { prefix: '📉 Down', tag: '📉 Down' },
    { prefix: '🔥 High Activity:', tag: '🔥 Activity' },
    { prefix: '⚡ Sector Momentum:', tag: '⚡ Sector' },
    { prefix: '⚡ Heavy Trading:', tag: '⚡ Trading' },
    { prefix: '🔄 High-Volume Consolidation:', tag: '🔄 Consolidation' },
    { prefix: '🔥 Active:', tag: '🔥 Active' },
  ];

  for (const { prefix, tag } of emojiPatterns) {
    if (reason.startsWith(prefix)) {
      const text = reason.slice(prefix.length).trim().replace(/^—?\s*/, '');
      return { tag, text };
    }
  }

  // Fallback: no tag, full text
  return { tag: '', text: reason };
}
