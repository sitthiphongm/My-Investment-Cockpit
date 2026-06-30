import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { watchlistApi, trendingApi } from '../api';
import type { WatchlistItem, WatchlistItemCreate, WatchlistItemUpdate, TrendingStock } from '../types';
import { formatTHB, formatPercent, toNum } from '../utils/format';
import { useSortableData } from '../hooks/useSortableData';
import { usePagination } from '../hooks/usePagination';
import Pagination from '../components/Pagination';
import toast from 'react-hot-toast';

// ===== Types =====

interface WatchlistFormData {
  stock_symbol: string;
  interested_at_price: string;
  notes: string;
}

const EMPTY_FORM: WatchlistFormData = {
  stock_symbol: '',
  interested_at_price: '',
  notes: '',
};

// ===== Main Component =====

export default function WatchlistPage() {
  const [items, setItems] = useState<WatchlistItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingItem, setEditingItem] = useState<WatchlistItem | null>(null);
  const [formData, setFormData] = useState<WatchlistFormData>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);

  // Trending stocks
  const [showTrending, setShowTrending] = useState(false);
  const [trendingStocks, setTrendingStocks] = useState<TrendingStock[]>([]);
  const [loadingTrending, setLoadingTrending] = useState(false);

  const fetchWatchlist = useCallback(async () => {
    try {
      const result = await watchlistApi.list();
      setItems(result ?? []);
    } catch {
      // Error handled by interceptor
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchWatchlist();
  }, [fetchWatchlist]);

  // ===== Trending Stocks =====

  const fetchTrending = async () => {
    setLoadingTrending(true);
    try {
      const data = await trendingApi.get();
      // Combine gainers, losers, and most active into a single list
      const allStocks = [...(data.gainers ?? []), ...(data.losers ?? []), ...(data.most_active ?? [])];
      // Deduplicate by symbol
      const seen = new Set<string>();
      const unique: TrendingStock[] = [];
      for (const stock of allStocks) {
        const sym = stock.symbol || stock.stock_symbol || '';
        if (!seen.has(sym)) {
          seen.add(sym);
          unique.push(stock);
        }
      }
      setTrendingStocks(unique);
    } catch {
      // Error handled by interceptor
    } finally {
      setLoadingTrending(false);
    }
  };

  const toggleTrending = () => {
    if (!showTrending) {
      fetchTrending();
    }
    setShowTrending(!showTrending);
  };

  const addTrendingToWatchlist = async (stock: TrendingStock) => {
    try {
      const data: WatchlistItemCreate = {
        stock_symbol: stock.symbol || stock.stock_symbol || '',
      };
      await watchlistApi.create(data);
      toast.success(`${stock.symbol || stock.stock_symbol} added to watchlist`, { duration: 4000 });
      fetchWatchlist();
    } catch {
      // Error handled by interceptor
    }
  };

  // ===== Form Handlers =====

  const openCreateForm = () => {
    setEditingItem(null);
    setFormData(EMPTY_FORM);
    setShowForm(true);
  };

  const openEditForm = (item: WatchlistItem) => {
    setEditingItem(item);
    setFormData({
      stock_symbol: item.stock_symbol,
      interested_at_price: item.interested_at_price != null ? String(item.interested_at_price) : '',
      notes: item.notes || '',
    });
    setShowForm(true);
  };

  const closeForm = () => {
    setShowForm(false);
    setEditingItem(null);
  };

  const handleFormChange = (field: keyof WatchlistFormData, value: string) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);

    const interestedPrice = formData.interested_at_price
      ? parseFloat(formData.interested_at_price)
      : null;
    const notes = formData.notes.trim() || null;

    try {
      if (editingItem) {
        const updateData: WatchlistItemUpdate = {
          interested_at_price: interestedPrice,
          notes: notes,
        };
        await watchlistApi.update(editingItem.id, updateData);
        toast.success('Watchlist entry updated', { duration: 4000 });
      } else {
        const createData: WatchlistItemCreate = {
          stock_symbol: formData.stock_symbol.toUpperCase(),
          interested_at_price: interestedPrice,
          notes: notes,
        };
        await watchlistApi.create(createData);
        toast.success('Stock added to watchlist', { duration: 4000 });
      }
      closeForm();
      fetchWatchlist();
    } catch {
      // Form data retained on failure — error shown by interceptor
    } finally {
      setSaving(false);
    }
  };

  // ===== Delete Handlers =====

  const handleDelete = async (id: string) => {
    try {
      await watchlistApi.delete(id);
      toast.success('Removed from watchlist', { duration: 4000 });
      setDeleteConfirmId(null);
      fetchWatchlist();
    } catch {
      // Error handled by interceptor
    }
  };

  // ===== Render =====

  if (loading) {
    return (
      <div className="page watchlist-page">
        <h1>Watchlist</h1>
        <p className="loading-text" aria-live="polite">Loading watchlist...</p>
      </div>
    );
  }

  return (
    <div className="page watchlist-page">
      <h1>Watchlist</h1>
      <p>Monitor stocks you're interested in.</p>

      {/* Action Buttons */}
      <div className="trading-actions">
        <button className="btn btn-primary" onClick={openCreateForm}>
          + Add Stock
        </button>
        <button className="btn btn-secondary" onClick={toggleTrending}>
          {showTrending ? '📈 Hide Trending' : '📈 Trending Stocks'}
        </button>
      </div>

      {/* Trending Stocks Section */}
      {showTrending && (
        <TrendingStocksPanel
          stocks={trendingStocks}
          loading={loadingTrending}
          watchedSymbols={items.map((i) => i.stock_symbol)}
          onAdd={addTrendingToWatchlist}
        />
      )}

      {/* Watchlist Table */}
      {items.length === 0 ? (
        <div className="empty-state" role="status">
          <div className="empty-state-icon">👁️</div>
          <h2>No Stocks on Watchlist</h2>
          <p>Add stocks to your watchlist to monitor their prices. You can also browse trending stocks for ideas.</p>
        </div>
      ) : (
        <WatchlistTable
          items={items}
          onEdit={openEditForm}
          onDelete={(id) => setDeleteConfirmId(id)}
        />
      )}

      {/* Create/Edit Form Modal */}
      {showForm && (
        <WatchlistFormModal
          editingItem={editingItem}
          formData={formData}
          saving={saving}
          onChange={handleFormChange}
          onSubmit={handleSubmit}
          onClose={closeForm}
        />
      )}

      {/* Delete Confirmation */}
      {deleteConfirmId && (
        <DeleteConfirmDialog
          onConfirm={() => handleDelete(deleteConfirmId)}
          onCancel={() => setDeleteConfirmId(null)}
        />
      )}
    </div>
  );
}

