import { useCallback, useEffect, useState } from 'react';
import { transfersApi } from '../api';
import type { Transfer, TransferCreate, TransferUpdate, TransferFilters, TransferType, Currency } from '../types';
import { TransferType as TransferTypeEnum, Currency as CurrencyEnum } from '../types';
import { formatUSD, formatDate } from '../utils/format';
import { useSortableData } from '../hooks/useSortableData';
import { usePagination } from '../hooks/usePagination';
import Pagination from '../components/Pagination';
import toast from 'react-hot-toast';

// ===== Helper Functions =====

function getTodayString(): string {
  return new Date().toISOString().slice(0, 10);
}

function formatFxRate(value: number | null | undefined): string {
  if (value == null) return '—';
  const num = typeof value === 'string' ? parseFloat(value as unknown as string) : value;
  if (isNaN(num)) return '—';
  return num.toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 6,
  });
}

function formatAmount2dp(value: number | null | undefined): string {
  if (value == null) return '—';
  const num = typeof value === 'string' ? parseFloat(value as unknown as string) : value;
  if (isNaN(num)) return '—';
  return num.toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

// ===== Types =====

interface TransferFormData {
  date: string;
  broker: string;
  transfer_type: TransferType;
  amount: string;
  original_currency: Currency;
  original_amount: string;
  fx_rate: string;
  fx_fee: string;
  note: string;
}

const EMPTY_FORM: TransferFormData = {
  date: getTodayString(),
  broker: '',
  transfer_type: TransferTypeEnum.IN,
  amount: '',
  original_currency: CurrencyEnum.USD,
  original_amount: '',
  fx_rate: '',
  fx_fee: '',
  note: '',
};

// ===== Main Component =====

export default function TransfersPage() {
  const [transfers, setTransfers] = useState<Transfer[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [formData, setFormData] = useState<TransferFormData>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);
  const [showImportExcel, setShowImportExcel] = useState(false);

  // Filters
  const [filters, setFilters] = useState<TransferFilters>({});
  const [filterBroker, setFilterBroker] = useState('');

  const fetchTransfers = useCallback(async () => {
    try {
      const result = await transfersApi.list(filters);
      setTransfers(result ?? []);
    } catch {
      // Error handled by interceptor
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => {
    fetchTransfers();
  }, [fetchTransfers]);

  // ===== Excel Export Handler =====
  const handleExportExcel = async () => {
    try {
      const blob = await transfersApi.exportExcel(filters);
      const url = window.URL.createObjectURL(new Blob([blob]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `transfers_${new Date().toISOString().slice(0, 10)}.xlsx`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      toast.success('Excel exported successfully', { duration: 4000 });
    } catch {
      // Error handled by interceptor
    }
  };

  // ===== Filter Handlers =====

  const applyFilters = () => {
    const newFilters: TransferFilters = {};
    if (filterBroker.trim()) newFilters.broker = filterBroker.trim();
    setFilters(newFilters);
  };

  const clearFilters = () => {
    setFilterBroker('');
    setFilters({});
  };

  // ===== Form Handlers =====

  const openCreateForm = () => {
    setEditingId(null);
    setFormData(EMPTY_FORM);
    setShowForm(true);
  };

  const openEditForm = (transfer: Transfer) => {
    setEditingId(transfer.id);
    setFormData({
      date: transfer.date,
      broker: transfer.broker,
      transfer_type: transfer.transfer_type,
      amount: String(transfer.amount),
      original_currency: (transfer.original_currency as Currency) || CurrencyEnum.USD,
      original_amount: transfer.original_amount != null ? String(transfer.original_amount) : '',
      fx_rate: transfer.fx_rate != null ? String(transfer.fx_rate) : '',
      fx_fee: transfer.fx_fee != null ? String(transfer.fx_fee) : '',
      note: transfer.note || '',
    });
    setShowForm(true);
  };

  const closeForm = () => {
    setShowForm(false);
    setEditingId(null);
  };

  const handleFormChange = (field: keyof TransferFormData, value: string) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);

    const isFx = formData.original_currency !== CurrencyEnum.USD;

    // For FX transfers, the USD amount is calculated from original_amount / fx_rate
    const amount = isFx
      ? parseFloat(formData.original_amount) / parseFloat(formData.fx_rate)
      : parseFloat(formData.amount);

    try {
      if (editingId) {
        const updateData: TransferUpdate = {
          date: formData.date,
          broker: formData.broker,
          transfer_type: formData.transfer_type,
          amount: parseFloat(amount.toFixed(2)),
          original_currency: formData.original_currency,
          original_amount: isFx ? parseFloat(formData.original_amount) : null,
          fx_rate: isFx ? parseFloat(formData.fx_rate) : null,
          fx_fee: formData.fx_fee ? parseFloat(formData.fx_fee) : null,
          note: formData.note || null,
        };
        await transfersApi.update(editingId, updateData);
        toast.success('Transfer updated successfully', { duration: 4000 });
      } else {
        const createData: TransferCreate = {
          date: formData.date,
          broker: formData.broker,
          transfer_type: formData.transfer_type,
          amount: parseFloat(amount.toFixed(2)),
          original_currency: formData.original_currency,
          original_amount: isFx ? parseFloat(formData.original_amount) : null,
          fx_rate: isFx ? parseFloat(formData.fx_rate) : null,
          fx_fee: formData.fx_fee ? parseFloat(formData.fx_fee) : null,
          note: formData.note || null,
        };
        await transfersApi.create(createData);
        toast.success('Transfer created successfully', { duration: 4000 });
      }
      closeForm();
      fetchTransfers();
    } catch {
      // Form data retained on failure — error shown by interceptor
    } finally {
      setSaving(false);
    }
  };

  // ===== Delete Handlers =====

  const handleDelete = async (id: string) => {
    try {
      await transfersApi.delete(id);
      toast.success('Transfer deleted successfully', { duration: 4000 });
      setDeleteConfirmId(null);
      fetchTransfers();
    } catch {
      // Error handled by interceptor
    }
  };

  // ===== Render =====

  if (loading) {
    return (
      <div className="page transfers-page">
        <h1>Money Transfers</h1>
        <p className="loading-text" aria-live="polite">Loading transfers...</p>
      </div>
    );
  }

  return (
    <div className="page transfers-page">
      <h1>Money Transfers</h1>
      <p>Track deposits and withdrawals across brokers.</p>

      {/* Action Buttons */}
      <div className="trading-actions">
        <button className="btn btn-primary" onClick={openCreateForm}>
          + New Transfer
        </button>
        <button className="btn btn-secondary" onClick={handleExportExcel}>
          📤 Export Excel
        </button>
        <button className="btn btn-secondary" onClick={() => setShowImportExcel(true)}>
          📥 Import Excel
        </button>
      </div>

      {/* Filter Panel */}
      <TransferFilterPanel
        broker={filterBroker}
        onBrokerChange={setFilterBroker}
        onApply={applyFilters}
        onClear={clearFilters}
      />

      {/* Transfer Table */}
      {transfers.length === 0 ? (
        <div className="empty-state" role="status">
          <div className="empty-state-icon">💰</div>
          <h2>No Transfers</h2>
          <p>No transfer records found. Create a new transfer to get started.</p>
        </div>
      ) : (
        <TransferTable
          transfers={transfers}
          onEdit={openEditForm}
          onDelete={(id) => setDeleteConfirmId(id)}
        />
      )}

      {/* Create/Edit Form Modal */}
      {showForm && (
        <TransferFormModal
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

      {/* Import Excel Modal */}
      {showImportExcel && (
        <TransferImportExcelModal
          onClose={() => setShowImportExcel(false)}
          onSuccess={() => { setShowImportExcel(false); fetchTransfers(); }}
        />
      )}
    </div>
  );
}

// ===== Filter Panel Component =====

interface TransferFilterPanelProps {
  broker: string;
  onBrokerChange: (v: string) => void;
  onApply: () => void;
  onClear: () => void;
}

function TransferFilterPanel({
  broker,
  onBrokerChange,
  onApply,
  onClear,
}: TransferFilterPanelProps) {
  return (
    <div className="filter-panel" role="search" aria-label="Transfer filters">
      <div className="filter-row">
        <div className="filter-field">
          <label htmlFor="filter-broker">Broker</label>
          <input
            id="filter-broker"
            type="text"
            placeholder="e.g. Webull"
            value={broker}
            onChange={(e) => onBrokerChange(e.target.value)}
          />
        </div>
      </div>
      <div className="filter-buttons">
        <button className="btn btn-primary btn-sm" onClick={onApply}>
          Apply Filter
        </button>
        <button className="btn btn-secondary btn-sm" onClick={onClear}>
          Clear
        </button>
      </div>
    </div>
  );
}

// ===== Transfer Table Component =====

interface TransferTableProps {
  transfers: Transfer[];
  onEdit: (transfer: Transfer) => void;
  onDelete: (id: string) => void;
}

function TransferTable({ transfers, onEdit, onDelete }: TransferTableProps) {
  const { sortedItems, requestSort, getSortIndicator } = useSortableData(transfers);
  const { paginatedItems, currentPage, totalItems, itemsPerPage, setPage, setPerPage } = usePagination(sortedItems);

  return (
    <div className="table-container">
      <table className="data-table" aria-label="Money transfers">
        <thead>
          <tr>
            <th scope="col" className="sortable-th" onClick={() => requestSort('date')}>Date{getSortIndicator('date')}</th>
            <th scope="col" className="sortable-th" onClick={() => requestSort('broker')}>Broker{getSortIndicator('broker')}</th>
            <th scope="col" className="sortable-th" onClick={() => requestSort('transfer_type')}>Type{getSortIndicator('transfer_type')}</th>
            <th scope="col" className="sortable-th" onClick={() => requestSort('original_currency')}>Currency{getSortIndicator('original_currency')}</th>
            <th scope="col" className="sortable-th number-col" onClick={() => requestSort('original_amount')}>Original Amount{getSortIndicator('original_amount')}</th>
            <th scope="col" className="sortable-th number-col" onClick={() => requestSort('fx_rate')}>FX Rate{getSortIndicator('fx_rate')}</th>
            <th scope="col" className="sortable-th number-col" onClick={() => requestSort('converted_usd_amount')}>Converted USD{getSortIndicator('converted_usd_amount')}</th>
            <th scope="col" className="sortable-th number-col" onClick={() => requestSort('amount')}>Amount (USD){getSortIndicator('amount')}</th>
            <th scope="col" className="sortable-th number-col" onClick={() => requestSort('fx_fee')}>Fee{getSortIndicator('fx_fee')}</th>
            <th scope="col">Note</th>
            <th scope="col">Actions</th>
          </tr>
        </thead>
        <tbody>
          {paginatedItems.map((transfer) => {
            const isUsd = !transfer.original_currency || transfer.original_currency === 'USD';
            return (
              <tr key={transfer.id}>
                <td>{formatDate(transfer.date)}</td>
                <td>{transfer.broker}</td>
                <td>
                  <span className={`action-badge action-${transfer.transfer_type.toLowerCase()}`}>
                    {transfer.transfer_type === 'In' ? '⬆️ In (Deposit)' : '⬇️ Out (Withdrawal)'}
                  </span>
                </td>
                <td>{transfer.original_currency || 'USD'}</td>
                <td className="number-cell">
                  {isUsd ? '—' : formatAmount2dp(transfer.original_amount)}
                </td>
                <td className="number-cell">
                  {isUsd ? '—' : formatFxRate(transfer.fx_rate)}
                </td>
                <td className="number-cell">
                  {isUsd ? '—' : formatUSD(transfer.converted_usd_amount)}
                </td>
                <td className="number-cell">{formatUSD(transfer.amount)}</td>
                <td className="number-cell">
                  {transfer.fx_fee != null ? formatAmount2dp(transfer.fx_fee) : '—'}
                </td>
                <td>{transfer.note || '—'}</td>
                <td className="actions-cell">
                  <button
                    className="btn btn-icon"
                    onClick={() => onEdit(transfer)}
                    title="Edit transfer"
                    aria-label={`Edit transfer ${transfer.broker} on ${transfer.date}`}
                  >
                    ✏️
                  </button>
                  <button
                    className="btn btn-icon btn-danger"
                    onClick={() => onDelete(transfer.id)}
                    title="Delete transfer"
                    aria-label={`Delete transfer ${transfer.broker} on ${transfer.date}`}
                  >
                    🗑️
                  </button>
                </td>
              </tr>
            );
          })}
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

// ===== Transfer Form Modal =====

interface TransferFormModalProps {
  editingId: string | null;
  formData: TransferFormData;
  saving: boolean;
  onChange: (field: keyof TransferFormData, value: string) => void;
  onSubmit: (e: React.FormEvent) => void;
  onClose: () => void;
}

function TransferFormModal({
  editingId,
  formData,
  saving,
  onChange,
  onSubmit,
  onClose,
}: TransferFormModalProps) {
  const isFx = formData.original_currency !== CurrencyEnum.USD;

  // Compute converted USD amount for display
  const computedUsd =
    isFx && formData.original_amount && formData.fx_rate
      ? parseFloat(formData.original_amount) / parseFloat(formData.fx_rate)
      : null;

  return (
    <div className="modal-overlay" onClick={onClose} role="dialog" aria-modal="true" aria-label={editingId ? 'Edit Transfer' : 'New Transfer'}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>{editingId ? 'Edit Transfer' : 'New Transfer'}</h2>
          <button className="btn btn-icon" onClick={onClose} aria-label="Close form">✕</button>
        </div>
        <form onSubmit={onSubmit} className="transfer-form">
          <div className="form-grid">
            <div className="form-field">
              <label htmlFor="tf-date">Date *</label>
              <input
                id="tf-date"
                type="date"
                value={formData.date}
                max={getTodayString()}
                onChange={(e) => onChange('date', e.target.value)}
                required
              />
            </div>
            <div className="form-field">
              <label htmlFor="tf-broker">Broker *</label>
              <input
                id="tf-broker"
                type="text"
                placeholder="e.g. Webull"
                value={formData.broker}
                onChange={(e) => onChange('broker', e.target.value)}
                maxLength={100}
                required
              />
            </div>
            <div className="form-field">
              <label htmlFor="tf-type">Transfer Type *</label>
              <select
                id="tf-type"
                value={formData.transfer_type}
                onChange={(e) => onChange('transfer_type', e.target.value)}
                required
              >
                <option value="In">In (Deposit)</option>
                <option value="Out">Out (Withdrawal)</option>
              </select>
            </div>
            <div className="form-field">
              <label htmlFor="tf-currency">Currency *</label>
              <select
                id="tf-currency"
                value={formData.original_currency}
                onChange={(e) => onChange('original_currency', e.target.value)}
                required
              >
                <option value="USD">USD</option>
                <option value="THB">THB</option>
              </select>
            </div>

            {/* USD-only: simple amount field */}
            {!isFx && (
              <div className="form-field">
                <label htmlFor="tf-amount">Amount (USD) *</label>
                <input
                  id="tf-amount"
                  type="number"
                  placeholder="0.00"
                  value={formData.amount}
                  onChange={(e) => onChange('amount', e.target.value)}
                  min={0.01}
                  max={999999999.99}
                  step="0.01"
                  required
                />
              </div>
            )}

            {/* FX fields: shown when currency is not USD */}
            {isFx && (
              <>
                <div className="form-field">
                  <label htmlFor="tf-original-amount">Amount in Original Currency ({formData.original_currency}) *</label>
                  <input
                    id="tf-original-amount"
                    type="number"
                    placeholder="0.00"
                    value={formData.original_amount}
                    onChange={(e) => onChange('original_amount', e.target.value)}
                    min={0.01}
                    step="0.01"
                    required
                  />
                </div>
                <div className="form-field">
                  <label htmlFor="tf-fx-rate">FX Rate ({formData.original_currency}/USD) *</label>
                  <input
                    id="tf-fx-rate"
                    type="number"
                    placeholder="e.g. 35.50"
                    value={formData.fx_rate}
                    onChange={(e) => onChange('fx_rate', e.target.value)}
                    min={0.000001}
                    step="0.000001"
                    required
                  />
                </div>
                <div className="form-field">
                  <label>Converted USD Amount</label>
                  <div className="computed-value" aria-live="polite">
                    {computedUsd != null && !isNaN(computedUsd)
                      ? formatUSD(computedUsd)
                      : '—'}
                  </div>
                </div>
              </>
            )}

            {/* Optional FX Fee */}
            <div className="form-field">
              <label htmlFor="tf-fx-fee">FX Fee (optional)</label>
              <input
                id="tf-fx-fee"
                type="number"
                placeholder="0.00"
                value={formData.fx_fee}
                onChange={(e) => onChange('fx_fee', e.target.value)}
                min={0}
                step="0.01"
              />
            </div>

            {/* Optional Note */}
            <div className="form-field">
              <label htmlFor="tf-note">Note (optional)</label>
              <input
                id="tf-note"
                type="text"
                placeholder="Transfer note..."
                value={formData.note}
                onChange={(e) => onChange('note', e.target.value)}
                maxLength={500}
              />
            </div>
          </div>

          <div className="form-actions">
            <button type="button" className="btn btn-secondary" onClick={onClose} disabled={saving}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? 'Saving...' : editingId ? 'Update' : 'Create'}
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
    <div className="modal-overlay" onClick={onCancel} role="alertdialog" aria-modal="true" aria-label="Confirm deletion">
      <div className="modal-content modal-sm" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Confirm Delete</h2>
        </div>
        <p>Are you sure you want to delete this transfer? This action cannot be undone.</p>
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


// ===== Transfer Import Excel Modal =====

function TransferImportExcelModal({ onClose, onSuccess }: { onClose: () => void; onSuccess: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [importing, setImporting] = useState(false);
  const [preview, setPreview] = useState<any>(null);

  const handlePreview = async () => {
    if (!file) return;
    setPreviewing(true);
    try {
      const result = await transfersApi.importExcelPreview(file);
      setPreview(result);
    } catch { toast.error('Failed to preview file', { duration: 4000 }); }
    finally { setPreviewing(false); }
  };

  const handleImport = async () => {
    if (!file) return;
    setImporting(true);
    try {
      const result = await transfersApi.importExcel(file);
      toast.success(result.message || `Imported ${result.imported_count} transfers`, { duration: 4000 });
      onSuccess();
    } catch { toast.error('Import failed', { duration: 4000 }); }
    finally { setImporting(false); }
  };

  const canImport = preview && preview.valid_rows > 0 && preview.error_rows.length === 0 && preview.duplicate_rows.length === 0;

  return (
    <div className="modal-overlay" onClick={onClose} role="dialog" aria-modal="true" aria-label="Import Excel">
      <div className="modal-content modal-wide" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Import Transfers from Excel</h2>
          <button className="btn btn-icon" onClick={onClose} aria-label="Close">✕</button>
        </div>
        <div className="import-excel-body">
          <div className="form-field">
            <label htmlFor="transfer-excel-file">Select Excel File (.xlsx)</label>
            <input id="transfer-excel-file" type="file" accept=".xlsx" onChange={(e) => { setFile(e.target.files?.[0] ?? null); setPreview(null); }} />
          </div>
          {file && !preview && (
            <div className="form-actions">
              <button className="btn btn-primary" onClick={handlePreview} disabled={previewing}>
                {previewing ? 'Validating...' : '🔍 Preview & Validate'}
              </button>
            </div>
          )}
          {preview && (
            <div className="import-preview">
              <div className="import-summary">
                <span className="badge badge-info">Total: {preview.total_rows}</span>
                <span className="badge badge-positive">Valid: {preview.valid_rows}</span>
                {preview.duplicate_rows.length > 0 && <span className="badge badge-warning">Duplicates: {preview.duplicate_rows.length}</span>}
                {preview.error_rows.length > 0 && <span className="badge badge-negative">Errors: {preview.error_rows.length}</span>}
              </div>
              {preview.error_rows.length > 0 && (
                <div className="import-errors"><h4 className="text-negative">❌ Errors</h4><ul>{preview.error_rows.map((e: any, i: number) => <li key={i} className="text-negative">Row {e.row_number}: {e.field} — {e.error}</li>)}</ul></div>
              )}
              {preview.duplicate_rows.length > 0 && (
                <div className="import-duplicates"><h4 className="text-warning">⚠️ Duplicates</h4><ul>{preview.duplicate_rows.map((d: any, i: number) => <li key={i} className="text-warning">Row {d.row_number}: {d.reason}</li>)}</ul></div>
              )}
              <div className="form-actions">
                <button className="btn btn-secondary" onClick={onClose}>Cancel</button>
                <button className="btn btn-primary" onClick={handleImport} disabled={!canImport || importing}>
                  {importing ? 'Importing...' : `✅ Import ${preview.valid_rows} Transfers`}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
