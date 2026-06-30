import { useCallback, useEffect, useState } from 'react';
import { ideasApi, transactionsApi } from '../api';
import type {
  InvestmentIdea,
  InvestmentIdeaCreate,
  InvestmentIdeaUpdate,
  IdeaFilters,
  Transaction,
} from '../types';
import { IdeaStatus, RiskLevel } from '../types';
import { formatTHB, formatDate } from '../utils/format';
import toast from 'react-hot-toast';

// ===== Types =====

interface IdeaFormData {
  stock_symbol: string;
  title: string;
  thesis: string;
  target_entry_price: string;
  risk_level: string;
  source_link: string;
  status: string;
  linked_transaction_id: string;
}

const EMPTY_FORM: IdeaFormData = {
  stock_symbol: '',
  title: '',
  thesis: '',
  target_entry_price: '',
  risk_level: RiskLevel.MEDIUM,
  source_link: '',
  status: IdeaStatus.RESEARCHING,
  linked_transaction_id: '',
};

// ===== Main Component =====

export default function IdeasPage() {
  const [ideas, setIdeas] = useState<InvestmentIdea[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingIdea, setEditingIdea] = useState<InvestmentIdea | null>(null);
  const [formData, setFormData] = useState<IdeaFormData>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);

  // Filters
  const [filterStatus, setFilterStatus] = useState<string>('');
  const [filterRiskLevel, setFilterRiskLevel] = useState<string>('');
  const [filterSymbol, setFilterSymbol] = useState<string>('');

  // Transactions for linking
  const [transactions, setTransactions] = useState<Transaction[]>([]);

  const fetchIdeas = useCallback(async () => {
    try {
      const filters: IdeaFilters = {};
      if (filterStatus) filters.status = filterStatus as typeof IdeaStatus[keyof typeof IdeaStatus];
      if (filterRiskLevel) filters.risk_level = filterRiskLevel as typeof RiskLevel[keyof typeof RiskLevel];
      if (filterSymbol) filters.stock_symbol = filterSymbol.toUpperCase();
      const result = await ideasApi.list(filters);
      setIdeas(result ?? []);
    } catch {
      // Error handled by interceptor
    } finally {
      setLoading(false);
    }
  }, [filterStatus, filterRiskLevel, filterSymbol]);

  useEffect(() => {
    fetchIdeas();
  }, [fetchIdeas]);

  // ===== Form Handlers =====

  const openCreateForm = () => {
    setEditingIdea(null);
    setFormData(EMPTY_FORM);
    setShowForm(true);
  };

  const openEditForm = (idea: InvestmentIdea) => {
    setEditingIdea(idea);
    setFormData({
      stock_symbol: idea.stock_symbol,
      title: idea.title,
      thesis: idea.thesis,
      target_entry_price: idea.target_entry_price != null ? String(idea.target_entry_price) : '',
      risk_level: idea.risk_level,
      source_link: idea.source_link || '',
      status: idea.status,
      linked_transaction_id: idea.linked_transaction_id || '',
    });
    // Load transactions for linking if status is Bought
    if (idea.status === IdeaStatus.BOUGHT) {
      fetchTransactions(idea.stock_symbol);
    }
    setShowForm(true);
  };

  const closeForm = () => {
    setShowForm(false);
    setEditingIdea(null);
  };

  const fetchTransactions = async (symbol?: string) => {
    try {
      const filters = symbol ? { stock_symbol: symbol } : undefined;
      const result = await transactionsApi.list(filters);
      setTransactions(result ?? []);
    } catch {
      // silent
    }
  };

  const handleFormChange = (field: keyof IdeaFormData, value: string) => {
    setFormData((prev) => {
      const updated = { ...prev, [field]: value };
      // When status changes to Bought, load transactions for linking
      if (field === 'status' && value === IdeaStatus.BOUGHT) {
        fetchTransactions(prev.stock_symbol || undefined);
      }
      return updated;
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);

    const targetPrice = formData.target_entry_price
      ? parseFloat(formData.target_entry_price)
      : null;
    const sourceLink = formData.source_link.trim() || null;
    const linkedTxId = formData.linked_transaction_id || null;

    try {
      if (editingIdea) {
        const updateData: InvestmentIdeaUpdate = {
          stock_symbol: formData.stock_symbol.toUpperCase(),
          title: formData.title,
          thesis: formData.thesis,
          target_entry_price: targetPrice,
          risk_level: formData.risk_level as typeof RiskLevel[keyof typeof RiskLevel],
          source_link: sourceLink,
          status: formData.status as typeof IdeaStatus[keyof typeof IdeaStatus],
          linked_transaction_id: formData.status === IdeaStatus.BOUGHT ? linkedTxId : null,
        };
        await ideasApi.update(editingIdea.id, updateData);
        toast.success('Idea updated', { duration: 4000 });
      } else {
        const createData: InvestmentIdeaCreate = {
          stock_symbol: formData.stock_symbol.toUpperCase(),
          title: formData.title,
          thesis: formData.thesis,
          target_entry_price: targetPrice,
          risk_level: formData.risk_level as typeof RiskLevel[keyof typeof RiskLevel],
          source_link: sourceLink,
          status: formData.status as typeof IdeaStatus[keyof typeof IdeaStatus],
        };
        await ideasApi.create(createData);
        toast.success('Idea created', { duration: 4000 });
      }
      closeForm();
      fetchIdeas();
    } catch {
      // Form data retained on failure — error shown by interceptor
    } finally {
      setSaving(false);
    }
  };

  // ===== Delete Handlers =====

  const handleDelete = async (id: string) => {
    try {
      await ideasApi.delete(id);
      toast.success('Idea deleted', { duration: 4000 });
      setDeleteConfirmId(null);
      fetchIdeas();
    } catch {
      // Error handled by interceptor
    }
  };

  // ===== Filter Handlers =====

  const clearFilters = () => {
    setFilterStatus('');
    setFilterRiskLevel('');
    setFilterSymbol('');
  };

  const hasActiveFilters = filterStatus || filterRiskLevel || filterSymbol;

  // ===== Render =====

  if (loading) {
    return (
      <div className="page ideas-page">
        <h1>Investment Ideas</h1>
        <p className="loading-text" aria-live="polite">Loading ideas...</p>
      </div>
    );
  }

  return (
    <div className="page ideas-page">
      <h1>Investment Ideas</h1>
      <p>Track your investment thesis and research pipeline.</p>

      {/* Action Buttons */}
      <div className="trading-actions">
        <button className="btn btn-primary" onClick={openCreateForm}>
          + New Idea
        </button>
      </div>

      {/* Filter Panel */}
      <div className="filter-panel">
        <div className="filter-row">
          <div className="filter-field">
            <label htmlFor="filter-status">Status</label>
            <select
              id="filter-status"
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value)}
            >
              <option value="">All</option>
              {Object.values(IdeaStatus).map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </div>
          <div className="filter-field">
            <label htmlFor="filter-risk">Risk Level</label>
            <select
              id="filter-risk"
              value={filterRiskLevel}
              onChange={(e) => setFilterRiskLevel(e.target.value)}
            >
              <option value="">All</option>
              {Object.values(RiskLevel).map((r) => (
                <option key={r} value={r}>{r}</option>
              ))}
            </select>
          </div>
          <div className="filter-field">
            <label htmlFor="filter-symbol">Symbol</label>
            <input
              id="filter-symbol"
              type="text"
              placeholder="e.g. DRAM"
              value={filterSymbol}
              onChange={(e) => setFilterSymbol(e.target.value.toUpperCase())}
              maxLength={20}
            />
          </div>
          {hasActiveFilters && (
            <button className="btn btn-secondary btn-sm" onClick={clearFilters}>
              Clear Filters
            </button>
          )}
        </div>
      </div>

      {/* Ideas Cards */}
      {ideas.length === 0 ? (
        <div className="empty-state" role="status">
          <div className="empty-state-icon">💡</div>
          <h2>No Investment Ideas</h2>
          <p>
            {hasActiveFilters
              ? 'No ideas match your filters. Try adjusting or clearing them.'
              : 'Create your first investment idea to start tracking your research pipeline.'}
          </p>
        </div>
      ) : (
        <div className="ideas-grid">
          {ideas.map((idea) => (
            <IdeaCard
              key={idea.id}
              idea={idea}
              onEdit={openEditForm}
              onDelete={(id) => setDeleteConfirmId(id)}
            />
          ))}
        </div>
      )}

      {/* Create/Edit Form Modal */}
      {showForm && (
        <IdeaFormModal
          editingIdea={editingIdea}
          formData={formData}
          saving={saving}
          transactions={transactions}
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

// ===== Idea Card =====

interface IdeaCardProps {
  idea: InvestmentIdea;
  onEdit: (idea: InvestmentIdea) => void;
  onDelete: (id: string) => void;
}

function IdeaCard({ idea, onEdit, onDelete }: IdeaCardProps) {
  const statusBadgeClass = getStatusBadgeClass(idea.status);
  const riskBadgeClass = getRiskBadgeClass(idea.risk_level);

  return (
    <div className="idea-card" aria-label={`Idea: ${idea.title}`}>
      <div className="idea-card-header">
        <span className="idea-card-symbol">{idea.stock_symbol}</span>
        <div className="idea-card-badges">
          <span className={`badge ${statusBadgeClass}`}>{idea.status}</span>
          <span className={`badge ${riskBadgeClass}`}>{idea.risk_level} Risk</span>
        </div>
      </div>

      <h3 className="idea-card-title">{idea.title}</h3>

      <p className="idea-card-thesis">
        {idea.thesis.length > 150 ? idea.thesis.slice(0, 150) + '…' : idea.thesis}
      </p>

      <div className="idea-card-details">
        <div className="idea-card-detail">
          <span className="detail-label">Target Entry</span>
          <span className="detail-value">
            {idea.target_entry_price != null ? formatTHB(idea.target_entry_price) : '-'}
          </span>
        </div>
        <div className="idea-card-detail">
          <span className="detail-label">Updated</span>
          <span className="detail-value">{formatDate(idea.updated_at)}</span>
        </div>
      </div>

      {idea.source_link && (
        <a
          className="idea-card-source"
          href={idea.source_link}
          target="_blank"
          rel="noopener noreferrer"
          aria-label={`Source link for ${idea.title}`}
        >
          📎 Source
        </a>
      )}

      {idea.status === IdeaStatus.BOUGHT && idea.linked_transaction_id && (
        <div className="idea-card-linked">
          <span className="badge badge-linked">🔗 Linked to Transaction</span>
        </div>
      )}

      <div className="idea-card-actions">
        <button
          className="btn btn-icon"
          onClick={() => onEdit(idea)}
          title="Edit idea"
          aria-label={`Edit ${idea.title}`}
        >
          ✏️
        </button>
        <button
          className="btn btn-icon btn-danger"
          onClick={() => onDelete(idea.id)}
          title="Delete idea"
          aria-label={`Delete ${idea.title}`}
        >
          🗑️
        </button>
      </div>
    </div>
  );
}

// ===== Idea Form Modal =====

interface IdeaFormModalProps {
  editingIdea: InvestmentIdea | null;
  formData: IdeaFormData;
  saving: boolean;
  transactions: Transaction[];
  onChange: (field: keyof IdeaFormData, value: string) => void;
  onSubmit: (e: React.FormEvent) => void;
  onClose: () => void;
}

function IdeaFormModal({
  editingIdea,
  formData,
  saving,
  transactions,
  onChange,
  onSubmit,
  onClose,
}: IdeaFormModalProps) {
  const showLinkedTransaction = formData.status === IdeaStatus.BOUGHT;

  return (
    <div
      className="modal-overlay"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label={editingIdea ? 'Edit Investment Idea' : 'Create Investment Idea'}
    >
      <div className="modal-content modal-lg" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>{editingIdea ? 'Edit Idea' : 'New Idea'}</h2>
          <button className="btn btn-icon" onClick={onClose} aria-label="Close form">✕</button>
        </div>
        <form onSubmit={onSubmit} className="idea-form">
          <div className="form-grid">
            <div className="form-field">
              <label htmlFor="idea-symbol">Stock Symbol *</label>
              <input
                id="idea-symbol"
                type="text"
                placeholder="e.g. DRAM"
                value={formData.stock_symbol}
                onChange={(e) => onChange('stock_symbol', e.target.value.toUpperCase())}
                maxLength={20}
                required
              />
            </div>

            <div className="form-field">
              <label htmlFor="idea-status">Status *</label>
              <select
                id="idea-status"
                value={formData.status}
                onChange={(e) => onChange('status', e.target.value)}
                required
              >
                {Object.values(IdeaStatus).map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </div>

            <div className="form-field form-field-full">
              <label htmlFor="idea-title">Title *</label>
              <input
                id="idea-title"
                type="text"
                placeholder="Brief title for this idea"
                value={formData.title}
                onChange={(e) => onChange('title', e.target.value)}
                maxLength={200}
                required
              />
            </div>

            <div className="form-field form-field-full">
              <label htmlFor="idea-thesis">Thesis *</label>
              <textarea
                id="idea-thesis"
                placeholder="Why are you interested in this stock? What's the investment case?"
                value={formData.thesis}
                onChange={(e) => onChange('thesis', e.target.value)}
                maxLength={2000}
                rows={4}
                required
              />
              <span className="char-count">{formData.thesis.length}/2000</span>
            </div>

            <div className="form-field">
              <label htmlFor="idea-target-price">Target Entry Price (USD)</label>
              <input
                id="idea-target-price"
                type="number"
                placeholder="Target price to enter"
                value={formData.target_entry_price}
                onChange={(e) => onChange('target_entry_price', e.target.value)}
                min={0.01}
                step="0.01"
              />
            </div>

            <div className="form-field">
              <label htmlFor="idea-risk">Risk Level *</label>
              <select
                id="idea-risk"
                value={formData.risk_level}
                onChange={(e) => onChange('risk_level', e.target.value)}
                required
              >
                {Object.values(RiskLevel).map((r) => (
                  <option key={r} value={r}>{r}</option>
                ))}
              </select>
            </div>

            <div className="form-field form-field-full">
              <label htmlFor="idea-source">Source / Link</label>
              <input
                id="idea-source"
                type="url"
                placeholder="https://..."
                value={formData.source_link}
                onChange={(e) => onChange('source_link', e.target.value)}
                maxLength={500}
              />
            </div>

            {showLinkedTransaction && (
              <div className="form-field form-field-full">
                <label htmlFor="idea-linked-tx">Link to Transaction</label>
                <select
                  id="idea-linked-tx"
                  value={formData.linked_transaction_id}
                  onChange={(e) => onChange('linked_transaction_id', e.target.value)}
                >
                  <option value="">— No linked transaction —</option>
                  {transactions.map((tx) => (
                    <option key={tx.id} value={tx.id}>
                      {tx.date} | {tx.stock_symbol} | {tx.action} | {tx.quantity} @ {formatTHB(tx.price_per_share)}
                    </option>
                  ))}
                </select>
                <span className="form-hint">
                  Link this idea to the buy transaction that executed it.
                </span>
              </div>
            )}
          </div>

          <div className="form-actions">
            <button type="button" className="btn btn-secondary" onClick={onClose} disabled={saving}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? 'Saving...' : editingIdea ? 'Update Idea' : 'Create Idea'}
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
          <h2>Delete Idea</h2>
        </div>
        <p>Are you sure you want to delete this investment idea? This action cannot be undone.</p>
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

// ===== Helper Functions =====

function getStatusBadgeClass(status: string): string {
  switch (status) {
    case IdeaStatus.RESEARCHING:
      return 'badge-researching';
    case IdeaStatus.WATCHING:
      return 'badge-watching';
    case IdeaStatus.BOUGHT:
      return 'badge-bought';
    case IdeaStatus.PASSED:
      return 'badge-passed';
    case IdeaStatus.CLOSED:
      return 'badge-closed';
    default:
      return 'badge-muted';
  }
}

function getRiskBadgeClass(risk: string): string {
  switch (risk) {
    case RiskLevel.LOW:
      return 'badge-risk-low';
    case RiskLevel.MEDIUM:
      return 'badge-risk-medium';
    case RiskLevel.HIGH:
      return 'badge-risk-high';
    default:
      return 'badge-muted';
  }
}
