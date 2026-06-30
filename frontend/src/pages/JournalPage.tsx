import { useCallback, useEffect, useState } from 'react';
import { transactionsApi, journalApi } from '../api';
import type { Transaction, Tag, TransactionFilters } from '../types';
import { formatTHB, formatDate } from '../utils/format';
import toast from 'react-hot-toast';

// ===== Constants =====

const PREDEFINED_TAGS = [
  'Earnings Play',
  'Momentum',
  'Value',
  'Dividend',
  'Speculative',
  'Technical',
];

const MAX_NOTE_LENGTH = 1000;

// ===== Main Component =====

export default function JournalPage() {
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [tags, setTags] = useState<Tag[]>([]);
  const [loading, setLoading] = useState(true);

  // Filter state
  const [filterTag, setFilterTag] = useState('');

  // Note editing
  const [editingNoteId, setEditingNoteId] = useState<string | null>(null);
  const [noteText, setNoteText] = useState('');
  const [savingNote, setSavingNote] = useState(false);

  // Tag management modal
  const [managingTagsId, setManagingTagsId] = useState<string | null>(null);
  const [selectedTagIds, setSelectedTagIds] = useState<string[]>([]);
  const [newTagName, setNewTagName] = useState('');
  const [savingTags, setSavingTags] = useState(false);
  const [creatingTag, setCreatingTag] = useState(false);

  // ===== Data Fetching =====

  const fetchTags = useCallback(async () => {
    try {
      const result = await journalApi.listTags();
      setTags(result ?? []);
    } catch {
      // Error handled by interceptor
    }
  }, []);

  const fetchTransactions = useCallback(async () => {
    try {
      const filters: TransactionFilters = {};
      if (filterTag) filters.tag = filterTag;
      const result = await transactionsApi.list(filters);
      setTransactions(result ?? []);
    } catch {
      // Error handled by interceptor
    } finally {
      setLoading(false);
    }
  }, [filterTag]);

  useEffect(() => {
    fetchTags();
  }, [fetchTags]);

  useEffect(() => {
    fetchTransactions();
  }, [fetchTransactions]);

  // ===== Note Handlers =====

  const openNoteEditor = (tx: Transaction) => {
    setEditingNoteId(tx.id);
    setNoteText(tx.note || '');
  };

  const closeNoteEditor = () => {
    setEditingNoteId(null);
    setNoteText('');
  };

  const handleSaveNote = async () => {
    if (!editingNoteId) return;
    setSavingNote(true);
    try {
      await journalApi.updateNote(editingNoteId, noteText);
      toast.success('Note saved successfully', { duration: 4000 });
      closeNoteEditor();
      fetchTransactions();
    } catch {
      // Error handled by interceptor, form data retained
    } finally {
      setSavingNote(false);
    }
  };

  // ===== Tag Management Handlers =====

  const openTagManager = (tx: Transaction) => {
    setManagingTagsId(tx.id);
    // Find tag IDs that match this transaction's tags
    const txTagIds = tags
      .filter((t) => tx.tags.includes(t.name))
      .map((t) => t.id);
    setSelectedTagIds(txTagIds);
    setNewTagName('');
  };

  const closeTagManager = () => {
    setManagingTagsId(null);
    setSelectedTagIds([]);
    setNewTagName('');
  };

  const toggleTag = (tagId: string) => {
    setSelectedTagIds((prev) =>
      prev.includes(tagId) ? prev.filter((id) => id !== tagId) : [...prev, tagId]
    );
  };

  const handleCreateTag = async () => {
    const trimmed = newTagName.trim();
    if (!trimmed || trimmed.length > 50) return;
    setCreatingTag(true);
    try {
      const newTag = await journalApi.createTag(trimmed);
      setTags((prev) => [...prev, newTag]);
      setSelectedTagIds((prev) => [...prev, newTag.id]);
      setNewTagName('');
      toast.success('Tag created', { duration: 4000 });
    } catch {
      // Error handled by interceptor
    } finally {
      setCreatingTag(false);
    }
  };

  const handleDeleteTag = async (tagId: string) => {
    try {
      await journalApi.deleteTag(tagId);
      setTags((prev) => prev.filter((t) => t.id !== tagId));
      setSelectedTagIds((prev) => prev.filter((id) => id !== tagId));
      toast.success('Tag deleted', { duration: 4000 });
    } catch {
      // Error handled by interceptor
    }
  };

  const handleSaveTags = async () => {
    if (!managingTagsId) return;
    setSavingTags(true);
    try {
      await journalApi.updateTags(managingTagsId, selectedTagIds);
      toast.success('Tags updated successfully', { duration: 4000 });
      closeTagManager();
      fetchTransactions();
    } catch {
      // Error handled by interceptor
    } finally {
      setSavingTags(false);
    }
  };

  // ===== Filter Handlers =====

  const clearFilter = () => {
    setFilterTag('');
  };

  // ===== Render =====

  if (loading) {
    return (
      <div className="page journal-page">
        <h1>Trade Journal</h1>
        <p>Loading...</p>
      </div>
    );
  }

  return (
    <div className="page journal-page">
      <h1>Trade Journal</h1>
      <p>Review notes and tags on your transactions.</p>

      {/* Filter by Tag */}
      <FilterByTag
        tags={tags}
        filterTag={filterTag}
        onFilterChange={setFilterTag}
        onClear={clearFilter}
      />

      {/* Transaction List */}
      {transactions.length === 0 ? (
        <div className="empty-state">
          <p>No transactions found{filterTag ? ' for the selected tag' : ''}.</p>
        </div>
      ) : (
        <div className="journal-list">
          {transactions.map((tx) => (
            <JournalEntry
              key={tx.id}
              transaction={tx}
              tags={tags}
              isEditingNote={editingNoteId === tx.id}
              noteText={editingNoteId === tx.id ? noteText : ''}
              savingNote={savingNote}
              onEditNote={() => openNoteEditor(tx)}
              onNoteChange={setNoteText}
              onSaveNote={handleSaveNote}
              onCancelNote={closeNoteEditor}
              isManagingTags={managingTagsId === tx.id}
              onManageTags={() => openTagManager(tx)}
            />
          ))}
        </div>
      )}

      {/* Tag Management Modal */}
      {managingTagsId && (
        <TagManagerModal
          tags={tags}
          selectedTagIds={selectedTagIds}
          newTagName={newTagName}
          savingTags={savingTags}
          creatingTag={creatingTag}
          onToggleTag={toggleTag}
          onNewTagNameChange={setNewTagName}
          onCreateTag={handleCreateTag}
          onDeleteTag={handleDeleteTag}
          onSave={handleSaveTags}
          onClose={closeTagManager}
        />
      )}
    </div>
  );
}

