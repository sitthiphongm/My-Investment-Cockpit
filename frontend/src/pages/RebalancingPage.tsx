import { useCallback, useEffect, useState } from 'react';
import { portfolioApi } from '../api';
import type { RebalancingData, TargetAllocation } from '../types';
import { formatPercent, toNum } from '../utils/format';
import toast from 'react-hot-toast';

export default function RebalancingPage() {
  const [data, setData] = useState<RebalancingData | null>(null);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [targets, setTargets] = useState<TargetAllocation[]>([]);
  const [saving, setSaving] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const result = await portfolioApi.getRebalancing();
      setData(result);
      // Initialize targets from current data
      if ((result.positions ?? []).length > 0) {
        setTargets(
          result.positions.map((p) => ({
            target_key: p.target_key,
            target_type: p.target_type,
            target_percentage: p.target_allocation,
          }))
        );
      }
    } catch {
      // Error handled by interceptor
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleTargetChange = (index: number, value: string) => {
    setTargets((prev) => {
      const updated = [...prev];
      updated[index] = { ...updated[index], target_percentage: Number(value) || 0 };
      return updated;
    });
  };

  const addTarget = () => {
    setTargets((prev) => [
      ...prev,
      { target_key: '', target_type: 'Symbol', target_percentage: 0 },
    ]);
  };

  const removeTarget = (index: number) => {
    setTargets((prev) => prev.filter((_, i) => i !== index));
  };

  const handleTargetKeyChange = (index: number, value: string) => {
    setTargets((prev) => {
      const updated = [...prev];
      updated[index] = { ...updated[index], target_key: value };
      return updated;
    });
  };

  const handleTargetTypeChange = (index: number, value: 'Symbol' | 'Sector') => {
    setTargets((prev) => {
      const updated = [...prev];
      updated[index] = { ...updated[index], target_type: value };
      return updated;
    });
  };

  const saveTargets = async () => {
    const total = targets.reduce((sum, t) => sum + t.target_percentage, 0);
    if (Math.abs(total - 100) > 0.01) {
      toast.error(`Target allocations must sum to 100%. Current sum: ${total.toFixed(2)}%`, { duration: 4000 });
      return;
    }
    setSaving(true);
    try {
      await portfolioApi.setTargetAllocations(targets);
      toast.success('Target allocations updated', { duration: 4000 });
      setShowForm(false);
      fetchData();
    } catch {
      // Error handled by interceptor
    } finally {
      setSaving(false);
    }
  };

  const totalTarget = targets.reduce((sum, t) => sum + t.target_percentage, 0);

  if (loading) {
    return (
      <div className="page rebalancing-page">
        <h1>Portfolio Rebalancing</h1>
        <p className="loading-text" aria-live="polite">Loading rebalancing data...</p>
      </div>
    );
  }

  return (
    <div className="page rebalancing-page">
      <h1>Portfolio Rebalancing</h1>
      <p>Compare current allocation against your targets and see suggested actions.</p>

      <div className="trading-actions">
        <button className="btn btn-primary" onClick={() => setShowForm(!showForm)}>
          {showForm ? 'Hide Targets Form' : '⚙️ Set Targets'}
        </button>
      </div>

      {/* Set Targets Form */}
      {showForm && (
        <div className="targets-form">
          <h3>Set Target Allocations</h3>
          <p className="form-hint">
            Total: <strong className={Math.abs(totalTarget - 100) > 0.01 ? 'text-negative' : 'text-positive'}>
              {totalTarget.toFixed(2)}%
            </strong>{' '}
            (must equal 100%)
          </p>
          {targets.map((target, index) => (
            <div key={index} className="target-row">
              <select
                value={target.target_type}
                onChange={(e) => handleTargetTypeChange(index, e.target.value as 'Symbol' | 'Sector')}
                aria-label="Target type"
              >
                <option value="Symbol">Symbol</option>
                <option value="Sector">Sector</option>
              </select>
              <input
                type="text"
                placeholder={target.target_type === 'Symbol' ? 'e.g. AAPL' : 'e.g. Technology'}
                value={target.target_key}
                onChange={(e) => handleTargetKeyChange(index, e.target.value)}
                aria-label="Target key"
              />
              <input
                type="number"
                step="0.1"
                min="0"
                max="100"
                value={target.target_percentage}
                onChange={(e) => handleTargetChange(index, e.target.value)}
                aria-label="Target percentage"
              />
              <span>%</span>
              <button
                className="btn btn-icon btn-danger btn-sm"
                onClick={() => removeTarget(index)}
                aria-label="Remove target"
              >
                ✕
              </button>
            </div>
          ))}
          <div className="form-actions">
            <button className="btn btn-secondary btn-sm" onClick={addTarget}>
              + Add Target
            </button>
            <button className="btn btn-primary" onClick={saveTargets} disabled={saving}>
              {saving ? 'Saving...' : 'Save Targets'}
            </button>
          </div>
        </div>
      )}

      {/* Current vs Target Table */}
      {data && (data.positions ?? []).length > 0 ? (
        <>
          <div className="table-container">
            <table className="data-table" aria-label="Rebalancing allocation comparison">
              <thead>
                <tr>
                  <th scope="col">Name</th>
                  <th scope="col">Type</th>
                  <th scope="col" className="number-col">Target %</th>
                  <th scope="col" className="number-col">Current %</th>
                  <th scope="col" className="number-col">Deviation</th>
                  <th scope="col">Status</th>
                  <th scope="col">Action</th>
                </tr>
              </thead>
              <tbody>
                {(data.positions ?? []).map((pos) => {
                  const status = pos.is_overweight ? 'Over' : pos.is_underweight ? 'Under' : 'On Target';
                  return (
                    <tr
                      key={pos.target_key}
                      className={
                        status === 'Over'
                          ? 'row-over'
                          : status === 'Under'
                          ? 'row-under'
                          : ''
                      }
                    >
                      <td className="symbol-cell">{pos.target_key}</td>
                      <td>{pos.target_type}</td>
                      <td className="number-cell">{formatPercent(pos.target_allocation)}</td>
                      <td className="number-cell">{formatPercent(pos.current_allocation)}</td>
                      <td className="number-cell">
                        <span
                          className={
                            toNum(pos.difference) > 0
                              ? 'text-positive'
                              : toNum(pos.difference) < 0
                              ? 'text-negative'
                              : ''
                          }
                        >
                          {toNum(pos.difference) > 0 ? '+' : ''}
                          {formatPercent(pos.difference)}
                        </span>
                      </td>
                      <td>
                        {status === 'Over' && (
                          <span className="badge badge-over">⬆️ Over-weight</span>
                        )}
                        {status === 'Under' && (
                          <span className="badge badge-under">⬇️ Under-weight</span>
                        )}
                        {status === 'On Target' && (
                          <span className="badge badge-on-target">✅ On Target</span>
                        )}
                      </td>
                      <td>{pos.suggested_action ?? '-'}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      ) : (
        <div className="empty-state" role="status">
          <div className="empty-state-icon">⚖️</div>
          <h2>No Rebalancing Data</h2>
          <p>Set your target allocations to see how your current portfolio compares.</p>
        </div>
      )}
    </div>
  );
}
