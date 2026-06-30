import { useCallback, useEffect, useState, useMemo } from 'react';
import { transactionsApi } from '../api';
import type { Transaction, TransactionCreate, TransactionUpdate, TransactionFilters, SnapshotEntry, ActionType } from '../types';
import { ActionType as ActionEnum } from '../types';
import { formatTHB, formatDate, toNum } from '../utils/format';
import { useSortableData } from '../hooks/useSortableData';
import Pagination from '../components/Pagination';
import toast from 'react-hot-toast';

// ===== Helper Functions =====

function getTodayString(): string {
  return new Date().toISOString().slice(0, 10);
}

function calcGrossValue(qty: number, price: number): number {
  return qty * price;
}

function calcNetCapitalFlow(action: ActionType, grossValue: number, fee: number, vat: number): number {
  if (action === ActionEnum.BUY || action === ActionEnum.SNAPSHOT) {
    return grossValue + fee + vat;
  }
  return grossValue - fee - vat;
}

// ===== Types =====

interface TransactionFormData {
  date: string;
  stock_symbol: string;
  action: ActionType;
  quantity: string;
  price_per_share: string;
  brokerage_fee: string;
  vat: string;
  broker: string;
}

const EMPTY_FORM: TransactionFormData = {
  date: getTodayString(),
  stock_symbol: '',
  action: ActionEnum.BUY,
  quantity: '',
  price_per_share: '',
  brokerage_fee: '',
  vat: '',
  broker: '',
};

interface SnapshotFormEntry {
  stock_symbol: string;
  quantity: string;
  price_per_share: string;
  broker: string;
}

const EMPTY_SNAPSHOT_ENTRY: SnapshotFormEntry = {
  stock_symbol: '',
  quantity: '',
  price_per_share: '',
  broker: '',
};

// ===== Main Component =====

