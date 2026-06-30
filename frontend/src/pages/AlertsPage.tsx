import { useCallback, useEffect, useState } from 'react';
import { alertsApi } from '../api';
import type { PriceAlert, PriceAlertCreate, AlertType } from '../types';
import { formatTHB, formatDateTime } from '../utils/format';
import { useSortableData } from '../hooks/useSortableData';
import { usePagination } from '../hooks/usePagination';
import Pagination from '../components/Pagination';
import toast from 'react-hot-toast';

interface AlertFormData {
  stock_symbol: string;
  alert_type: AlertType;
  target_price: string;
  note: string;
}

const EMPTY_FORM: AlertFormData = {
  stock_symbol: '',
  alert_type: 'Above',
  target_price: '',
  note: '',
};

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<PriceAlert[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState<AlertFormData>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);

  const fetchAlerts = useCallback(async () => {
    try {
      const result = await alertsApi.list();
      setAlerts(result ?? []);
    } catch {
      // Error handled by interceptor
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAlerts();
  }, [fetchAlerts]);

  const handleFormChange = (field: keyof AlertFormData, value: string) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.stock_symbol.trim() || !formData.target_price) return;

    setSaving(true);
    try {
      const data: PriceAlertCreate = {
        stock_symbol: formData.stock_symbol.toUpperCase(),
        alert_type: formData.alert_type,
        target_price: parseFloat(formData.target_price),
        note: formData.note.trim() || null,
      };
      await alertsApi.create(data);
      toast.success('Alert created', { duration: 4000 });
      setFormData(EMPTY_FORM);
      setShowForm(false);
      fetchAlerts();
    } catch {
      // Error handled by interceptor
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await alertsApi.delete(id);
      toast.success('Alert deleted', { duration: 4000 });
      setDeleteConfirmId(null);
      fetchAlerts();
    } catch {
      // Error handled by interceptor
    }
  };

  const activeAlerts = alerts.filter((a) => !a.triggered);
  const triggeredAlerts = alerts.filter((a) => a.triggered);

  if (loading) {
    return (
      <div className="page alerts-page">
        <h1>Price Alerts</h1>
        <p className="loading-text" aria-live="polite">Loading alerts...</p>
      </div>
    );
  }

  return (
    <div className="page alerts-page">
      <h1>Price Alerts</h1>
      <p>Get notified when stocks reach your target prices.</p>

      <div className="trading-actions">
        <button className="btn btn-primary" onClick={() => setShowForm(!showForm)}>
          + Create Alert
        </button>
      </div>

      {/* Create Alert Form */}
      {showForm && (
        <div className="alert-form-container">
          <form onSubmit={handleSubmit} className="alert-form">
            <div className="form-grid">
              <div className="form-field">
                <label htmlFor="alert-symbol">Stock Symbol *</label>
                <input
                  id="alert-symbol"
                  type="text"
                  placeholder="e.g. DRAM"
                  value={formData.stock_symbol}
                  onChange={(e) => handleFormChange('stock_symbol', e.target.value.toUpperCase())}
                  maxLength={20}
                  required
                />
              </div>
              <div className="form-field">
                <label htmlFor="alert-type">Alert Type *</label>
                <select
                  id="alert-type"
                  value={formData.alert_type}
                  onChange={(e) => handleFormChange('alert_type', e.target.value)}
                  required
                >
                  <option value="Above">Above (price goes up to)</option>
                  <option value="Below">Below (price drops to)</option>
                </select>
              </div>
              <div className="form-field">
                <label htmlFor="alert-target">Target Price (USD) *</label>
                <input
                  id="alert-target"
                  type="number"
                  step="0.01"
                  min="0.01"
                  placeholder="Target price"
                  value={formData.target_price}
                  onChange={(e) => handleFormChange('target_price', e.target.value)}
                  required
                />
              </div>
              <div className="form-field">
                <label htmlFor="alert-note">Note</label>
                <input
                  id="alert-note"
                  type="text"
                  placeholder="Optional note"
                  value={formData.note}
                  onChange={(e) => handleFormChange('note', e.target.value)}
                  maxLength={200}
                />
              </div>
            </div>
            <div className="form-actions">
              <button type="button" className="btn btn-secondary" onClick={() => setShowForm(false)}>
                Cancel
              </button>
              <button type="submit" className="btn btn-primary" disabled={saving}>
                {saving ? 'Creating...' : 'Create Alert'}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Triggered Alerts */}
      {triggeredAlerts.length > 0 && (
        <div className="triggered-alerts-section">
          <h3>🔔 Triggered Alerts</h3>
          <AlertsTable alerts={triggeredAlerts} onDelete={(id) => setDeleteConfirmId(id)} rowClassName="row-triggered" />
        </div>
      )}

      {/* Active Alerts */}
      <h3>Active Alerts ({activeAlerts.length})</h3>
      {activeAlerts.length === 0 ? (
        <div className="empty-state" role="status">
          <div className="empty-state-icon">🔔</div>
          <h2>No Active Alerts</h2>
          <p>Create a price alert to get notified when a stock reaches your target price.</p>
        </div>
      ) : (
        <AlertsTable alerts={activeAlerts} onDelete={(id) => setDeleteConfirmId(id)} />
      )}

      {/* Delete Confirmation */}
      {deleteConfirmId && (
        <div className="modal-overlay" onClick={() => setDeleteConfirmId(null)} role="alertdialog" aria-modal="true" aria-label="Confirm delete alert">
          <div className="modal-content modal-sm" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Delete Alert</h2>
            </div>
            <p>Are you sure you want to delete this price alert?</p>
            <div className="form-actions">
              <button className="btn btn-secondary" onClick={() => setDeleteConfirmId(null)}>
                Cancel
              </button>
              <button className="btn btn-danger" onClick={() => handleDelete(deleteConfirmId)}>
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ===== Alerts Table Component =====

interface AlertsTableProps {
  alerts: PriceAlert[];
  onDelete: (id: string) => void;
  rowClassName?: string;
}

function AlertsTable({ alerts, onDelete, rowClassName }: AlertsTableProps) {
  const { sortedItems, requestSort, getSortIndicator } = useSortableData(alerts);
  const { paginatedItems, currentPage, totalItems, itemsPerPage, setPage, setPerPage } = usePagination(sortedItems);

  return (
    <div className="table-container">
      <table className="data-table" aria-label="Price alerts">
        <thead>
          <tr>
            <th scope="col" className="sortable-th" onClick={() => requestSort('stock_symbol')}>Symbol{getSortIndicator('stock_symbol')}</th>
            <th scope="col" className="sortable-th" onClick={() => requestSort('alert_type')}>Type{getSortIndicator('alert_type')}</th>
            <th scope="col" className="sortable-th number-col" onClick={() => requestSort('target_price')}>Target Price{getSortIndicator('target_price')}</th>
            <th scope="col">Note</th>
            <th scope="col">Created</th>
            <th scope="col">Actions</th>
          </tr>
        </thead>
        <tbody>
          {paginatedItems.map((alert) => (
            <tr key={alert.id} className={rowClassName}>
              <td className="symbol-cell">{alert.stock_symbol}</td>
              <td>
                <span className={alert.alert_type === 'Above' ? 'badge badge-above' : 'badge badge-below'}>
                  {alert.alert_type === 'Above' ? '📈' : '📉'} {alert.alert_type}
                </span>
              </td>
              <td className="number-cell">{formatTHB(alert.target_price)}</td>
              <td>{alert.note || '-'}</td>
              <td>{formatDateTime(alert.created_at)}</td>
              <td>
                <button
                  className="btn btn-icon btn-danger"
                  onClick={() => onDelete(alert.id)}
                  aria-label={`Delete alert for ${alert.stock_symbol}`}
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
