import { useCallback, useEffect, useState } from 'react';
import { performanceApi } from '../api';
import type {
  PerformanceSnapshot,
  PerformanceSnapshotCreate,
  PerformanceSnapshotUpdate,
  PerformanceFilters,
} from '../types';
import { formatTHB, formatDate, toNum } from '../utils/format';
import { useSortableData } from '../hooks/useSortableData';
import { usePagination } from '../hooks/usePagination';
import Pagination from '../components/Pagination';
import toast from 'react-hot-toast';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';

// ===== Helper Functions =====

function getTodayString(): string {
  return new Date().toISOString().slice(0, 10);
}

// ===== Types =====

interface SnapshotFormData {
  date: string;
  total_portfolio_value: string;
  total_cost: string;
}

const EMPTY_FORM: SnapshotFormData = {
  date: getTodayString(),
  total_portfolio_value: '',
  total_cost: '',
};

type AggregationView = '' | 'monthly' | 'yearly';

// ===== Main Component =====

export default function PerformancePage() {
  const [snapshots, setSnapshots] = useState<PerformanceSnapshot[]>([]);
  const [cumulativeReturn, setCumulativeReturn] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [formData, setFormData] = useState<SnapshotFormData>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);

  // Filters
  const [filters, setFilters] = useState<PerformanceFilters>({});
  const [filterDateFrom, setFilterDateFrom] = useState('');
  const [filterDateTo, setFilterDateTo] = useState('');
  const [aggregation, setAggregation] = useState<AggregationView>('');

  const fetchSnapshots = useCallback(async () => {
    try {
      const result = await performanceApi.list(filters);
      setSnapshots(result.snapshots ?? []);
      setCumulativeReturn(result.cumulative_return ?? null);
    } catch {
      // Error handled by interceptor
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => {
    fetchSnapshots();
  }, [fetchSnapshots]);

  // ===== Filter Handlers =====

  const applyFilters = () => {
    const newFilters: PerformanceFilters = {};
    if (filterDateFrom) newFilters.date_from = filterDateFrom;
    if (filterDateTo) newFilters.date_to = filterDateTo;
    if (aggregation) newFilters.aggregation = aggregation;
    setFilters(newFilters);
  };

  const clearFilters = () => {
    setFilterDateFrom('');
    setFilterDateTo('');
    setAggregation('');
    setFilters({});
  };

  // ===== Form Handlers =====

  const openCreateForm = () => {
    setEditingId(null);
    setFormData(EMPTY_FORM);
    setShowForm(true);
  };

  const openEditForm = (snapshot: PerformanceSnapshot) => {
    setEditingId(snapshot.id);
    setFormData({
      date: snapshot.date,
      total_portfolio_value: String(snapshot.total_portfolio_value),
      total_cost: String(snapshot.total_cost),
    });
    setShowForm(true);
  };

  const closeForm = () => {
    setShowForm(false);
    setEditingId(null);
  };

  const handleFormChange = (field: keyof SnapshotFormData, value: string) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);

    const portfolioValue = parseFloat(formData.total_portfolio_value);
    const totalCost = parseFloat(formData.total_cost);

    try {
      if (editingId) {
        const updateData: PerformanceSnapshotUpdate = {
          date: formData.date,
          total_portfolio_value: portfolioValue,
          total_cost: totalCost,
        };
        await performanceApi.update(editingId, updateData);
        toast.success('Snapshot updated successfully', { duration: 4000 });
      } else {
        const createData: PerformanceSnapshotCreate = {
          date: formData.date,
          total_portfolio_value: portfolioValue,
          total_cost: totalCost,
        };
        await performanceApi.create(createData);
        toast.success('Snapshot recorded successfully', { duration: 4000 });
      }
      closeForm();
      fetchSnapshots();
    } catch {
      // Form data retained on failure — error shown by interceptor
    } finally {
      setSaving(false);
    }
  };

  // ===== Delete Handlers =====

  const handleDelete = async (id: string) => {
    try {
      await performanceApi.delete(id);
      toast.success('Snapshot deleted successfully', { duration: 4000 });
      setDeleteConfirmId(null);
      fetchSnapshots();
    } catch {
      // Error handled by interceptor
    }
  };

  // ===== Render =====

  if (loading) {
    return (
      <div className="page performance-page">
        <h1>Performance History</h1>
        <p className="loading-text" aria-live="polite">Loading performance data...</p>
      </div>
    );
  }

  return (
    <div className="page performance-page">
      <h1>Performance History</h1>
      <p>Track your portfolio value and returns over time.</p>

      {/* Action Buttons */}
      <div className="trading-actions">
        <button className="btn btn-primary" onClick={openCreateForm}>
          + Record Snapshot
        </button>
      </div>

      {/* Filter Panel */}
      <PerformanceFilterPanel
        dateFrom={filterDateFrom}
        dateTo={filterDateTo}
        aggregation={aggregation}
        onDateFromChange={setFilterDateFrom}
        onDateToChange={setFilterDateTo}
        onAggregationChange={setAggregation}
        onApply={applyFilters}
        onClear={clearFilters}
      />

      {/* Cumulative Return */}
      {cumulativeReturn !== null && snapshots.length > 0 && (
        <div className="cumulative-return-card">
          <span className="cumulative-return-label">Cumulative Return:</span>
          <span
            className={`cumulative-return-value ${toNum(cumulativeReturn) >= 0 ? 'positive' : 'negative'}`}
          >
            {toNum(cumulativeReturn) >= 0 ? '+' : ''}
            {toNum(cumulativeReturn).toFixed(2)}%
          </span>
        </div>
      )}

      {/* Content */}
      {snapshots.length === 0 ? (
        <div className="empty-state" role="status">
          <div className="empty-state-icon">📈</div>
          <h2>No Performance Data</h2>
          <p>
            No performance snapshots recorded yet. Record your first snapshot to start tracking
            your portfolio value over time.
          </p>
        </div>
      ) : (
        <>
          {/* Line Chart */}
          <PerformanceChart snapshots={snapshots} />

          {/* Snapshots Table */}
          <SnapshotTable
            snapshots={snapshots}
            onEdit={openEditForm}
            onDelete={(id) => setDeleteConfirmId(id)}
          />
        </>
      )}

      {/* Create/Edit Form Modal */}
      {showForm && (
        <SnapshotFormModal
          editingId={editingId}
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

// ===== Filter Panel Component =====

interface PerformanceFilterPanelProps {
  dateFrom: string;
  dateTo: string;
  aggregation: AggregationView;
  onDateFromChange: (v: string) => void;
  onDateToChange: (v: string) => void;
  onAggregationChange: (v: AggregationView) => void;
  onApply: () => void;
  onClear: () => void;
}

function PerformanceFilterPanel({
  dateFrom,
  dateTo,
  aggregation,
  onDateFromChange,
  onDateToChange,
  onAggregationChange,
  onApply,
  onClear,
}: PerformanceFilterPanelProps) {
  return (
    <div className="filter-panel" role="search" aria-label="Performance filters">
      <div className="filter-row">
        <div className="filter-field">
          <label htmlFor="perf-filter-date-from">From</label>
          <input
            id="perf-filter-date-from"
            type="date"
            value={dateFrom}
            onChange={(e) => onDateFromChange(e.target.value)}
          />
        </div>
        <div className="filter-field">
          <label htmlFor="perf-filter-date-to">To</label>
          <input
            id="perf-filter-date-to"
            type="date"
            value={dateTo}
            onChange={(e) => onDateToChange(e.target.value)}
          />
        </div>
        <div className="filter-field">
          <label htmlFor="perf-filter-aggregation">View</label>
          <select
            id="perf-filter-aggregation"
            value={aggregation}
            onChange={(e) => onAggregationChange(e.target.value as AggregationView)}
          >
            <option value="">All Snapshots</option>
            <option value="monthly">Monthly</option>
            <option value="yearly">Yearly</option>
          </select>
        </div>
      </div>
      <div className="filter-buttons">
        <button className="btn btn-primary btn-sm" onClick={onApply}>
          Apply Filters
        </button>
        <button className="btn btn-secondary btn-sm" onClick={onClear}>
          Clear
        </button>
      </div>
    </div>
  );
}

// ===== Performance Chart Component =====

interface PerformanceChartProps {
  snapshots: PerformanceSnapshot[];
}

function PerformanceChart({ snapshots }: PerformanceChartProps) {
  const chartData = snapshots.map((s) => ({
    date: s.date,
    value: s.total_portfolio_value,
  }));

  return (
    <div className="performance-chart-container" aria-label="Portfolio value over time">
      <h3>Portfolio Value Over Time</h3>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={chartData} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="date" tick={{ fontSize: 12 }} />
          <YAxis
            tick={{ fontSize: 12 }}
            tickFormatter={(value: number) => `฿${(value / 1000).toFixed(0)}k`}
          />
          <Tooltip
            formatter={(value) => [formatTHB(value as number), 'Portfolio Value']}
            labelFormatter={(label) => `Date: ${label}`}
          />
          <Line
            type="monotone"
            dataKey="value"
            stroke="#4f46e5"
            strokeWidth={2}
            dot={{ r: 3 }}
            activeDot={{ r: 5 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

// ===== Snapshot Table Component =====

interface SnapshotTableProps {
  snapshots: PerformanceSnapshot[];
  onEdit: (snapshot: PerformanceSnapshot) => void;
  onDelete: (id: string) => void;
}

function SnapshotTable({ snapshots, onEdit, onDelete }: SnapshotTableProps) {
  const { sortedItems, requestSort, getSortIndicator } = useSortableData(snapshots);
  const { paginatedItems, currentPage, totalItems, itemsPerPage, setPage, setPerPage } = usePagination(sortedItems);

  return (
    <div className="table-container">
      <table className="data-table" aria-label="Performance snapshots">
        <thead>
          <tr>
            <th scope="col" className="sortable-th" onClick={() => requestSort('date')}>Date{getSortIndicator('date')}</th>
            <th scope="col" className="sortable-th number-col" onClick={() => requestSort('total_portfolio_value')}>Portfolio Value{getSortIndicator('total_portfolio_value')}</th>
            <th scope="col" className="sortable-th number-col" onClick={() => requestSort('total_cost')}>Total Cost{getSortIndicator('total_cost')}</th>
            <th scope="col" className="sortable-th number-col" onClick={() => requestSort('pl')}>P/L{getSortIndicator('pl')}</th>
            <th scope="col" className="sortable-th number-col" onClick={() => requestSort('period_return')}>Period Return{getSortIndicator('period_return')}</th>
            <th scope="col">Actions</th>
          </tr>
        </thead>
        <tbody>
          {paginatedItems.map((snapshot) => (
            <tr key={snapshot.id}>
              <td>{formatDate(snapshot.date)}</td>
              <td className="number-cell">{formatTHB(snapshot.total_portfolio_value)}</td>
              <td className="number-cell">{formatTHB(snapshot.total_cost)}</td>
              <td className={`number-cell ${toNum(snapshot.pl) >= 0 ? 'positive' : 'negative'}`}>
                {formatTHB(snapshot.pl)}
              </td>
              <td className="number-cell">
                {snapshot.period_return !== null ? (
                  <span className={toNum(snapshot.period_return) >= 0 ? 'positive' : 'negative'}>
                    {toNum(snapshot.period_return) >= 0 ? '+' : ''}
                    {toNum(snapshot.period_return).toFixed(2)}%
                  </span>
                ) : (
                  <span className="na-text">N/A</span>
                )}
              </td>
              <td className="actions-cell">
                <button
                  className="btn btn-icon"
                  onClick={() => onEdit(snapshot)}
                  title="Edit snapshot"
                  aria-label={`Edit snapshot on ${snapshot.date}`}
                >
                  ✏️
                </button>
                <button
                  className="btn btn-icon btn-danger"
                  onClick={() => onDelete(snapshot.id)}
                  title="Delete snapshot"
                  aria-label={`Delete snapshot on ${snapshot.date}`}
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

// ===== Snapshot Form Modal =====

interface SnapshotFormModalProps {
  editingId: string | null;
  formData: SnapshotFormData;
  saving: boolean;
  onChange: (field: keyof SnapshotFormData, value: string) => void;
  onSubmit: (e: React.FormEvent) => void;
  onClose: () => void;
}

function SnapshotFormModal({
  editingId,
  formData,
  saving,
  onChange,
  onSubmit,
  onClose,
}: SnapshotFormModalProps) {
  const portfolioValue = parseFloat(formData.total_portfolio_value) || 0;
  const totalCost = parseFloat(formData.total_cost) || 0;
  const pl = portfolioValue - totalCost;

  return (
    <div
      className="modal-overlay"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label={editingId ? 'Edit Snapshot' : 'Record Snapshot'}
    >
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>{editingId ? 'Edit Snapshot' : 'Record Snapshot'}</h2>
          <button className="btn btn-icon" onClick={onClose} aria-label="Close form">
            ✕
          </button>
        </div>
        <form onSubmit={onSubmit} className="snapshot-form">
          <div className="form-grid">
            <div className="form-field">
              <label htmlFor="snap-date">Date *</label>
              <input
                id="snap-date"
                type="date"
                value={formData.date}
                max={getTodayString()}
                onChange={(e) => onChange('date', e.target.value)}
                required
              />
            </div>
            <div className="form-field">
              <label htmlFor="snap-portfolio-value">Portfolio Value (USD) *</label>
              <input
                id="snap-portfolio-value"
                type="number"
                placeholder="0.00"
                value={formData.total_portfolio_value}
                onChange={(e) => onChange('total_portfolio_value', e.target.value)}
                min={0}
                max={999999999.99}
                step="0.01"
                required
              />
            </div>
            <div className="form-field">
              <label htmlFor="snap-total-cost">Total Cost (USD) *</label>
              <input
                id="snap-total-cost"
                type="number"
                placeholder="0.00"
                value={formData.total_cost}
                onChange={(e) => onChange('total_cost', e.target.value)}
                min={0}
                max={999999999.99}
                step="0.01"
                required
              />
            </div>
          </div>

          {/* Auto-calculated P/L preview */}
          <div className="form-calculated">
            <div className="calculated-field">
              <span className="calculated-label">P/L:</span>
              <span className={`calculated-value ${pl >= 0 ? 'positive' : 'negative'}`}>
                {formatTHB(pl)}
              </span>
            </div>
          </div>

          <div className="form-actions">
            <button type="button" className="btn btn-secondary" onClick={onClose} disabled={saving}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? 'Saving...' : editingId ? 'Update' : 'Record'}
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
    <div
      className="modal-overlay"
      onClick={onCancel}
      role="alertdialog"
      aria-modal="true"
      aria-label="Confirm deletion"
    >
      <div className="modal-content modal-sm" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Confirm Delete</h2>
        </div>
        <p>Are you sure you want to delete this snapshot? This action cannot be undone.</p>
        <div className="form-actions">
          <button className="btn btn-secondary" onClick={onCancel}>
            Cancel
          </button>
          <button className="btn btn-danger" onClick={onConfirm}>
            Delete
          </button>
        </div>
      </div>
    </div>
  );
}
