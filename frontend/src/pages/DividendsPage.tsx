import { useCallback, useEffect, useState } from 'react';
import { dividendsApi } from '../api';
import type { DividendRecord, DividendCreate, DividendSummary, DividendProjection } from '../types';
import { formatTHB, formatDate, toNum } from '../utils/format';
import { useSortableData } from '../hooks/useSortableData';
import { usePagination } from '../hooks/usePagination';
import Pagination from '../components/Pagination';
import toast from 'react-hot-toast';

type ViewTab = 'records' | 'summary' | 'projection';

interface DividendFormData {
  date: string;
  stock_symbol: string;
  amount_per_share: string;
  shares_held: string;
  total_amount: string;
}

const EMPTY_FORM: DividendFormData = {
  date: '',
  stock_symbol: '',
  amount_per_share: '',
  shares_held: '',
  total_amount: '',
};

export default function DividendsPage() {
  const [records, setRecords] = useState<DividendRecord[]>([]);
  const [summary, setSummary] = useState<DividendSummary | null>(null);
  const [projection, setProjection] = useState<DividendProjection | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<ViewTab>('records');
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState<DividendFormData>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [summaryGroupBy, setSummaryGroupBy] = useState<'stock' | 'monthly' | 'yearly'>('stock');

  const fetchRecords = useCallback(async () => {
    try {
      const data = await dividendsApi.list();
      setRecords(data ?? []);
    } catch {
      // Error handled by interceptor
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchSummary = useCallback(async () => {
    try {
      const data = await dividendsApi.getSummary(summaryGroupBy);
      setSummary(data);
    } catch {
      // Error handled by interceptor
    }
  }, [summaryGroupBy]);

  const fetchProjection = useCallback(async () => {
    try {
      const data = await dividendsApi.getProjection();
      setProjection(data);
    } catch {
      // Error handled by interceptor
    }
  }, []);

  useEffect(() => {
    fetchRecords();
  }, [fetchRecords]);

  useEffect(() => {
    if (activeTab === 'summary') fetchSummary();
    if (activeTab === 'projection') fetchProjection();
  }, [activeTab, fetchSummary, fetchProjection]);

  const handleFormChange = (field: keyof DividendFormData, value: string) => {
    setFormData((prev) => {
      const updated = { ...prev, [field]: value };
      // Auto-calculate total_amount
      if (field === 'amount_per_share' || field === 'shares_held') {
        const aps = parseFloat(field === 'amount_per_share' ? value : prev.amount_per_share);
        const sh = parseInt(field === 'shares_held' ? value : prev.shares_held);
        if (!isNaN(aps) && !isNaN(sh)) {
          updated.total_amount = (aps * sh).toFixed(2);
        }
      }
      return updated;
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      const data: DividendCreate = {
        date: formData.date,
        stock_symbol: formData.stock_symbol.toUpperCase(),
        amount_per_share: parseFloat(formData.amount_per_share),
        shares_held: parseInt(formData.shares_held),
        total_amount: parseFloat(formData.total_amount),
      };
      await dividendsApi.create(data);
      toast.success('Dividend recorded', { duration: 4000 });
      setFormData(EMPTY_FORM);
      setShowForm(false);
      fetchRecords();
    } catch {
      // Error handled by interceptor
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="page dividends-page">
        <h1>Dividend Tracker</h1>
        <p className="loading-text" aria-live="polite">Loading dividends...</p>
      </div>
    );
  }

  return (
    <div className="page dividends-page">
      <h1>Dividend Tracker</h1>
      <p>Track dividend income received from your holdings.</p>

      <div className="trading-actions">
        <button className="btn btn-primary" onClick={() => setShowForm(!showForm)}>
          + Record Dividend
        </button>
      </div>

      {/* Create Form */}
      {showForm && (
        <div className="dividend-form-container">
          <form onSubmit={handleSubmit} className="dividend-form">
            <div className="form-grid">
              <div className="form-field">
                <label htmlFor="div-date">Date *</label>
                <input
                  id="div-date"
                  type="date"
                  value={formData.date}
                  onChange={(e) => handleFormChange('date', e.target.value)}
                  max={new Date().toISOString().split('T')[0]}
                  required
                />
              </div>
              <div className="form-field">
                <label htmlFor="div-symbol">Stock Symbol *</label>
                <input
                  id="div-symbol"
                  type="text"
                  placeholder="e.g. DRAM"
                  value={formData.stock_symbol}
                  onChange={(e) => handleFormChange('stock_symbol', e.target.value.toUpperCase())}
                  maxLength={20}
                  required
                />
              </div>
              <div className="form-field">
                <label htmlFor="div-aps">Amount Per Share (USD) *</label>
                <input
                  id="div-aps"
                  type="number"
                  step="0.01"
                  min="0.01"
                  placeholder="0.00"
                  value={formData.amount_per_share}
                  onChange={(e) => handleFormChange('amount_per_share', e.target.value)}
                  required
                />
              </div>
              <div className="form-field">
                <label htmlFor="div-shares">Shares Held *</label>
                <input
                  id="div-shares"
                  type="number"
                  min="1"
                  placeholder="Number of shares"
                  value={formData.shares_held}
                  onChange={(e) => handleFormChange('shares_held', e.target.value)}
                  required
                />
              </div>
              <div className="form-field">
                <label htmlFor="div-total">Total Amount (USD)</label>
                <input
                  id="div-total"
                  type="number"
                  step="0.01"
                  value={formData.total_amount}
                  onChange={(e) => handleFormChange('total_amount', e.target.value)}
                  placeholder="Auto-calculated"
                />
              </div>
            </div>
            <div className="form-actions">
              <button type="button" className="btn btn-secondary" onClick={() => setShowForm(false)}>
                Cancel
              </button>
              <button type="submit" className="btn btn-primary" disabled={saving}>
                {saving ? 'Saving...' : 'Record Dividend'}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* View Tabs */}
      <div className="tab-bar">
        <button
          className={`tab-btn ${activeTab === 'records' ? 'active' : ''}`}
          onClick={() => setActiveTab('records')}
        >
          📋 Records
        </button>
        <button
          className={`tab-btn ${activeTab === 'summary' ? 'active' : ''}`}
          onClick={() => setActiveTab('summary')}
        >
          📊 Summary
        </button>
        <button
          className={`tab-btn ${activeTab === 'projection' ? 'active' : ''}`}
          onClick={() => setActiveTab('projection')}
        >
          🔮 Projection
        </button>
      </div>

      {/* Records View */}
      {activeTab === 'records' && (
        <>
          {records.length === 0 ? (
            <div className="empty-state" role="status">
              <div className="empty-state-icon">💰</div>
              <h2>No Dividend Records</h2>
              <p>Record your first dividend payment to start tracking income.</p>
            </div>
          ) : (
            <DividendRecordsTable records={records} />
          )}
        </>
      )}

      {/* Summary View */}
      {activeTab === 'summary' && (
        <div className="summary-view">
          <div className="summary-controls">
            <label htmlFor="summary-group">Group by:</label>
            <select
              id="summary-group"
              value={summaryGroupBy}
              onChange={(e) => setSummaryGroupBy(e.target.value as 'stock' | 'monthly' | 'yearly')}
            >
              <option value="stock">Stock</option>
              <option value="monthly">Monthly</option>
              <option value="yearly">Yearly</option>
            </select>
          </div>
          {summary ? (
            <>
              <div className="summary-total">
                <strong>Total Dividends: {formatTHB(summary.total)}</strong>
              </div>
              <div className="table-container">
                <table className="data-table" aria-label="Dividend summary">
                  <thead>
                    <tr>
                      <th scope="col">{summaryGroupBy === 'stock' ? 'Stock' : 'Period'}</th>
                      <th scope="col" className="number-col">Total</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(
                      summaryGroupBy === 'stock' ? (summary.by_stock ?? {}) : (summary.by_period ?? {})
                    ).map(([key, value]) => (
                      <tr key={key}>
                        <td>{key}</td>
                        <td className="number-cell">{formatTHB(value)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          ) : (
            <p className="loading-text">Loading summary...</p>
          )}
        </div>
      )}

      {/* Projection View */}
      {activeTab === 'projection' && (
        <div className="projection-view">
          {projection ? (
            <>
              <div className="projection-total">
                <h3>Projected Annual Income</h3>
                <p className="projection-amount">{formatTHB(projection.projected_annual_income)}</p>
              </div>
              {Object.keys(projection.by_stock ?? {}).length > 0 && (
                <div className="table-container">
                  <table className="data-table" aria-label="Dividend projection by stock">
                    <thead>
                      <tr>
                        <th scope="col">Stock</th>
                        <th scope="col" className="number-col">Projected Annual</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(projection.by_stock ?? {}).map(([symbol, amount]) => (
                        <tr key={symbol}>
                          <td className="symbol-cell">{symbol}</td>
                          <td className="number-cell">{formatTHB(amount)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          ) : (
            <p className="loading-text">Loading projection...</p>
          )}
        </div>
      )}
    </div>
  );
}

// ===== Dividend Records Table Component =====

function DividendRecordsTable({ records }: { records: DividendRecord[] }) {
  const { sortedItems, requestSort, getSortIndicator } = useSortableData(records);
  const { paginatedItems, currentPage, totalItems, itemsPerPage, setPage, setPerPage } = usePagination(sortedItems);

  return (
    <div className="table-container">
      <table className="data-table" aria-label="Dividend records">
        <thead>
          <tr>
            <th scope="col" className="sortable-th" onClick={() => requestSort('date')}>Date{getSortIndicator('date')}</th>
            <th scope="col" className="sortable-th" onClick={() => requestSort('stock_symbol')}>Symbol{getSortIndicator('stock_symbol')}</th>
            <th scope="col" className="sortable-th number-col" onClick={() => requestSort('amount_per_share')}>Amount/Share{getSortIndicator('amount_per_share')}</th>
            <th scope="col" className="sortable-th number-col" onClick={() => requestSort('shares_held')}>Shares Held{getSortIndicator('shares_held')}</th>
            <th scope="col" className="sortable-th number-col" onClick={() => requestSort('total_amount')}>Total Amount{getSortIndicator('total_amount')}</th>
          </tr>
        </thead>
        <tbody>
          {paginatedItems.map((record) => (
            <tr key={record.id}>
              <td>{formatDate(record.date)}</td>
              <td className="symbol-cell">{record.stock_symbol}</td>
              <td className="number-cell">{formatTHB(record.amount_per_share)}</td>
              <td className="number-cell">{toNum(record.shares_held).toLocaleString()}</td>
              <td className="number-cell">{formatTHB(record.total_amount)}</td>
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
