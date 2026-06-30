/**
 * LoadingSkeleton - Content loading placeholder component.
 * Uses dark surface colors for the shimmer effect (not light grey).
 * Respects design token: surface #0F172A, elevated #111827, border #1E293B.
 */

export interface LoadingSkeletonProps {
  /** Number of skeleton rows to display */
  rows?: number;
  /** Variant of skeleton layout */
  variant?: 'card' | 'table' | 'text' | 'metric';
  /** Optional className for additional styling */
  className?: string;
}

export default function LoadingSkeleton({
  rows = 3,
  variant = 'text',
  className = '',
}: LoadingSkeletonProps) {
  const classes = ['loading-skeleton', `loading-skeleton--${variant}`, className]
    .filter(Boolean)
    .join(' ');

  if (variant === 'metric') {
    return (
      <div className={classes} role="status" aria-label="Loading metrics">
        <span className="sr-only">Loading...</span>
        <div className="loading-skeleton__metrics">
          {Array.from({ length: rows }, (_, i) => (
            <div key={i} className="loading-skeleton__metric-card">
              <div className="loading-skeleton__line loading-skeleton__line--short" />
              <div className="loading-skeleton__line loading-skeleton__line--wide" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (variant === 'card') {
    return (
      <div className={classes} role="status" aria-label="Loading content">
        <span className="sr-only">Loading...</span>
        {Array.from({ length: rows }, (_, i) => (
          <div key={i} className="loading-skeleton__card">
            <div className="loading-skeleton__line loading-skeleton__line--short" />
            <div className="loading-skeleton__line loading-skeleton__line--wide" />
            <div className="loading-skeleton__line loading-skeleton__line--medium" />
          </div>
        ))}
      </div>
    );
  }

  if (variant === 'table') {
    return (
      <div className={classes} role="status" aria-label="Loading table">
        <span className="sr-only">Loading...</span>
        <div className="loading-skeleton__table-header">
          {Array.from({ length: 5 }, (_, i) => (
            <div key={i} className="loading-skeleton__line loading-skeleton__line--cell" />
          ))}
        </div>
        {Array.from({ length: rows }, (_, i) => (
          <div key={i} className="loading-skeleton__table-row">
            {Array.from({ length: 5 }, (_, j) => (
              <div key={j} className="loading-skeleton__line loading-skeleton__line--cell" />
            ))}
          </div>
        ))}
      </div>
    );
  }

  // Default: text variant
  return (
    <div className={classes} role="status" aria-label="Loading content">
      <span className="sr-only">Loading...</span>
      {Array.from({ length: rows }, (_, i) => (
        <div
          key={i}
          className={`loading-skeleton__line ${i % 3 === 0 ? 'loading-skeleton__line--short' : i % 3 === 1 ? 'loading-skeleton__line--wide' : 'loading-skeleton__line--medium'}`}
        />
      ))}
    </div>
  );
}
