import { useCallback, useEffect, useMemo, useState } from 'react';
import { realizedPlApi } from '../api';
import type { RealizedPL, RealizedPLSummary } from '../types';
import { formatTHB, formatDate, toNum } from '../utils/format';
import { useSortableData } from '../hooks/useSortableData';
import { usePagination } from '../hooks/usePagination';
import Pagination from '../components/Pagination';

type PeriodFilter = '' | 'monthly' | 'yearly';

/** Compute date_from/date_to for the period filter. */
function getDateRange(period: PeriodFilter): { date_from?: string; date_to?: string } {
  if (!period) return {};
  const now = new Date();
  const year = now.getFullYear();
  const month = now.getMonth(); // 0-indexed

  if (period === 'monthly') {
    const from = new Date(year, month, 1);
    const to = new Date(year, month + 1, 0); // last day of current month
    return {
      date_from: from.toISOString().slice(0, 10),
      date_to: to.toISOString().slice(0, 10),
    };
  }
  // yearly
  return {
    date_from: `${year}-01-01`,
    date_to: `${year}-12-31`,
  };
}

export default function RealizedPLPage() {
  const [records, setRecords] = useState<RealizedPL[]>([]);
  const [summary, setSummary] = useState<RealizedPLSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [period, setPeriod] = useState<PeriodFilter>('');

  const fetchData = useCallback(async () => {
    try {
      const dateRange = getDateRange(period);
      const [recordsData, summaryData] = await Promise.all([
        realizedPlApi.list(Object.keys(dateRange).length > 0 ? dateRange : undefined),
        realizedPlApi.getSummary('monthly'),
      ]);
      setRecords(recordsData ?? []);
      setSummary(summaryData);
    } catch {
      // Error handled by interceptor
    } finally {
      setLoading(false);
    }
  }, [period]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Derive yearly and monthly maps from summary entries
  const { yearlyEntries, monthlyEntries } = useMemo(() => {
    if (!summary) return { yearlyEntries: [], monthlyEntries: [] };

    const monthlyEntries = summary.entries.filter((e) => e.period.includes('-'));
    // Aggregate yearly from monthly entries
    const yearlyMap = new Map<string, number>();
    for (const entry of monthlyEntries) {
      const year = entry.period.split('-')[0];
      yearlyMap.set(year, (yearlyMap.get(year) ?? 0) + entry.total_realized_pl);
    }
    const yearlyEntries = Array.from(yearlyMap.entries())
      .map(([year, total]) => ({ period: year, total_realized_pl: total }))
      .sort((a, b) => b.period.localeCompare(a.period));

    return { yearlyEntries, monthlyEntries };
  }, [summary]);

  if (loading) {
    return (
      <div className="page realized-pl-page">
        <h1>Realized P/L</h1>
        <p className="loading-text" aria-live="polite">Loading realized P/L data...</p>
      </div>
    );
  }

  return (
    <div className="page realized-pl-page">
      <h1>Realized P/L</h1>
      <p>View profits and losses from completed (sold) positions.</p>

      {/* Summary Cards */}
      {summary && (
        <div className="summary-cards">
          <div className="summary-card">
            <span className="summary-label">All-Time Realized P/L</span>
            <span
              className={`summary-value ${
                toNum(summary.all_time_total) >= 0 ? 'text-positive' : 'text-negative'
              }`}
            >
              {formatTHB(summary.all_time_total)}
            </span>
          </div>
        </div>
      )}

      {/* Period Filter */}
      <div className="filter-row">
        <label htmlFor="rpl-period">Period Filter:</label>
        <select
          id="rpl-period"
          value={period}
          onChange={(e) => setPeriod(e.target.value as PeriodFilter)}
        >
          <option value="">All Time</option>
          <option value="monthly">This Month</option>
          <option value="yearly">This Year</option>
        </select>
      </div>

      {/* Cumulative Totals */}
      {summary && (
        <div className="cumulative-section">
          <h3>Cumulative Totals</h3>
          <div className="cumulative-grid">
            {yearlyEntries.length > 0 && (
              <div className="cumulative-block">
                <h4>By Year</h4>
                <div className="table-container">
                  <table className="data-table data-table-sm" aria-label="Yearly realized P/L">
                    <thead>
                      <tr>
                        <th scope="col">Year</th>
                        <th scope="col" className="number-col">P/L</th>
                      </tr>
                    </thead>
                    <tbody>
                      {yearlyEntries.map((entry) => (
                        <tr key={entry.period}>
                          <td>{entry.period}</td>
                          <td className="number-cell">
                            <span className={toNum(entry.total_realized_pl) >= 0 ? 'text-positive' : 'text-negative'}>
                              {formatTHB(entry.total_realized_pl)}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
            {monthlyEntries.length > 0 && (
              <div className="cumulative-block">
                <h4>By Month</h4>
                <div className="table-container">
                  <table className="data-table data-table-sm" aria-label="Monthly realized P/L">
                    <thead>
                      <tr>
                        <th scope="col">Month</th>
                        <th scope="col" className="number-col">P/L</th>
                      </tr>
                    </thead>
                    <tbody>
                      {monthlyEntries.map((entry) => (
                        <tr key={entry.period}>
                          <td>{entry.period}</td>
                          <td className="number-cell">
                            <span className={toNum(entry.total_realized_pl) >= 0 ? 'text-positive' : 'text-negative'}>
                              {formatTHB(entry.total_realized_pl)}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Records Table */}
      <h3>Transaction Records</h3>
      {records.length === 0 ? (
        <div className="empty-state" role="status">
          <div className="empty-state-icon">📈</div>
          <h2>No Realized P/L Records</h2>
          <p>Sell transactions will automatically generate realized P/L records.</p>
        </div>
      ) : (
        <RealizedPLTable records={records} />
      )}
    </div>
  );
}

// ===== Realized P/L Table Component =====

function RealizedPLTable({ records }: { records: RealizedPL[] }) {
  const { sortedItems, requestSort, getSortIndicator } = useSortableData(records);
  const { paginatedItems, currentPage, totalItems, itemsPerPage, setPage, setPerPage } = usePagination(sortedItems);

  return (
    <div className="table-container">
      <table className="data-table" aria-label="Realized P/L records">
        <thead>
          <tr>
            <th scope="col" className="sortable-th" onClick={() => requestSort('date')}>Date{getSortIndicator('date')}</th>
            <th scope="col" className="sortable-th" onClick={() => requestSort('stock_symbol')}>Symbol{getSortIndicator('stock_symbol')}</th>
            <th scope="col" className="sortable-th number-col" onClick={() => requestSort('sell_quantity')}>Qty Sold{getSortIndicator('sell_quantity')}</th>
            <th scope="col" className="sortable-th number-col" onClick={() => requestSort('sell_price')}>Sell Price{getSortIndicator('sell_price')}</th>
            <th scope="col" className="sortable-th number-col" onClick={() => requestSort('avg_cost_at_sale')}>Avg Cost{getSortIndicator('avg_cost_at_sale')}</th>
            <th scope="col" className="sortable-th number-col" onClick={() => requestSort('realized_pl')}>Realized P/L{getSortIndicator('realized_pl')}</th>
            <th scope="col" className="sortable-th number-col" onClick={() => requestSort('hold_duration_days')}>Hold Days{getSortIndicator('hold_duration_days')}</th>
            <th scope="col">Term</th>
          </tr>
        </thead>
        <tbody>
          {paginatedItems.map((record) => (
            <tr key={record.id}>
              <td>{formatDate(record.date)}</td>
              <td className="symbol-cell">{record.stock_symbol}</td>
              <td className="number-cell">{toNum(record.sell_quantity).toLocaleString()}</td>
              <td className="number-cell">{formatTHB(record.sell_price)}</td>
              <td className="number-cell">{formatTHB(record.avg_cost_at_sale)}</td>
              <td className="number-cell">
                <span
                  className={toNum(record.realized_pl) >= 0 ? 'text-positive' : 'text-negative'}
                >
                  {formatTHB(record.realized_pl)}
                </span>
              </td>
              <td className="number-cell">{record.hold_duration_days}</td>
              <td>
                <span
                  className={`badge ${
                    record.term_type === 'Long-term'
                      ? 'badge-long-term'
                      : 'badge-short-term'
                  }`}
                >
                  {record.term_type}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <Pagination
        currentPage={currentPage}
        totalItems={totalItems}
        itemsPerPage={itemsPerPage}
        onPageChange={setPage}
        onItemsPerPageChange={setPerPage}
      />
    </div>
  );
}
