import { useCallback, useEffect, useState } from 'react';
import { dashboardApi } from '../api';
import type { DashboardData, BrokerCapital } from '../types';
import { formatTHB, formatPercent, toNum } from '../utils/format';

/** Format currency or return "N/A" when null/undefined */
function formatCurrencyOrNA(value: number | null | undefined): string {
  if (value == null) return 'N/A';
  return formatTHB(value);
}

/** Format percent or return "N/A" */
function formatPercentOrNA(value: number | null | undefined): string {
  if (value == null) return 'N/A';
  return formatPercent(value);
}

/** CSS class for profit/loss coloring */
function plClass(value: number | null | undefined): string {
  if (value == null) return '';
  const n = toNum(value);
  if (n > 0) return 'positive';
  if (n < 0) return 'negative';
  return '';
}

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchDashboard = useCallback(async () => {
    try {
      const result = await dashboardApi.get();
      setData(result);
    } catch {
      // Error handled by axios interceptor
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDashboard();
  }, [fetchDashboard]);

  if (loading) {
    return (
      <div className="page dashboard-page">
        <h1>Dashboard</h1>
        <p className="loading-text" aria-live="polite">Loading dashboard data...</p>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="page dashboard-page">
        <h1>Dashboard</h1>
        <p>Failed to load dashboard data. Please try again.</p>
      </div>
    );
  }

  return (
    <div className="page dashboard-page">
      <h1>Dashboard</h1>
      <p>Overview of your investment portfolio.</p>

      {!data.market_data_complete && data.total_positions > 0 && (
        <MarketDataWarning />
      )}

      <div className="dashboard-grid">
        <SummaryCards data={data} />
        <PortfolioCounts data={data} />
      </div>

      <BrokerBreakdown brokers={data.capital_per_broker ?? []} />
    </div>
  );
}

function MarketDataWarning() {
  return (
    <div className="dashboard-warning" role="alert">
      <span className="dashboard-warning-icon">⚠️</span>
      <span>
        Market data is incomplete for one or more positions. Total Market Value and
        Overall P/L may not be available until market data is fetched.
      </span>
    </div>
  );
}

function SummaryCards({ data }: { data: DashboardData }) {
  return (
    <div className="dashboard-cards" role="region" aria-label="Investment summary">
      <div className="dashboard-card">
        <div className="dashboard-card-label">Total Invested</div>
        <div className="dashboard-card-value">{formatTHB(data.total_invested)}</div>
      </div>
      <div className="dashboard-card">
        <div className="dashboard-card-label">Total Withdrawn</div>
        <div className="dashboard-card-value">{formatTHB(data.total_withdrawn)}</div>
      </div>
      <div className="dashboard-card">
        <div className="dashboard-card-label">Net Invested</div>
        <div className={`dashboard-card-value ${plClass(data.net_invested)}`}>
          {formatTHB(data.net_invested)}
        </div>
      </div>
      <div className="dashboard-card">
        <div className="dashboard-card-label">Total Market Value</div>
        <div className="dashboard-card-value">
          {formatCurrencyOrNA(data.total_market_value)}
        </div>
      </div>
      <div className="dashboard-card">
        <div className="dashboard-card-label">Overall P/L</div>
        <div className={`dashboard-card-value ${plClass(data.overall_pl)}`}>
          {formatCurrencyOrNA(data.overall_pl)}
        </div>
      </div>
      <div className="dashboard-card">
        <div className="dashboard-card-label">Overall ROI</div>
        <div className={`dashboard-card-value ${plClass(data.overall_roi_percent)}`}>
          {formatPercentOrNA(data.overall_roi_percent)}
        </div>
      </div>
    </div>
  );
}

function PortfolioCounts({ data }: { data: DashboardData }) {
  return (
    <div className="dashboard-counts" role="region" aria-label="Portfolio counts">
      <div className="dashboard-count-item">
        <div className="dashboard-count-value">{data.total_positions}</div>
        <div className="dashboard-count-label">Held Positions</div>
      </div>
      <div className="dashboard-count-item">
        <div className="dashboard-count-value">{data.total_brokers}</div>
        <div className="dashboard-count-label">Brokers</div>
      </div>
    </div>
  );
}

function BrokerBreakdown({ brokers }: { brokers: BrokerCapital[] }) {
  if (brokers.length === 0) {
    return (
      <div className="dashboard-broker-section">
        <h2>Capital per Broker</h2>
        <div className="empty-state" role="status" aria-label="No broker data">
          <div className="empty-state-icon">🏦</div>
          <h2>No Broker Data</h2>
          <p>No money transfers have been recorded yet. Add transfers to see capital breakdown by broker.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="dashboard-broker-section">
      <h2>Capital per Broker</h2>
      <div className="dashboard-broker-table-container">
        <table className="dashboard-broker-table" aria-label="Capital per broker breakdown">
          <thead>
            <tr>
              <th scope="col">Broker</th>
              <th scope="col">Capital In</th>
              <th scope="col">Capital Out</th>
              <th scope="col">Net Capital</th>
            </tr>
          </thead>
          <tbody>
            {brokers.map((broker) => (
              <tr key={broker.broker}>
                <td className="broker-name">{broker.broker}</td>
                <td className="broker-amount">{formatTHB(broker.total_in)}</td>
                <td className="broker-amount">{formatTHB(broker.total_out)}</td>
                <td className={`broker-amount ${plClass(broker.net_capital)}`}>
                  {formatTHB(broker.net_capital)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