// ===== Sub-Components =====

interface FilterByTagProps {
  tags: Tag[];
  filterTag: string;
  onFilterChange: (tagId: string) => void;
  onClear: () => void;
}

function FilterByTag({ tags, filterTag, onFilterChange, onClear }: FilterByTagProps) {
  return (
    <div className="filter-panel">
      <div className="filter-row">
        <label htmlFor="filter-tag">Filter by Tag:</label>
        <select
          id="filter-tag"
          value={filterTag}
          onChange={(e) => onFilterChange(e.target.value)}
        >
          <option value="">All transactions</option>
          {tags.map((tag) => (
            <option key={tag.id} value={tag.name}>
              {tag.name}
            </option>
          ))}
        </select>
        {filterTag && (
          <button type="button" className="btn btn-secondary" onClick={onClear}>
            Clear
          </button>
        )}
      </div>
    </div>
  );
}

interface JournalEntryProps {
  transaction: Transaction;
  tags: Tag[];
  isEditingNote: boolean;
  noteText: string;
  savingNote: boolean;
  onEditNote: () => void;
  onNoteChange: (text: string) => void;
  onSaveNote: () => void;
  onCancelNote: () => void;
  isManagingTags: boolean;
  onManageTags: () => void;
}

function JournalEntry({
  transaction,
  isEditingNote,
  noteText,
  savingNote,
  onEditNote,
  onNoteChange,
  onSaveNote,
  onCancelNote,
  onManageTags,
}: JournalEntryProps) {
  return (
    <div className="journal-entry">
      {/* Transaction Summary */}
      <div className="journal-entry-header">
        <div className="journal-entry-info">
          <span className={`action-badge action-${transaction.action.toLowerCase()}`}>
            {transaction.action}
          </span>
          <strong>{transaction.stock_symbol}</strong>
          <span className="journal-entry-detail">
            {transaction.quantity} shares @ {formatTHB(transaction.price_per_share)}
          </span>
          <span className="journal-entry-date">{formatDate(transaction.date)}</span>
          <span className="journal-entry-broker">{transaction.broker}</span>
        </div>
        <div className="journal-entry-value">
          {formatTHB(transaction.net_capital_flow)}
        </div>
      </div>

      {/* Tags Display */}
      <div className="journal-entry-tags">
        {transaction.tags.length > 0 ? (
          transaction.tags.map((tagName) => (
            <span key={tagName} className="tag-badge">
              {tagName}
            </span>
          ))
        ) : (
          <span className="no-tags">No tags</span>
        )}
        <button type="button" className="btn btn-sm btn-secondary" onClick={onManageTags}>
          Manage Tags
        </button>
      </div>

      {/* Note Section */}
      <div className="journal-entry-note">
        {isEditingNote ? (
          <div className="note-editor">
            <textarea
              value={noteText}
              onChange={(e) => onNoteChange(e.target.value)}
              maxLength={MAX_NOTE_LENGTH}
              rows={4}
              placeholder="Add your trade reasoning or notes here..."
              aria-label="Transaction note"
            />
            <div className="note-editor-footer">
              <span className="char-count">
                {noteText.length}/{MAX_NOTE_LENGTH}
              </span>
              <div className="note-editor-actions">
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={onCancelNote}
                  disabled={savingNote}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={onSaveNote}
                  disabled={savingNote}
                >
                  {savingNote ? 'Saving...' : 'Save Note'}
                </button>
              </div>
            </div>
          </div>
        ) : (
          <div className="note-display">
            {transaction.note ? (
              <p className="note-text">{transaction.note}</p>
            ) : (
              <p className="note-placeholder">No note attached</p>
            )}
            <button type="button" className="btn btn-sm btn-secondary" onClick={onEditNote}>
              {transaction.note ? 'Edit Note' : 'Add Note'}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

interface TagManagerModalProps {
  tags: Tag[];
  selectedTagIds: string[];
  newTagName: string;
  savingTags: boolean;
  creatingTag: boolean;
  onToggleTag: (tagId: string) => void;
  onNewTagNameChange: (name: string) => void;
  onCreateTag: () => void;
  onDeleteTag: (tagId: string) => void;
  onSave: () => void;
  onClose: () => void;
}

function TagManagerModal({
  tags,
  selectedTagIds,
  newTagName,
  savingTags,
  creatingTag,
  onToggleTag,
  onNewTagNameChange,
  onCreateTag,
  onDeleteTag,
  onSave,
  onClose,
}: TagManagerModalProps) {
  const predefinedTags = tags.filter((t) => PREDEFINED_TAGS.includes(t.name));
  const customTags = tags.filter((t) => !PREDEFINED_TAGS.includes(t.name));

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Manage Tags</h2>
          <button type="button" className="btn btn-close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>

        <div className="modal-body">
          {/* Predefined Tags */}
          {predefinedTags.length > 0 && (
            <div className="tag-section">
              <h3>Predefined Tags</h3>
              <div className="tag-list">
                {predefinedTags.map((tag) => (
                  <label key={tag.id} className="tag-checkbox">
                    <input
                      type="checkbox"
                      checked={selectedTagIds.includes(tag.id)}
                      onChange={() => onToggleTag(tag.id)}
                    />
                    <span>{tag.name}</span>
                  </label>
                ))}
              </div>
            </div>
          )}

          {/* Custom Tags */}
          <div className="tag-section">
            <h3>Custom Tags</h3>
            {customTags.length > 0 ? (
              <div className="tag-list">
                {customTags.map((tag) => (
                  <div key={tag.id} className="tag-checkbox-row">
                    <label className="tag-checkbox">
                      <input
                        type="checkbox"
                        checked={selectedTagIds.includes(tag.id)}
                        onChange={() => onToggleTag(tag.id)}
                      />
                      <span>{tag.name}</span>
                    </label>
                    <button
                      type="button"
                      className="btn btn-sm btn-danger"
                      onClick={() => onDeleteTag(tag.id)}
                      title="Delete tag"
                      aria-label={`Delete tag ${tag.name}`}
                    >
                      ×
                    </button>
                  </div>
                ))}
              </div>
            ) : (
              <p className="no-tags">No custom tags yet.</p>
            )}
          </div>

          {/* Create New Tag */}
          <div className="tag-section">
            <h3>Create New Tag</h3>
            <div className="create-tag-row">
              <input
                type="text"
                value={newTagName}
                onChange={(e) => onNewTagNameChange(e.target.value)}
                placeholder="Tag name (1-50 chars)"
                maxLength={50}
                aria-label="New tag name"
              />
              <button
                type="button"
                className="btn btn-secondary"
                onClick={onCreateTag}
                disabled={creatingTag || !newTagName.trim() || newTagName.trim().length > 50}
              >
                {creatingTag ? 'Creating...' : 'Add'}
              </button>
            </div>
          </div>
        </div>

        <div className="modal-footer">
          <button type="button" className="btn btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button
            type="button"
            className="btn btn-primary"
            onClick={onSave}
            disabled={savingTags}
          >
            {savingTags ? 'Saving...' : 'Save Tags'}
          </button>
        </div>
      </div>
    </div>
  );
}
