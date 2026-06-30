import { useBehavioralStats, useBehavioralPatterns } from '../hooks/useNewApis';

export default function BehavioralPage() {
  const { data: stats, isLoading: loadingStats } = useBehavioralStats();
  const { data: patterns, isLoading: loadingPatterns } = useBehavioralPatterns();

  if (loadingStats || loadingPatterns) {
    return (
      <div className="page">
        <h1>Behavioral Analytics</h1>
        <p>Loading...</p>
      </div>
    );
  }

  return (
    <div className="page">
      <h1>Behavioral Analytics</h1>
      <p>Understand your trading behavior and improve your process.</p>

      {/* Stats Cards */}
      {stats && (
        <div className="stats-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px', marginTop: '24px' }}>
          <StatCard label="Win Rate" value={`${stats.win_rate}%`} />
          <StatCard label="Total Closed Trades" value={String(stats.total_closed_trades)} />
          <StatCard label="Avg Winner" value={`$${Number(stats.avg_winner).toLocaleString()}`} positive />
          <StatCard label="Avg Loser" value={`$${Number(stats.avg_loser).toLocaleString()}`} negative />
          <StatCard label="Payoff Ratio" value={`${stats.payoff_ratio}x`} />
          <StatCard label="Avg Holding" value={`${stats.avg_holding_days} days`} />
          <StatCard label="Best Trade" value={`$${Number(stats.best_trade_pl).toLocaleString()}`} positive />
          <StatCard label="Worst Trade" value={`$${Number(stats.worst_trade_pl).toLocaleString()}`} negative />
          <StatCard label="Total Realized P/L" value={`$${Number(stats.total_realized_pl).toLocaleString()}`} positive={Number(stats.total_realized_pl) >= 0} negative={Number(stats.total_realized_pl) < 0} />
        </div>
      )}

      {/* Patterns */}
      {patterns && patterns.length > 0 && (
        <div style={{ marginTop: '32px' }}>
          <h2>Identified Patterns</h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginTop: '16px' }}>
            {patterns.map((p: { pattern_id: string; label: string; description: string; severity: string }) => (
              <div
                key={p.pattern_id}
                style={{
                  padding: '16px',
                  borderRadius: '12px',
                  border: `1px solid ${p.severity === 'concern' ? '#EF4444' : p.severity === 'warning' ? '#F59E0B' : '#1E293B'}`,
                  background: p.severity === 'concern' ? 'rgba(239,68,68,0.05)' : p.severity === 'warning' ? 'rgba(245,158,11,0.05)' : 'transparent',
                }}
              >
                <div style={{ fontWeight: 600, marginBottom: '4px' }}>
                  {p.severity === 'concern' ? '🔴' : p.severity === 'warning' ? '⚠️' : 'ℹ️'} {p.label}
                </div>
                <div style={{ fontSize: '14px', opacity: 0.8 }}>{p.description}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function StatCard({ label, value, positive, negative }: { label: string; value: string; positive?: boolean; negative?: boolean }) {
  return (
    <div style={{ padding: '16px', borderRadius: '12px', border: '1px solid var(--border)', background: 'var(--bg)' }}>
      <div style={{ fontSize: '12px', textTransform: 'uppercase', fontWeight: 600, opacity: 0.6 }}>{label}</div>
      <div style={{ fontSize: '24px', fontWeight: 700, color: positive ? '#22C55E' : negative ? '#EF4444' : 'inherit', marginTop: '4px' }}>{value}</div>
    </div>
  );
}