// ===== Trending Stocks Panel =====

interface TrendingStocksPanelProps {
  stocks: TrendingStock[];
  loading: boolean;
  watchedSymbols: string[];
  onAdd: (stock: TrendingStock) => void;
}

function TrendingStocksPanel({ stocks, loading, watchedSymbols, onAdd }: TrendingStocksPanelProps) {
  if (loading) {
    return (
      <div className="trending-panel" aria-live="polite">
        <h3>Trending Stocks</h3>
        <p className="loading-text">Loading trending stocks...</p>
      </div>
    );
  }

  if (stocks.length === 0) {
    return (
      <div className="trending-panel">
        <h3>Trending Stocks</h3>
        <p>No trending data available at the moment.</p>
      </div>
    );
  }

  return (
    <div className="trending-panel">
      <h3>Trending Stocks</h3>
      <div className="table-container">
        <table className="data-table trending-table" aria-label="Trending stocks">
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
              <th scope="col">Stock</th>
              <th scope="col">Sector</th>
              <th scope="col" className="number-col">Price</th>
              <th scope="col" className="number-col">Change</th>
              <th scope="col" className="number-col">Volume</th>
              <th scope="col" className="number-col">Mkt Cap</th>
              <th scope="col">Reason</th>
              <th scope="col">Action</th>
            </tr>
          </thead>
          <tbody>
            {stocks.map((stock) => {
              const sym = stock.symbol || stock.stock_symbol || '';
              const alreadyWatched = watchedSymbols.includes(sym);
              const pct = toNum(stock.day_change_percent);
              const vol = toNum(stock.volume);
              const reason = (stock as any).reason || '';
              const sector = (stock as any).sector || '';
              const mktCap = toNum((stock as any).market_cap);

              return (
                <tr key={sym}>
                  <td className="stock-name-cell">
                    <a href={`https://stockanalysis.com/stocks/${sym.toLowerCase()}/`} target="_blank" rel="noopener noreferrer" className="stock-symbol-link">{sym}</a>
                    <span className="stock-company-sub">{stock.company_name || ''}</span>
                  </td>
                  <td>{sector ? <span className="sector-tag">{sector}</span> : <span className="na-text">—</span>}</td>
                  <td className="number-cell">{stock.current_price != null ? `$${toNum(stock.current_price).toFixed(2)}` : 'N/A'}</td>
                  <td className="number-cell">
                    <span className={`change-badge ${pct >= 0 ? 'change-positive' : 'change-negative'}`}>
                      {pct >= 0 ? '+' : ''}{pct.toFixed(2)}%
                    </span>
                  </td>
                  <td className="number-cell">
                    <span className="vol-primary">{vol >= 1e6 ? `${(vol/1e6).toFixed(1)}M` : vol >= 1e3 ? `${(vol/1e3).toFixed(0)}K` : vol.toLocaleString()}</span>
                  </td>
                  <td className="number-cell">{mktCap > 0 ? (mktCap >= 1e9 ? `$${(mktCap/1e9).toFixed(1)}B` : `$${(mktCap/1e6).toFixed(0)}M`) : 'N/A'}</td>
                  <td className="reason-cell-v2">
                    <span className="reason-text">{reason}</span>
                  </td>
                  <td>
                    {alreadyWatched ? (
                      <span className="badge badge-muted">Watched</span>
                    ) : (
                      <button className="btn btn-sm btn-primary" onClick={() => onAdd(stock)} aria-label={`Add ${sym}`}>+ Add</button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ===== Watchlist Table =====

interface WatchlistTableProps {
  items: WatchlistItem[];
  onEdit: (item: WatchlistItem) => void;
  onDelete: (id: string) => void;
}

function WatchlistTable({ items, onEdit, onDelete }: WatchlistTableProps) {
  const { sortedItems, requestSort, getSortIndicator } = useSortableData(items);
  const { paginatedItems, currentPage, totalItems, itemsPerPage, setPage, setPerPage } = usePagination(sortedItems);

  return (
    <div className="table-container">
      <table className="data-table" aria-label="Watchlist stocks">
        <thead>
          <tr>
            <th scope="col" className="sortable-th" onClick={() => requestSort('stock_symbol')}>Symbol{getSortIndicator('stock_symbol')}</th>
            <th scope="col">Company</th>
            <th scope="col" className="sortable-th number-col" onClick={() => requestSort('current_price')}>Current Price{getSortIndicator('current_price')}</th>
            <th scope="col" className="sortable-th number-col" onClick={() => requestSort('day_change_percent')}>Day Change{getSortIndicator('day_change_percent')}</th>
            <th scope="col" className="sortable-th number-col" onClick={() => requestSort('interested_at_price')}>Target Price{getSortIndicator('interested_at_price')}</th>
            <th scope="col">Status</th>
            <th scope="col">Notes</th>
            <th scope="col">Actions</th>
          </tr>
        </thead>
        <tbody>
          {paginatedItems.map((item) => (
            <tr
              key={item.id}
              className={item.at_target ? 'row-at-target' : ''}
            >
              <td className="symbol-cell"><Link to={`/stock/${item.stock_symbol}`}>{item.stock_symbol}</Link></td>
              <td>{item.company_name || '-'}</td>
              <td className="number-cell">
                {item.current_price != null ? formatTHB(item.current_price) : 'N/A'}
              </td>
              <td className="number-cell">
                <span
                  className={
                    item.day_change_percent != null
                      ? toNum(item.day_change_percent) >= 0
                        ? 'text-positive'
                        : 'text-negative'
                      : ''
                  }
                >
                  {item.day_change_percent != null
                    ? formatPercent(item.day_change_percent)
                    : 'N/A'}
                </span>
              </td>
              <td className="number-cell">
                {item.interested_at_price != null
                  ? formatTHB(item.interested_at_price)
                  : '-'}
              </td>
              <td>
                {item.at_target ? (
                  <span className="badge badge-at-target">🎯 At Target</span>
                ) : item.interested_at_price != null ? (
                  <span className="badge badge-watching">Watching</span>
                ) : (
                  <span className="badge badge-muted">No target</span>
                )}
              </td>
              <td className="notes-cell" title={item.notes || undefined}>
                {item.notes ? (item.notes.length > 30 ? item.notes.slice(0, 30) + '…' : item.notes) : '-'}
              </td>
              <td className="actions-cell">
                <button
                  className="btn btn-icon"
                  onClick={() => onEdit(item)}
                  title="Edit watchlist entry"
                  aria-label={`Edit ${item.stock_symbol} watchlist entry`}
                >
                  ✏️
                </button>
                <button
                  className="btn btn-icon btn-danger"
                  onClick={() => onDelete(item.id)}
                  title="Remove from watchlist"
                  aria-label={`Remove ${item.stock_symbol} from watchlist`}
                >
                  🗑️
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <Pagination
        currentPage={currentPage}
        totalItems={totalItems}
        itemsPerPage={itemsPerPage}
        onPageChange={setPage}
        onItemsPerPageChange={setPerPage}
      />
    </div>
  );
}

// ===== Watchlist Form Modal =====

interface WatchlistFormModalProps {
  editingItem: WatchlistItem | null;
  formData: WatchlistFormData;
  saving: boolean;
  onChange: (field: keyof WatchlistFormData, value: string) => void;
  onSubmit: (e: React.FormEvent) => void;
  onClose: () => void;
}

function WatchlistFormModal({
  editingItem,
  formData,
  saving,
  onChange,
  onSubmit,
  onClose,
}: WatchlistFormModalProps) {
  return (
    <div className="modal-overlay" onClick={onClose} role="dialog" aria-modal="true" aria-label={editingItem ? 'Edit Watchlist Entry' : 'Add to Watchlist'}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>{editingItem ? 'Edit Watchlist Entry' : 'Add to Watchlist'}</h2>
          <button className="btn btn-icon" onClick={onClose} aria-label="Close form">✕</button>
        </div>
        <form onSubmit={onSubmit} className="watchlist-form">
          <div className="form-grid">
            {!editingItem && (
              <div className="form-field">
                <label htmlFor="wl-symbol">Stock Symbol *</label>
                <input
                  id="wl-symbol"
                  type="text"
                  placeholder="e.g. DRAM"
                  value={formData.stock_symbol}
                  onChange={(e) => onChange('stock_symbol', e.target.value.toUpperCase())}
                  maxLength={20}
                  required
                />
              </div>
            )}
            {editingItem && (
              <div className="form-field">
                <label>Stock Symbol</label>
                <input
                  type="text"
                  value={formData.stock_symbol}
                  disabled
                  aria-label="Stock symbol (read only)"
                />
              </div>
            )}
            <div className="form-field">
              <label htmlFor="wl-target-price">Interested At Price (USD)</label>
              <input
                id="wl-target-price"
                type="number"
                placeholder="Target price to buy"
                value={formData.interested_at_price}
                onChange={(e) => onChange('interested_at_price', e.target.value)}
                min={0.01}
                step="0.01"
              />
            </div>
            <div className="form-field form-field-full">
              <label htmlFor="wl-notes">Notes</label>
              <textarea
                id="wl-notes"
                placeholder="Why are you watching this stock?"
                value={formData.notes}
                onChange={(e) => onChange('notes', e.target.value)}
                maxLength={500}
                rows={3}
              />
              <span className="char-count">{formData.notes.length}/500</span>
            </div>
          </div>

          <div className="form-actions">
            <button type="button" className="btn btn-secondary" onClick={onClose} disabled={saving}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? 'Saving...' : editingItem ? 'Update' : 'Add to Watchlist'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ===== Delete Confirmation Dialog =====

interface DeleteConfirmDialogProps {
  onConfirm: () => void;
  onCancel: () => void;
}

function DeleteConfirmDialog({ onConfirm, onCancel }: DeleteConfirmDialogProps) {
  return (
    <div className="modal-overlay" onClick={onCancel} role="alertdialog" aria-modal="true" aria-label="Confirm removal">
      <div className="modal-content modal-sm" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Remove from Watchlist</h2>
        </div>
        <p>Are you sure you want to remove this stock from your watchlist?</p>
        <div className="form-actions">
          <button className="btn btn-secondary" onClick={onCancel}>
            Cancel
          </button>
          <button className="btn btn-danger" onClick={onConfirm}>
            Remove
          </button>
        </div>
      </div>
    </div>
  );
}
