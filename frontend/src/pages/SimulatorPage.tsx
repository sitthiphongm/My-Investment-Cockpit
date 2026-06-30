import { useState } from 'react';
import { useRunSimulation } from '../hooks/useNewApis';
import toast from 'react-hot-toast';

export default function SimulatorPage() {
  const [priceChanges, setPriceChanges] = useState('');
  const [cashDeposit, setCashDeposit] = useState('');
  const simulationMutation = useRunSimulation();

  const handleRunSimulation = () => {
    const scenario: Record<string, unknown> = {};

    // Parse price changes (format: "AAPL=180,MSFT=420")
    if (priceChanges.trim()) {
      const changes: Record<string, number> = {};
      priceChanges.split(',').forEach((pair) => {
        const [symbol, price] = pair.split('=');
        if (symbol && price) {
          changes[symbol.trim().toUpperCase()] = Number(price.trim());
        }
      });
      if (Object.keys(changes).length > 0) {
        scenario.price_changes = changes;
      }
    }

    if (cashDeposit.trim()) {
      scenario.cash_deposit = Number(cashDeposit);
    }

    simulationMutation.mutate(scenario as Parameters<typeof simulationMutation.mutate>[0], {
      onError: () => toast.error('Simulation failed'),
    });
  };

  const result = simulationMutation.data;

  return (
    <div className="page">
      <h1>Scenario Simulator</h1>
      <p>Model portfolio changes before acting. Real data is never modified.</p>

      {/* Input Form */}
      <div style={{ marginTop: '24px', display: 'flex', flexDirection: 'column', gap: '16px', maxWidth: '500px' }}>
        <div>
          <label htmlFor="price-changes" style={{ display: 'block', marginBottom: '4px', fontSize: '13px', fontWeight: 600 }}>
            Price Changes (SYMBOL=PRICE, comma-separated)
          </label>
          <input
            id="price-changes"
            type="text"
            value={priceChanges}
            onChange={(e) => setPriceChanges(e.target.value)}
            placeholder="AAPL=180,MSFT=420"
            style={{ width: '100%', padding: '10px', borderRadius: '10px', border: '1px solid var(--border)', background: 'var(--bg)' }}
          />
        </div>

        <div>
          <label htmlFor="cash-deposit" style={{ display: 'block', marginBottom: '4px', fontSize: '13px', fontWeight: 600 }}>
            Cash Deposit (USD)
          </label>
          <input
            id="cash-deposit"
            type="number"
            value={cashDeposit}
            onChange={(e) => setCashDeposit(e.target.value)}
            placeholder="10000"
            style={{ width: '100%', padding: '10px', borderRadius: '10px', border: '1px solid var(--border)', background: 'var(--bg)' }}
          />
        </div>

        <button
          type="button"
          onClick={handleRunSimulation}
          disabled={simulationMutation.isPending}
          style={{ padding: '12px 24px', borderRadius: '10px', background: '#3B82F6', color: 'white', border: 'none', fontWeight: 600, cursor: 'pointer' }}
        >
          {simulationMutation.isPending ? 'Simulating...' : 'Run Simulation'}
        </button>
      </div>

      {/* Results */}
      {result && (
        <div style={{ marginTop: '32px' }}>
          <h2>Simulation Results</h2>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px', marginTop: '16px' }}>
            <ResultCard label="Current Value" value={`$${Number(result.current_market_value).toLocaleString()}`} />
            <ResultCard label="Simulated Value" value={`$${Number(result.simulated_market_value).toLocaleString()}`} />
            <ResultCard label="Impact on Value" value={`$${Number(result.impact_on_value).toLocaleString()}`} positive={Number(result.impact_on_value) >= 0} />
            <ResultCard label="Current P/L" value={`$${Number(result.current_pl).toLocaleString()}`} />
            <ResultCard label="Simulated P/L" value={`$${Number(result.simulated_pl).toLocaleString()}`} />
            <ResultCard label="Impact on P/L" value={`$${Number(result.impact_on_pl).toLocaleString()}`} positive={Number(result.impact_on_pl) >= 0} />
            <ResultCard label="Positions" value={`${result.current_position_count} → ${result.simulated_position_count}`} />
          </div>

          {result.warnings && result.warnings.length > 0 && (
            <div style={{ marginTop: '16px', padding: '12px', background: 'rgba(245,158,11,0.1)', borderRadius: '8px', border: '1px solid #F59E0B' }}>
              <strong>⚠️ Warnings:</strong>
              <ul style={{ margin: '8px 0 0 16px', padding: 0 }}>
                {result.warnings.map((w: string, i: number) => (
                  <li key={i} style={{ fontSize: '13px' }}>{w}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ResultCard({ label, value, positive }: { label: string; value: string; positive?: boolean }) {
  return (
    <div style={{ padding: '16px', borderRadius: '12px', border: '1px solid var(--border)', background: 'var(--bg)' }}>
      <div style={{ fontSize: '12px', textTransform: 'uppercase', fontWeight: 600, opacity: 0.6 }}>{label}</div>
      <div style={{ fontSize: '20px', fontWeight: 700, marginTop: '4px', color: positive !== undefined ? (positive ? '#22C55E' : '#EF4444') : 'inherit' }}>{value}</div>
    </div>
  );
}