export default function TradingPage() {
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [showSnapshotForm, setShowSnapshotForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [formData, setFormData] = useState<TransactionFormData>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);

  // Filters
  const [filters, setFilters] = useState<TransactionFilters>({});
  const [filterDateFrom, setFilterDateFrom] = useState('');
  const [filterDateTo, setFilterDateTo] = useState('');
  const [filterSymbol, setFilterSymbol] = useState('');
  const [filterBroker, setFilterBroker] = useState('');
  const [filterAction, setFilterAction] = useState('');

  // Snapshot import
  const [snapshotEntries, setSnapshotEntries] = useState<SnapshotFormEntry[]>([
    { ...EMPTY_SNAPSHOT_ENTRY },
  ]);
  const [importingSnapshot, setImportingSnapshot] = useState(false);

  // Excel import
  const [showImportExcel, setShowImportExcel] = useState(false);

  const fetchTransactions = useCallback(async () => {
    try {
      const result = await transactionsApi.list(filters);
      setTransactions(result ?? []);
    } catch {
      // Error handled by interceptor
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => {
    fetchTransactions();
  }, [fetchTransactions]);

  // ===== Filter Handlers =====

  const applyFilters = () => {
    const newFilters: TransactionFilters = {};
    if (filterDateFrom) newFilters.date_from = filterDateFrom;
    if (filterDateTo) newFilters.date_to = filterDateTo;
    if (filterSymbol.trim()) newFilters.stock_symbol = filterSymbol.trim().toUpperCase();
    if (filterBroker.trim()) newFilters.broker = filterBroker.trim();
    if (filterAction) newFilters.action = filterAction as ActionType;
    setFilters(newFilters);
  };

  const clearFilters = () => {
    setFilterDateFrom('');
    setFilterDateTo('');
    setFilterSymbol('');
    setFilterBroker('');
    setFilterAction('');
    setFilters({});
  };

  // ===== Form Handlers =====

  const openCreateForm = () => {
    setEditingId(null);
    setFormData(EMPTY_FORM);
    setShowForm(true);
    setShowSnapshotForm(false);
  };

  const openEditForm = (tx: Transaction) => {
    setEditingId(tx.id);
    setFormData({
      date: tx.date,
      stock_symbol: tx.stock_symbol,
      action: tx.action,
      quantity: String(Number(tx.quantity) || ''),
      price_per_share: String(Number(tx.price_per_share) || ''),
      brokerage_fee: String(Number(tx.brokerage_fee) || '0'),
      vat: String(Number(tx.vat) || '0'),
      broker: tx.broker,
    });
    setShowForm(true);
    setShowSnapshotForm(false);
  };

  const closeForm = () => {
    setShowForm(false);
    setEditingId(null);
  };

  const handleFormChange = (field: keyof TransactionFormData, value: string) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);

    const qty = parseFloat(formData.quantity);
    const price = parseFloat(formData.price_per_share);
    const fee = parseFloat(formData.brokerage_fee) || 0;
    const vatVal = parseFloat(formData.vat) || 0;

    try {
      if (editingId) {
        const updateData: TransactionUpdate = {
          date: formData.date,
          stock_symbol: formData.stock_symbol.toUpperCase(),
          action: formData.action,
          quantity: qty > 0 ? qty : undefined,
          price_per_share: price > 0 ? price : undefined,
          brokerage_fee: fee,
          vat: vatVal,
          broker: formData.broker,
        };
        await transactionsApi.update(editingId, updateData);
        toast.success('Transaction updated successfully', { duration: 4000 });
      } else {
        const createData: TransactionCreate = {
          date: formData.date,
          stock_symbol: formData.stock_symbol.toUpperCase(),
          action: formData.action,
          quantity: qty,
          price_per_share: price,
          brokerage_fee: fee,
          vat: vatVal,
          broker: formData.broker,
        };
        await transactionsApi.create(createData);
        toast.success('Transaction created successfully', { duration: 4000 });
      }
      closeForm();
      fetchTransactions();
    } catch {
      // Form data retained on failure — error shown by interceptor
    } finally {
      setSaving(false);
    }
  };

  // ===== Delete Handlers =====

  const handleDelete = async (id: string) => {
    try {
      await transactionsApi.delete(id);
      toast.success('Transaction deleted successfully', { duration: 4000 });
      setDeleteConfirmId(null);
      fetchTransactions();
    } catch {
      // Error handled by interceptor
    }
  };

  // ===== Snapshot Import Handlers =====

  const openSnapshotForm = () => {
    setSnapshotEntries([{ ...EMPTY_SNAPSHOT_ENTRY }]);
    setShowSnapshotForm(true);
    setShowForm(false);
  };

  const closeSnapshotForm = () => {
    setShowSnapshotForm(false);
  };

  const addSnapshotEntry = () => {
    setSnapshotEntries((prev) => [...prev, { ...EMPTY_SNAPSHOT_ENTRY }]);
  };

  const removeSnapshotEntry = (index: number) => {
    setSnapshotEntries((prev) => prev.filter((_, i) => i !== index));
  };

  const updateSnapshotEntry = (index: number, field: keyof SnapshotFormEntry, value: string) => {
    setSnapshotEntries((prev) =>
      prev.map((entry, i) => (i === index ? { ...entry, [field]: value } : entry))
    );
  };

  const handleSnapshotImport = async (e: React.FormEvent) => {
    e.preventDefault();
    setImportingSnapshot(true);

    const entries: SnapshotEntry[] = snapshotEntries.map((entry) => ({
      stock_symbol: entry.stock_symbol.toUpperCase(),
      quantity: parseFloat(entry.quantity),
      price_per_share: parseFloat(entry.price_per_share),
      broker: entry.broker,
    }));

    try {
      await transactionsApi.importSnapshot(entries);
      toast.success(`Successfully imported ${entries.length} snapshot entries`, { duration: 4000 });
      closeSnapshotForm();
      fetchTransactions();
    } catch {
      // Form data retained on failure — error shown by interceptor
    } finally {
      setImportingSnapshot(false);
    }
  };

  // ===== Excel Export Handler =====

  const handleExportExcel = async () => {
    try {
      const blob = await transactionsApi.exportExcel(filters);
      const url = window.URL.createObjectURL(new Blob([blob]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `trading_log_${new Date().toISOString().slice(0, 10)}.xlsx`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      toast.success('Excel exported successfully', { duration: 4000 });
    } catch {
      // Error handled by interceptor
    }
  };

  // ===== Computed Values for Form =====

  const formQty = parseFloat(formData.quantity) || 0;
  const formPrice = parseFloat(formData.price_per_share) || 0;
  const formFee = parseFloat(formData.brokerage_fee) || 0;
  const formVat = parseFloat(formData.vat) || 0;
  const formGrossValue = calcGrossValue(formQty, formPrice);
  const formNetCapitalFlow = calcNetCapitalFlow(formData.action, formGrossValue, formFee, formVat);

  // ===== Render =====

  if (loading) {
    return (
      <div className="page trading-page">
        <h1>Trading Log</h1>
        <p className="loading-text" aria-live="polite">Loading transactions...</p>
      </div>
    );
  }

  return (
    <div className="page trading-page">
      <h1>Trading Log</h1>
      <p>Record and manage your buy/sell transactions.</p>

      {/* Action Buttons */}
      <div className="trading-actions">
        <button className="btn btn-primary" onClick={openCreateForm}>
          + New Transaction
        </button>
        <button className="btn btn-secondary" onClick={openSnapshotForm}>
          📥 Import
        </button>
        <button className="btn btn-secondary" onClick={handleExportExcel}>
          📤 Export Excel
        </button>
      </div>

      {/* Filter Panel */}
      <FilterPanel
        dateFrom={filterDateFrom}
        dateTo={filterDateTo}
        symbol={filterSymbol}
        broker={filterBroker}
        action={filterAction}
        onDateFromChange={setFilterDateFrom}
        onDateToChange={setFilterDateTo}
        onSymbolChange={setFilterSymbol}
        onBrokerChange={setFilterBroker}
        onActionChange={setFilterAction}
        onApply={applyFilters}
        onClear={clearFilters}
      />

      {/* Transaction Table */}
      {transactions.length === 0 ? (
        <div className="empty-state" role="status">
          <div className="empty-state-icon">📊</div>
          <h2>No Transactions</h2>
          <p>No transactions found. Create a new transaction or import a snapshot to get started.</p>
        </div>
      ) : (
        <TransactionTable
          transactions={transactions}
          onEdit={openEditForm}
          onDelete={(id) => setDeleteConfirmId(id)}
        />
      )}

      {/* Create/Edit Form Modal */}
      {showForm && (
        <TransactionFormModal
          editingId={editingId}
          formData={formData}
          grossValue={formGrossValue}
          netCapitalFlow={formNetCapitalFlow}
          saving={saving}
          onChange={handleFormChange}
          onSubmit={handleSubmit}
          onClose={closeForm}
        />
      )}

      {/* Snapshot Import Modal */}
      {showSnapshotForm && (
        <SnapshotImportModal
          entries={snapshotEntries}
          importing={importingSnapshot}
          onAddEntry={addSnapshotEntry}
          onRemoveEntry={removeSnapshotEntry}
          onUpdateEntry={updateSnapshotEntry}
          onSubmit={handleSnapshotImport}
          onClose={closeSnapshotForm}
          onSwitchToExcel={() => {
            closeSnapshotForm();
            setShowImportExcel(true);
          }}
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
        <ImportExcelModal
          onClose={() => setShowImportExcel(false)}
          onSuccess={() => {
            setShowImportExcel(false);
            fetchTransactions();
          }}
          onSwitchToManual={() => {
            setShowImportExcel(false);
            openSnapshotForm();
          }}
        />
      )}
    </div>
  );
}

// ===== Filter Panel Component =====

interface FilterPanelProps {
  dateFrom: string;
  dateTo: string;
  symbol: string;
  broker: string;
  action: string;
  onDateFromChange: (v: string) => void;
  onDateToChange: (v: string) => void;
  onSymbolChange: (v: string) => void;
  onBrokerChange: (v: string) => void;
  onActionChange: (v: string) => void;
  onApply: () => void;
  onClear: () => void;
}

function FilterPanel({
  dateFrom,
  dateTo,
  symbol,
  broker,
  action,
  onDateFromChange,
  onDateToChange,
  onSymbolChange,
  onBrokerChange,
  onActionChange,
  onApply,
  onClear,
}: FilterPanelProps) {
  return (
    <div className="filter-panel" role="search" aria-label="Transaction filters">
      <div className="filter-row">
        <div className="filter-field">
          <label htmlFor="filter-date-from">From</label>
          <input
            id="filter-date-from"
            type="date"
            value={dateFrom}
            onChange={(e) => onDateFromChange(e.target.value)}
          />
        </div>
        <div className="filter-field">
          <label htmlFor="filter-date-to">To</label>
          <input
            id="filter-date-to"
            type="date"
            value={dateTo}
            onChange={(e) => onDateToChange(e.target.value)}
          />
        </div>
        <div className="filter-field">
          <label htmlFor="filter-symbol">Symbol</label>
          <input
            id="filter-symbol"
            type="text"
            placeholder="e.g. DRAM"
            value={symbol}
            onChange={(e) => onSymbolChange(e.target.value)}
          />
        </div>
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
        <div className="filter-field">
          <label htmlFor="filter-action">Action</label>
          <select
            id="filter-action"
            value={action}
            onChange={(e) => onActionChange(e.target.value)}
          >
            <option value="">All</option>
            <option value="Buy">Buy</option>
            <option value="Sell">Sell</option>
            <option value="Snapshot">Snapshot</option>
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

// ===== Transaction Table Component =====

interface TransactionTableProps {
  transactions: Transaction[];
  onEdit: (tx: Transaction) => void;
  onDelete: (id: string) => void;
}

function TransactionTable({ transactions, onEdit, onDelete }: TransactionTableProps) {
  const { sortedItems, requestSort, getSortIndicator } = useSortableData(transactions);
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage, setItemsPerPage] = useState(10);

  // Reset to page 1 when data changes
  const totalItems = sortedItems.length;
  const totalPages = Math.max(1, Math.ceil(totalItems / itemsPerPage));
  const safeCurrentPage = Math.min(currentPage, totalPages);

  const paginatedItems = useMemo(() => {
    const start = (safeCurrentPage - 1) * itemsPerPage;
    return sortedItems.slice(start, start + itemsPerPage);
  }, [sortedItems, safeCurrentPage, itemsPerPage]);

  const handlePageChange = (page: number) => {
    setCurrentPage(page);
  };

  const handleItemsPerPageChange = (perPage: number) => {
    setItemsPerPage(perPage);
    setCurrentPage(1);
  };

  return (
    <div className="table-container">
      <table className="data-table trading-table" aria-label="Trading transactions">
        <colgroup>
          <col className="col-date" />
          <col className="col-symbol" />
          <col className="col-action" />
          <col className="col-qty" />
          <col className="col-price" />
          <col className="col-gross" />
          <col className="col-fee" />
          <col className="col-vat" />
          <col className="col-net" />
          <col className="col-broker" />
          <col className="col-actions" />
        </colgroup>
        <thead>
          <tr>
            <th scope="col" className="sortable-th" onClick={() => requestSort('date')}>Date{getSortIndicator('date')}</th>
            <th scope="col" className="sortable-th" onClick={() => requestSort('stock_symbol')}>Symbol{getSortIndicator('stock_symbol')}</th>
            <th scope="col" className="sortable-th" onClick={() => requestSort('action')}>Action{getSortIndicator('action')}</th>
            <th scope="col" className="sortable-th number-col" onClick={() => requestSort('quantity')}>Qty{getSortIndicator('quantity')}</th>
            <th scope="col" className="sortable-th number-col" onClick={() => requestSort('price_per_share')}>Price{getSortIndicator('price_per_share')}</th>
            <th scope="col" className="sortable-th number-col" onClick={() => requestSort('gross_value')}>Gross Value{getSortIndicator('gross_value')}</th>
            <th scope="col" className="sortable-th number-col" onClick={() => requestSort('brokerage_fee')}>Fee{getSortIndicator('brokerage_fee')}</th>
            <th scope="col" className="sortable-th number-col" onClick={() => requestSort('vat')}>VAT{getSortIndicator('vat')}</th>
            <th scope="col" className="sortable-th number-col" onClick={() => requestSort('net_capital_flow')}>Net Capital Flow{getSortIndicator('net_capital_flow')}</th>
            <th scope="col" className="sortable-th" onClick={() => requestSort('broker')}>Broker{getSortIndicator('broker')}</th>
            <th scope="col">Actions</th>
          </tr>
        </thead>
        <tbody>
          {paginatedItems.map((tx) => (
            <tr key={tx.id}>
              <td>{formatDate(tx.date)}</td>
              <td className="symbol-cell">{tx.stock_symbol}</td>
              <td>
                <span className={`action-badge action-${tx.action.toLowerCase()}`}>
                  {tx.action === 'Snapshot' ? `${tx.action} (Snapshot)` : tx.action}
                </span>
              </td>
              <td className="number-cell">{toNum(tx.quantity).toLocaleString()}</td>
              <td className="number-cell">{formatTHB(tx.price_per_share)}</td>
              <td className="number-cell">{formatTHB(tx.gross_value)}</td>
              <td className="number-cell">{formatTHB(tx.brokerage_fee)}</td>
              <td className="number-cell">{formatTHB(tx.vat)}</td>
              <td className="number-cell">{formatTHB(tx.net_capital_flow)}</td>
              <td>{tx.broker}</td>
              <td className="actions-cell">
                <button
                  className="btn btn-icon"
                  onClick={() => onEdit(tx)}
                  title="Edit transaction"
                  aria-label={`Edit transaction ${tx.stock_symbol} on ${tx.date}`}
                >
                  ✏️
                </button>
                <button
                  className="btn btn-icon btn-danger"
                  onClick={() => onDelete(tx.id)}
                  title="Delete transaction"
                  aria-label={`Delete transaction ${tx.stock_symbol} on ${tx.date}`}
                >
                  🗑️
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <Pagination
        currentPage={safeCurrentPage}
        totalItems={totalItems}
        itemsPerPage={itemsPerPage}
        onPageChange={handlePageChange}
        onItemsPerPageChange={handleItemsPerPageChange}
      />
    </div>
  );
}

// ===== Transaction Form Modal =====

interface TransactionFormModalProps {
  editingId: string | null;
  formData: TransactionFormData;
  grossValue: number;
  netCapitalFlow: number;
  saving: boolean;
  onChange: (field: keyof TransactionFormData, value: string) => void;
  onSubmit: (e: React.FormEvent) => void;
  onClose: () => void;
}

function TransactionFormModal({
  editingId,
  formData,
  grossValue,
  netCapitalFlow,
  saving,
  onChange,
  onSubmit,
  onClose,
}: TransactionFormModalProps) {
  return (
    <div className="modal-overlay" onClick={onClose} role="dialog" aria-modal="true" aria-label={editingId ? 'Edit Transaction' : 'New Transaction'}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>{editingId ? 'Edit Transaction' : 'New Transaction'}</h2>
          <button className="btn btn-icon" onClick={onClose} aria-label="Close form">✕</button>
        </div>
        <form onSubmit={onSubmit} className="transaction-form">
          <div className="form-grid">
            <div className="form-field">
              <label htmlFor="tx-date">Date *</label>
              <input
                id="tx-date"
                type="date"
                value={formData.date}
                max={getTodayString()}
                onChange={(e) => onChange('date', e.target.value)}
                required
              />
            </div>
            <div className="form-field">
              <label htmlFor="tx-symbol">Symbol *</label>
              <input
                id="tx-symbol"
                type="text"
                placeholder="e.g. DRAM"
                value={formData.stock_symbol}
                onChange={(e) => onChange('stock_symbol', e.target.value.toUpperCase())}
                maxLength={20}
                required
              />
            </div>
            <div className="form-field">
              <label htmlFor="tx-action">Action *</label>
              <select
                id="tx-action"
                value={formData.action}
                onChange={(e) => onChange('action', e.target.value)}
                required
              >
                <option value="Buy">Buy</option>
                <option value="Sell">Sell</option>
              </select>
            </div>
            <div className="form-field">
              <label htmlFor="tx-quantity">Quantity *</label>
              <input
                id="tx-quantity"
                type="number"
                placeholder="0"
                value={formData.quantity}
                onChange={(e) => onChange('quantity', e.target.value)}
                min={0.000001}
                max={99999999}
                step="any"
                required
              />
            </div>
            <div className="form-field">
              <label htmlFor="tx-price">Price per Share (USD) *</label>
              <input
                id="tx-price"
                type="number"
                placeholder="0.00"
                value={formData.price_per_share}
                onChange={(e) => onChange('price_per_share', e.target.value)}
                min={0.01}
                max={99999999.99}
                step="0.01"
                required
              />
            </div>
            <div className="form-field">
              <label htmlFor="tx-fee">Brokerage Fee (USD)</label>
              <input
                id="tx-fee"
                type="number"
                placeholder="0.00"
                value={formData.brokerage_fee}
                onChange={(e) => onChange('brokerage_fee', e.target.value)}
                min={0}
                step="0.01"
              />
            </div>
            <div className="form-field">
              <label htmlFor="tx-vat">VAT (USD)</label>
              <input
                id="tx-vat"
                type="number"
                placeholder="0.00"
                value={formData.vat}
                onChange={(e) => onChange('vat', e.target.value)}
                min={0}
                step="0.01"
              />
            </div>
            <div className="form-field">
              <label htmlFor="tx-broker">Broker *</label>
              <input
                id="tx-broker"
                type="text"
                placeholder="e.g. Webull"
                value={formData.broker}
                onChange={(e) => onChange('broker', e.target.value)}
                maxLength={100}
                required
              />
            </div>
          </div>

          {/* Auto-calculated fields */}
          <div className="form-calculated">
            <div className="calculated-field">
              <span className="calculated-label">Gross Value:</span>
              <span className="calculated-value">{formatTHB(grossValue)}</span>
            </div>
            <div className="calculated-field">
              <span className="calculated-label">Net Capital Flow:</span>
              <span className="calculated-value">{formatTHB(netCapitalFlow)}</span>
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

// ===== Snapshot Import Modal =====

interface SnapshotImportModalProps {
  entries: SnapshotFormEntry[];
  importing: boolean;
  onAddEntry: () => void;
  onRemoveEntry: (index: number) => void;
  onUpdateEntry: (index: number, field: keyof SnapshotFormEntry, value: string) => void;
  onSubmit: (e: React.FormEvent) => void;
  onClose: () => void;
  onSwitchToExcel: () => void;
}

function SnapshotImportModal({
  entries,
  importing,
  onAddEntry,
  onRemoveEntry,
  onUpdateEntry,
  onSubmit,
  onClose,
  onSwitchToExcel,
}: SnapshotImportModalProps) {
  return (
    <div className="modal-overlay" onClick={onClose} role="dialog" aria-modal="true" aria-label="Import Data">
      <div className="modal-content modal-wide" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Import Data</h2>
          <button className="btn btn-icon" onClick={onClose} aria-label="Close form">✕</button>
        </div>

        {/* Tab Bar */}
        <div className="tab-bar" style={{ marginBottom: '1rem' }}>
          <button className="tab-btn active">📋 Manual Snapshot</button>
          <button className="tab-btn" onClick={onSwitchToExcel}>📤 Import from Excel</button>
        </div>

        <p className="modal-description">
          Bulk import your existing positions. All entries will be saved as snapshot entries.
        </p>
        <form onSubmit={onSubmit} className="snapshot-form">
          <div className="snapshot-entries">
            {entries.map((entry, index) => (
              <div key={index} className="snapshot-entry-row">
                <div className="form-field">
                  <label htmlFor={`snap-symbol-${index}`}>Symbol *</label>
                  <input
                    id={`snap-symbol-${index}`}
                    type="text"
                    placeholder="e.g. DRAM"
                    value={entry.stock_symbol}
                    onChange={(e) => onUpdateEntry(index, 'stock_symbol', e.target.value.toUpperCase())}
                    maxLength={20}
                    required
                  />
                </div>
                <div className="form-field">
                  <label htmlFor={`snap-qty-${index}`}>Quantity *</label>
                  <input
                    id={`snap-qty-${index}`}
                    type="number"
                    placeholder="0"
                    value={entry.quantity}
                    onChange={(e) => onUpdateEntry(index, 'quantity', e.target.value)}
                    min={0.000001}
                    step="any"
                    required
                  />
                </div>
                <div className="form-field">
                  <label htmlFor={`snap-price-${index}`}>Avg Cost (USD) *</label>
                  <input
                    id={`snap-price-${index}`}
                    type="number"
                    placeholder="0.00"
                    value={entry.price_per_share}
                    onChange={(e) => onUpdateEntry(index, 'price_per_share', e.target.value)}
                    min={0.01}
                    step="0.01"
                    required
                  />
                </div>
                <div className="form-field">
                  <label htmlFor={`snap-broker-${index}`}>Broker *</label>
                  <input
                    id={`snap-broker-${index}`}
                    type="text"
                    placeholder="e.g. Webull"
                    value={entry.broker}
                    onChange={(e) => onUpdateEntry(index, 'broker', e.target.value)}
                    maxLength={100}
                    required
                  />
                </div>
                {entries.length > 1 && (
                  <button
                    type="button"
                    className="btn btn-icon btn-danger"
                    onClick={() => onRemoveEntry(index)}
                    title="Remove entry"
                    aria-label={`Remove snapshot entry ${index + 1}`}
                  >
                    ✕
                  </button>
                )}
              </div>
            ))}
          </div>

          <button type="button" className="btn btn-secondary btn-sm" onClick={onAddEntry}>
            + Add Another Entry
          </button>

          <div className="form-actions">
            <button type="button" className="btn btn-secondary" onClick={onClose} disabled={importing}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={importing}>
              {importing ? 'Importing...' : `Import ${entries.length} ${entries.length === 1 ? 'Entry' : 'Entries'}`}
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
        <p>Are you sure you want to delete this transaction? This action cannot be undone.</p>
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

// ===== Import Excel Modal =====

interface ImportExcelModalProps {
  onClose: () => void;
  onSuccess: () => void;
  onSwitchToManual: () => void;
}

interface ImportPreviewResult {
  valid_rows: number;
  duplicate_rows: { row_number: number; reason: string }[];
  error_rows: { row_number: number; field: string; error: string }[];
  preview_data: {
    date: string;
    stock_symbol: string;
    action: string;
    quantity: number;
    price_per_share: number;
    fee: number;
    vat: number;
    broker: string;
    note: string;
  }[];
  total_rows: number;
}

function ImportExcelModal({ onClose, onSuccess, onSwitchToManual }: ImportExcelModalProps) {
  const [file, setFile] = useState<File | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [importing, setImporting] = useState(false);
  const [preview, setPreview] = useState<ImportPreviewResult | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0] ?? null;
    setFile(selected);
    setPreview(null);
  };

  const handlePreview = async () => {
    if (!file) return;
    setPreviewing(true);
    try {
      const result = await transactionsApi.importExcelPreview(file);
      setPreview(result);
    } catch {
      toast.error('Failed to preview Excel file', { duration: 4000 });
    } finally {
      setPreviewing(false);
    }
  };

  const handleImport = async () => {
    if (!file) return;
    setImporting(true);
    try {
      const result = await transactionsApi.importExcel(file);
      toast.success(result.message || `Imported ${result.imported_count} transactions`, { duration: 4000 });
      onSuccess();
    } catch {
      toast.error('Import failed. Check for duplicates or validation errors.', { duration: 4000 });
    } finally {
      setImporting(false);
    }
  };

  const canImport = preview && preview.valid_rows > 0 && preview.error_rows.length === 0 && preview.duplicate_rows.length === 0;

  return (
    <div className="modal-overlay" onClick={onClose} role="dialog" aria-modal="true" aria-label="Import Excel">
      <div className="modal-content modal-wide" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Import Data</h2>
          <button className="btn btn-icon" onClick={onClose} aria-label="Close">✕</button>
        </div>

        {/* Tab Bar */}
        <div className="tab-bar" style={{ marginBottom: '1rem' }}>
          <button className="tab-btn" onClick={onSwitchToManual}>📋 Manual Snapshot</button>
          <button className="tab-btn active">📤 Import from Excel</button>
        </div>

        <div className="import-excel-body">
          {/* File Upload */}
          <div className="form-field">
            <label htmlFor="excel-file">Select Excel File (.xlsx)</label>
            <input
              id="excel-file"
              type="file"
              accept=".xlsx"
              onChange={handleFileChange}
            />
          </div>

          {file && !preview && (
            <div className="form-actions">
              <button
                className="btn btn-primary"
                onClick={handlePreview}
                disabled={previewing}
              >
                {previewing ? 'Validating...' : '🔍 Preview & Validate'}
              </button>
            </div>
          )}

          {/* Preview Results */}
          {preview && (
            <div className="import-preview">
              {/* Summary */}
              <div className="import-summary">
                <span className="badge badge-info">Total Rows: {preview.total_rows}</span>
                <span className="badge badge-positive">Valid: {preview.valid_rows}</span>
                {preview.duplicate_rows.length > 0 && (
                  <span className="badge badge-warning">Duplicates: {preview.duplicate_rows.length}</span>
                )}
                {preview.error_rows.length > 0 && (
                  <span className="badge badge-negative">Errors: {preview.error_rows.length}</span>
                )}
              </div>

              {/* Errors */}
              {preview.error_rows.length > 0 && (
                <div className="import-errors">
                  <h4 className="text-negative">❌ Validation Errors</h4>
                  <ul>
                    {preview.error_rows.map((err, i) => (
                      <li key={i} className="text-negative">
                        Row {err.row_number}: <strong>{err.field}</strong> — {err.error}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Duplicates */}
              {preview.duplicate_rows.length > 0 && (
                <div className="import-duplicates">
                  <h4 className="text-warning">⚠️ Duplicate Entries (will be skipped)</h4>
                  <ul>
                    {preview.duplicate_rows.map((dup, i) => (
                      <li key={i} className="text-warning">
                        Row {dup.row_number}: {dup.reason}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Preview Table */}
              {preview.preview_data.length > 0 && (
                <div className="import-preview-table">
                  <h4>Preview (first {preview.preview_data.length} rows)</h4>
                  <div className="table-container">
                    <table className="data-table" aria-label="Import preview">
                      <thead>
                        <tr>
                          <th scope="col">Date</th>
                          <th scope="col">Symbol</th>
                          <th scope="col">Action</th>
                          <th scope="col" className="number-col">Qty</th>
                          <th scope="col" className="number-col">Price</th>
                          <th scope="col">Broker</th>
                        </tr>
                      </thead>
                      <tbody>
                        {preview.preview_data.map((row, i) => (
                          <tr key={i}>
                            <td>{row.date}</td>
                            <td className="symbol-cell">{row.stock_symbol}</td>
                            <td>{row.action}</td>
                            <td className="number-cell">{row.quantity}</td>
                            <td className="number-cell">${row.price_per_share.toFixed(2)}</td>
                            <td>{row.broker}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Import Button */}
              <div className="form-actions">
                <button className="btn btn-secondary" onClick={onClose}>
                  Cancel
                </button>
                <button
                  className="btn btn-primary"
                  onClick={handleImport}
                  disabled={!canImport || importing}
                >
                  {importing ? 'Importing...' : `✅ Import ${preview.valid_rows} Transactions`}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
