import type { ReactNode } from 'react';

/**
 * EmptyState - Reusable component for empty data states with action guidance.
 * Uses dark theme tokens: card-bg (#0F172A), dashed border (#1E293B), 16px radius.
 */

export interface EmptyStateProps {
  /** Icon or emoji to display */
  icon?: ReactNode;
  /** Title text */
  title: string;
  /** Description/guidance text */
  description?: string;
  /** Optional action button */
  action?: ReactNode;
  /** Optional className */
  className?: string;
}

export default function EmptyState({
  icon = '📭',
  title,
  description,
  action,
  className = '',
}: EmptyStateProps) {
  return (
    <div className={`empty-state ${className}`} role="status" aria-label={title}>
      <div className="empty-state-icon" aria-hidden="true">
        {icon}
      </div>
      <h2>{title}</h2>
      {description && <p>{description}</p>}
      {action && <div className="empty-state__action">{action}</div>}
    </div>
  );
}
