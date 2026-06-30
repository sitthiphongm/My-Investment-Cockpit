/**
 * FilterPanel - Reusable filter controls for date range, symbol, broker, and action type.
 * Used across Trading Log, Transfers, and other pages that need filtering.
 */

export interface FilterPanelProps {
  /** Date range start value (YYYY-MM-DD) */
  dateFrom?: string;
  /** Date range end value (YYYY-MM-DD) */
  dateTo?: string;
  /** Stock symbol filter */
  symbol?: string;
  /** Broker name filter */
  broker?: string;
  /** Action type filter */
  action?: string;

  /** Which fields to show. Defaults to all fields. */
  fields?: Array<'dateFrom' | 'dateTo' | 'symbol' | 'broker' | 'action'>;

  /** Action type options (defaults to Buy/Sell/Snapshot) */
  actionOptions?: Array<{ value: string; label: string }>;

  // Callbacks
  onDateFromChange?: (value: string) => void;
  onDateToChange?: (value: string) => void;
  onSymbolChange?: (value: string) => void;
  onBrokerChange?: (value: string) => void;
  onActionChange?: (value: string) => void;
  onApply: () => void;
  onClear: () => void;

  /** Optional aria-label for the filter panel */
  ariaLabel?: string;
}

const DEFAULT_ACTION_OPTIONS = [
  { value: 'Buy', label: 'Buy' },
  { value: 'Sell', label: 'Sell' },
  { value: 'Snapshot', label: 'Snapshot' },
];

const ALL_FIELDS: FilterPanelProps['fields'] = ['dateFrom', 'dateTo', 'symbol', 'broker', 'action'];

export default function FilterPanel({
  dateFrom = '',
  dateTo = '',
  symbol = '',
  broker = '',
  action = '',
  fields = ALL_FIELDS,
  actionOptions = DEFAULT_ACTION_OPTIONS,
  onDateFromChange,
  onDateToChange,
  onSymbolChange,
  onBrokerChange,
  onActionChange,
  onApply,
  onClear,
  ariaLabel = 'Filters',
}: FilterPanelProps) {
  const visibleFields = new Set(fields);

  return (
    <div className="filter-panel" role="search" aria-label={ariaLabel}>
      <div className="filter-row">
        {visibleFields.has('dateFrom') && (
          <div className="filter-field">
            <label htmlFor="fp-date-from">From</label>
            <input
              id="fp-date-from"
              type="date"
              value={dateFrom}
              onChange={(e) => onDateFromChange?.(e.target.value)}
            />
          </div>
        )}
        {visibleFields.has('dateTo') && (
          <div className="filter-field">
            <label htmlFor="fp-date-to">To</label>
            <input
              id="fp-date-to"
              type="date"
              value={dateTo}
              onChange={(e) => onDateToChange?.(e.target.value)}
            />
          </div>
        )}
        {visibleFields.has('symbol') && (
          <div className="filter-field">
            <label htmlFor="fp-symbol">Symbol</label>
            <input
              id="fp-symbol"
              type="text"
              placeholder="e.g. DRAM"
              value={symbol}
              onChange={(e) => onSymbolChange?.(e.target.value)}
            />
          </div>
        )}
        {visibleFields.has('broker') && (
          <div className="filter-field">
            <label htmlFor="fp-broker">Broker</label>
            <input
              id="fp-broker"
              type="text"
              placeholder="e.g. Webull"
              value={broker}
              onChange={(e) => onBrokerChange?.(e.target.value)}
            />
          </div>
        )}
        {visibleFields.has('action') && (
          <div className="filter-field">
            <label htmlFor="fp-action">Action</label>
            <select
              id="fp-action"
              value={action}
              onChange={(e) => onActionChange?.(e.target.value)}
            >
              <option value="">All</option>
              {actionOptions.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>
        )}
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
