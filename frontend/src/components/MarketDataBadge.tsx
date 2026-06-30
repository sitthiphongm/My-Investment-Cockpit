import { formatDateTime } from '../utils/format';

/**
 * MarketDataBadge - Displays the last market data refresh timestamp.
 * Shows "Last refreshed: {timestamp}" or "No data available" when no timestamp exists.
 */

export interface MarketDataBadgeProps {
  /** ISO timestamp of last refresh, or null/undefined if never refreshed */
  lastRefresh: string | null | undefined;
  /** Optional className for custom styling */
  className?: string;
}

export default function MarketDataBadge({ lastRefresh, className = '' }: MarketDataBadgeProps) {
  const baseClass = 'market-data-badge';
  const classes = [baseClass, className].filter(Boolean).join(' ');

  return (
    <span
      className={classes}
      aria-label="Market data refresh status"
      role="status"
    >
      {lastRefresh ? (
        <>
          <span className="market-data-badge__icon" aria-hidden="true">🔄</span>
          <span className="market-data-badge__text">
            Last refreshed: {formatDateTime(lastRefresh)}
          </span>
        </>
      ) : (
        <>
          <span className="market-data-badge__icon" aria-hidden="true">⚠️</span>
          <span className="market-data-badge__text">No data available</span>
        </>
      )}
    </span>
  );
}
