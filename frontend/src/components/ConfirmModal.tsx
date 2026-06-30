import type { ReactNode } from 'react';

/**
 * ConfirmModal - Reusable destructive action confirmation modal.
 * Uses dark theme: surface background, blur backdrop, proper border radius (16px).
 * Follows existing modal-overlay + modal-content pattern in the codebase.
 */

export interface ConfirmModalProps {
  /** Whether the modal is open */
  open: boolean;
  /** Modal title */
  title?: string;
  /** Description text explaining the action */
  description?: string | ReactNode;
  /** Confirm button text */
  confirmText?: string;
  /** Cancel button text */
  cancelText?: string;
  /** Confirm button variant */
  confirmVariant?: 'danger' | 'primary' | 'success';
  /** Callback when confirmed */
  onConfirm: () => void;
  /** Callback when cancelled or modal closed */
  onCancel: () => void;
  /** Optional aria-label for the dialog */
  ariaLabel?: string;
}

export default function ConfirmModal({
  open,
  title = 'Confirm Action',
  description = 'Are you sure you want to proceed? This action cannot be undone.',
  confirmText = 'Confirm',
  cancelText = 'Cancel',
  confirmVariant = 'danger',
  onConfirm,
  onCancel,
  ariaLabel,
}: ConfirmModalProps) {
  if (!open) return null;

  const confirmBtnClass = `btn btn-${confirmVariant}`;

  return (
    <div
      className="modal-overlay"
      onClick={onCancel}
      role="alertdialog"
      aria-modal="true"
      aria-label={ariaLabel || title}
    >
      <div className="modal-content modal-sm" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>{title}</h2>
          <button className="btn-close" onClick={onCancel} aria-label="Close">
            ×
          </button>
        </div>
        <div className="modal-body">
          {typeof description === 'string' ? (
            <p className="modal-description">{description}</p>
          ) : (
            description
          )}
        </div>
        <div className="modal-footer">
          <button className="btn btn-secondary" onClick={onCancel}>
            {cancelText}
          </button>
          <button className={confirmBtnClass} onClick={onConfirm}>
            {confirmText}
          </button>
        </div>
      </div>
    </div>
  );
}
