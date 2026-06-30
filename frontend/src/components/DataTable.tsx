import { useState, useMemo, useCallback } from 'react';

/**
 * DataTable - A reusable sortable, filterable table component.
 * Supports column-based sorting (ascending/descending) and optional text filtering.
 */

export interface Column<T> {
  /** Unique key for the column */
  key: string;
  /** Display header text */
  header: string;
  /** Function to render cell content */
  render: (row: T) => React.ReactNode;
  /** Function to get raw sortable value from row (for sorting) */
  sortValue?: (row: T) => string | number | null;
  /** Optional CSS class for the column */
  className?: string;
  /** Whether this column is sortable. Default true. */
  sortable?: boolean;
}

export interface DataTableProps<T> {
  /** Column definitions */
  columns: Column<T>[];
  /** Data rows */
  data: T[];
  /** Function to extract a unique key from each row */
  rowKey: (row: T) => string;
  /** Optional aria-label for the table */
  ariaLabel?: string;
  /** Optional className for the table wrapper */
  className?: string;
  /** Show empty state message when no data */
  emptyMessage?: string;
  /** Optional: initial sort column key */
  defaultSortKey?: string;
  /** Optional: initial sort direction */
  defaultSortDirection?: 'asc' | 'desc';
}

type SortDirection = 'asc' | 'desc' | null;

export default function DataTable<T>({
  columns,
  data,
  rowKey,
  ariaLabel = 'Data table',
  className = '',
  emptyMessage = 'No data available',
  defaultSortKey,
  defaultSortDirection = 'asc',
}: DataTableProps<T>) {
  const [sortKey, setSortKey] = useState<string | null>(defaultSortKey ?? null);
  const [sortDirection, setSortDirection] = useState<SortDirection>(
    defaultSortKey ? defaultSortDirection : null
  );

  const handleSort = useCallback(
    (columnKey: string) => {
      if (sortKey === columnKey) {
        // Cycle: asc -> desc -> none
        if (sortDirection === 'asc') {
          setSortDirection('desc');
        } else if (sortDirection === 'desc') {
          setSortKey(null);
          setSortDirection(null);
        }
      } else {
        setSortKey(columnKey);
        setSortDirection('asc');
      }
    },
    [sortKey, sortDirection]
  );

  const sortedData = useMemo(() => {
    if (!sortKey || !sortDirection) return data;

    const column = columns.find((c) => c.key === sortKey);
    if (!column?.sortValue) return data;

    const getValue = column.sortValue;

    return [...data].sort((a, b) => {
      const aVal = getValue(a);
      const bVal = getValue(b);

      if (aVal == null && bVal == null) return 0;
      if (aVal == null) return 1;
      if (bVal == null) return -1;

      let comparison: number;
      if (typeof aVal === 'number' && typeof bVal === 'number') {
        comparison = aVal - bVal;
      } else {
        comparison = String(aVal).localeCompare(String(bVal));
      }

      return sortDirection === 'desc' ? -comparison : comparison;
    });
  }, [data, sortKey, sortDirection, columns]);

  const getSortIndicator = (columnKey: string): string => {
    if (sortKey !== columnKey) return '';
    if (sortDirection === 'asc') return ' ▲';
    if (sortDirection === 'desc') return ' ▼';
    return '';
  };

  if (data.length === 0) {
    return (
      <div className={`table-container ${className}`}>
        <p className="empty-table-message" role="status">
          {emptyMessage}
        </p>
      </div>
    );
  }

  return (
    <div className={`table-container ${className}`}>
      <table className="data-table" aria-label={ariaLabel}>
        <thead>
          <tr>
            {columns.map((col) => {
              const isSortable = col.sortable !== false && col.sortValue != null;
              return (
                <th
                  key={col.key}
                  scope="col"
                  className={[col.className, isSortable ? 'sortable-header' : '']
                    .filter(Boolean)
                    .join(' ')}
                  onClick={isSortable ? () => handleSort(col.key) : undefined}
                  onKeyDown={
                    isSortable
                      ? (e) => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault();
                            handleSort(col.key);
                          }
                        }
                      : undefined
                  }
                  tabIndex={isSortable ? 0 : undefined}
                  role={isSortable ? 'columnheader' : undefined}
                  aria-sort={
                    sortKey === col.key
                      ? sortDirection === 'asc'
                        ? 'ascending'
                        : 'descending'
                      : undefined
                  }
                  style={isSortable ? { cursor: 'pointer', userSelect: 'none' } : undefined}
                >
                  {col.header}
                  {isSortable && (
                    <span className="sort-indicator" aria-hidden="true">
                      {getSortIndicator(col.key)}
                    </span>
                  )}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {sortedData.map((row) => (
            <tr key={rowKey(row)}>
              {columns.map((col) => (
                <td key={col.key} className={col.className}>
                  {col.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
