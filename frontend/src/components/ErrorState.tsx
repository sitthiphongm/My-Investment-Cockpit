import type { ReactNode } from 'react';

/**
 * ErrorState - Error display component with retry/fallback guidance.
 * Uses dark theme tokens with negative color accents (#EF4444).
 */

export interface ErrorStateProps {
  /** Error title */
  title?: string;
  /** Error message or description */
  message?: string;
  /** Optional retry callback */
  onRetry?: () => void;
  /** Optional custom action */
  action?: ReactNode;
  /** Optional icon */
  icon?: ReactNode;
  /** Optional className */
  className?: string;
}

export default function ErrorState({
  title = 'Something went wrong',
  message = 'An error occurred while loading data. Please try again.',
  onRetry,
  action,
  icon = '⚠️',
  className = '',
}: ErrorStateProps) {
  return (
    <div className={`error-state ${className}`} role="alert" aria-label={title}>
      <div className="error-state__icon" aria-hidden="true">
        {icon}
      </div>
      <h2 className="error-state__title">{title}</h2>
      <p className="error-state__message">{message}</p>
      <div className="error-state__actions">
        {onRetry && (
          <button className="btn btn-primary btn-sm" onClick={onRetry}>
            Try Again
          </button>
        )}
        {action}
      </div>
    </div>
  );
}
