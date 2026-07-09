import { useEffect, useState } from 'react';
import { apiClient } from '../api';
import { screenerApi } from '../api';
import type { ScreenerPreset } from '../types';
import { formatPercent, toNum } from '../utils/format';
import { useSortableData } from '../hooks/useSortableData';
import { usePagination } from '../hooks/usePagination';
import Pagination from '../components/Pagination';
import toast from 'react-hot-toast';

// ===== Types =====

interface SystemPreset {
  id: string;
  name: string;
  description: string;
  filters: Record<string, any>;
  signals?: string[];
}

interface FilterMeta {
  key: string;
  label: string;
  type: string;
  min?: number;
  max?: number;
  step?: number;
  group?: string;
  options?: string[];
}

interface ActiveFilter {
  key: string;
  meta: FilterMeta;
  value: any;
}

interface ScreenResult {
  symbol: string;
  company_name: string | null;
  sector: string | null;
  industry: string | null;
  market_cap: number | null;
  price: number | null;
  pe_trailing: number | null;
  dividend_yield: number | null;
  beta: number | null;
  price_to_book: number | null;
  data_source: string;
}

interface ScreenResponse {
  results: ScreenResult[];
  total_matches: number;
  providers_used: string[];
  provider_status: Record<string, string>;
}

// ===== Main Component =====

export default function ScreenerPage() {
  const [systemPresets, setSystemPresets] = useState<SystemPreset[]>([]);
  const [userPresets, setUserPresets] = useState<ScreenerPreset[]>([]);
  const [availableFilters, setAvailableFilters] = useState<FilterMeta[]>([]);
  const [activeFilters, setActiveFilters] = useState<Record<string, any>>({});
  const [activePresetId, setActivePresetId] = useState<string | null>(null);
  const [results, setResults] = useState<ScreenResult[]>([]);
  const [providerStatus, setProviderStatus] = useState<Record<string, string>>({});
  const [providersUsed, setProvidersUsed] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [showSaveModal, setShowSaveModal] = useState(false);
  const [showFilterDropdown, setShowFilterDropdown] = useState(false);

  // Fetch metadata on mount
  useEffect(() => {
    const fetchMeta = async () => {
      try {
        const [presets, filters, uPresets] = await Promise.all([
          apiClient.get('/api/screener/presets/system').then(r => r.data),
          apiClient.get('/api/screener/filters/available').then(r => r.data),
          screenerApi.listPresets(),
        ]);
        setSystemPresets(presets ?? []);
        setAvailableFilters(filters ?? []);
        setUserPresets(uPresets ?? []);
      } catch { /* ignore */ }
    };
    fetchMeta();
  }, []);

  // Search handler
  const handleSearch = async () => {
    setLoading(true);
    try {
      const body: any = { filters: activeFilters };
      if (activePresetId) body.preset = activePresetId;
      const res = await apiClient.post('/api/screener/advanced', body);
      const data: ScreenResponse = res.data;
      setResults(data.results ?? []);
      setProviderStatus(data.provider_status ?? {});
      setProvidersUsed(data.providers_used ?? []);
    } catch {
      toast.error('Screener search failed', { duration: 4000 });
    } finally {
      setLoading(false);
    }
  };

  // Preset selection
  const selectPreset = (preset: SystemPreset) => {
    setActivePresetId(preset.id);
    setActiveFilters({ ...preset.filters });
  };

  const clearAll = () => {
    setActivePresetId(null);
    setActiveFilters({});
    setResults([]);
  };

  // Add a filter from dropdown
  const addFilter = (meta: FilterMeta) => {
    if (!(meta.key in activeFilters)) {
      const initialValue = meta.type === 'select' ? null : meta.type === 'text' ? '' : meta.min ?? '';
      setActiveFilters(prev => ({ ...prev, [meta.key]: initialValue }));
    }
    setShowFilterDropdown(false);
  };

  // Remove a filter
  const removeFilter = (key: string) => {
    setActiveFilters(prev => {
      const next = { ...prev };
      delete next[key];
      return next;
    });
  };

  // Update filter value
  const updateFilter = (key: string, value: any) => {
    const normalizedValue = value === ''
      ? null
      : typeof value === 'string' && isNaN(Number(value))
        ? value
        : Number(value);
    setActiveFilters(prev => ({ ...prev, [key]: normalizedValue }));
  };

  // Save preset
  const savePreset = async (name: string) => {
    try {
      await screenerApi.savePreset({ name, filter_criteria: activeFilters as any });
      toast.success('Preset saved', { duration: 4000 });
      setShowSaveModal(false);
      const uPresets = await screenerApi.listPresets();
      setUserPresets(uPresets ?? []);
    } catch { toast.error('Failed to save preset'); }
  };

  const { sortedItems, requestSort, getSortIndicator } = useSortableData(results);
  const { paginatedItems, currentPage, totalItems, itemsPerPage, setPage, setPerPage } = usePagination(sortedItems);

  // Get active filter keys for display
  // Keep keys that have been added, even if their value is not set yet.
  const activeFilterKeys = Object.keys(activeFilters);
  const unusedFilters = availableFilters.filter(f => !(f.key in activeFilters));

  return (
    <div className="page screener-page">
      <h1>Advanced Stock Screener</h1>
      <p>Multi-provider intelligent stock screening with strategy presets.</p>

      {/* Provider Status Bar */}
      <ProviderStatusBar status={providerStatus} used={providersUsed} />

      {/* System Presets */}
      <div className="preset-chips-bar">
        <span className="preset-label">Strategies:</span>
        {systemPresets.map(p => (
          <button
            key={p.id}
            className={`preset-chip ${activePresetId === p.id ? 'active' : ''}`}
            onClick={() => selectPreset(p)}
            title={p.description}
          >
            {p.name}
          </button>
        ))}
        {userPresets.length > 0 && (
          <>
            <span className="preset-divider">|</span>
            {userPresets.map(p => (
              <span key={p.id} className="preset-chip-wrapper">
                <button
                  className={`preset-chip preset-user`}
                  onClick={() => { setActivePresetId(null); setActiveFilters(p.filter_criteria as any); }}
                  title={`User preset: ${p.name}`}
                >
                  {p.name}
                </button>
                <button
                  className="preset-delete-btn"
                  onClick={async (e) => { e.stopPropagation(); await screenerApi.deletePreset(p.id); setUserPresets(prev => prev.filter(x => x.id !== p.id)); toast.success('Preset deleted'); }}
                  title="Delete preset"
                >✕</button>
              </span>
            ))}
          </>
        )}
      </div>

      {/* Active Filters */}
      <div className="dynamic-filter-panel">
        {activeFilterKeys.map(key => {
          const meta = availableFilters.find(f => f.key === key);
          if (!meta) return null;
          return (
            <FilterRow
              key={key}
              meta={meta}
              value={activeFilters[key]}
              onChange={(v) => updateFilter(key, v)}
              onRemove={() => removeFilter(key)}
            />
          );
        })}

        {/* Add Filter Button */}
        <div className="add-filter-row">
          <button className="btn btn-secondary btn-sm" onClick={() => setShowFilterDropdown(!showFilterDropdown)}>
            + Add Filter
          </button>
          {showFilterDropdown && (
            <div className="filter-dropdown">
              {unusedFilters.map(f => (
                <button key={f.key} className="filter-dropdown-item" onClick={() => addFilter(f)}>
                  <span className="filter-dropdown-group">{f.group}</span>
                  {f.label}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Actions */}
      <div className="screener-actions">
        <button className="btn btn-primary" onClick={handleSearch} disabled={loading}>
          {loading ? 'Screening...' : '🔍 Screen Stocks'}
        </button>
        <button className="btn btn-secondary" onClick={clearAll}>Reset</button>
        <button className="btn btn-secondary" onClick={() => setShowSaveModal(true)}>💾 Save Preset</button>
      </div>

      {/* Results */}
      {results.length > 0 && (
        <>
          <h3>Results ({results.length})</h3>
          <ResultsTable
            items={paginatedItems}
            requestSort={requestSort}
            getSortIndicator={getSortIndicator}
          />
          <Pagination
            currentPage={currentPage}
            totalItems={totalItems}
            itemsPerPage={itemsPerPage}
            onPageChange={setPage}
            onItemsPerPageChange={setPerPage}
          />
        </>
      )}

      {results.length === 0 && !loading && (
        <div className="empty-state">
          <div className="empty-state-icon">🔍</div>
          <h2>Select a Strategy or Add Filters</h2>
          <p>Choose a preset strategy above or add custom filters to find stocks.</p>
        </div>
      )}

      {/* Save Modal */}
      {showSaveModal && <SavePresetModal onSave={savePreset} onClose={() => setShowSaveModal(false)} />}
    </div>
  );
}


// ===== Provider Status Bar =====

function ProviderStatusBar({ status, used }: { status: Record<string, string>; used: string[] }) {
  if (Object.keys(status).length === 0) return null;
  const providers = ['fmp', 'eodhd', 'alpha_vantage', 'twelve_data', 'yfinance'];
  return (
    <div className="provider-status-bar">
      {providers.map(p => {
        const s = status[p];
        const isUsed = used.includes(p);
        const color = s === 'success' ? 'provider-ok' : s === 'empty' ? 'provider-warn' : s ? 'provider-err' : 'provider-idle';
        return (
          <span key={p} className={`provider-badge ${color}`} title={s || 'Not queried'}>
            {p.replace('_', ' ').toUpperCase().slice(0, 5)}
            {isUsed && ' ✓'}
          </span>
        );
      })}
    </div>
  );
}

// ===== Filter Row with Slider =====

function FilterRow({ meta, value, onChange, onRemove }: { meta: FilterMeta; value: any; onChange: (v: any) => void; onRemove: () => void }) {
  if (meta.type === 'select') {
    return (
      <div className="filter-row-item">
        <label>{meta.label}</label>
        <select value={value || ''} onChange={(e) => onChange(e.target.value || null)}>
          <option value="">Any</option>
          {meta.options?.map(o => <option key={o} value={o}>{o}</option>)}
        </select>
        <button className="btn btn-icon btn-sm" onClick={onRemove} title="Remove">✕</button>
      </div>
    );
  }

  const numVal = value != null ? Number(value) : '';
  const sliderMin = meta.min ?? 0;
  const sliderMax = meta.max ?? 100;
  const step = meta.step ?? 1;

  return (
    <div className="filter-row-item">
      <div className="filter-row-header">
        <label>{meta.label}</label>
        <button className="btn btn-icon btn-sm" onClick={onRemove} title="Remove filter">✕</button>
      </div>
      <div className="filter-row-controls">
        <input
          type="range"
          min={sliderMin}
          max={sliderMax}
          step={step}
          value={numVal || sliderMin}
          onChange={(e) => onChange(e.target.value)}
          className="filter-slider"
        />
        <input
          type="number"
          min={sliderMin}
          max={sliderMax}
          step={step}
          value={numVal}
          onChange={(e) => onChange(e.target.value)}
          className="filter-number-input"
          placeholder={meta.label}
        />
      </div>
    </div>
  );
}

// ===== Results Table =====

function ResultsTable({ items, requestSort, getSortIndicator }: { items: ScreenResult[]; requestSort: (k: string) => void; getSortIndicator: (k: string) => string }) {
  return (
    <div className="table-container">
      <table className="data-table screener-results-table" aria-label="Advanced screener results">
        <colgroup>
          <col style={{ width: '7%' }} />
          <col style={{ width: '14%' }} />
          <col style={{ width: '10%' }} />
          <col style={{ width: '10%' }} />
          <col style={{ width: '10%' }} />
          <col style={{ width: '7%' }} />
          <col style={{ width: '7%' }} />
          <col style={{ width: '7%' }} />
          <col style={{ width: '7%' }} />
          <col style={{ width: '7%' }} />
          <col style={{ width: '9%' }} />
          <col style={{ width: '5%' }} />
        </colgroup>
        <thead>
          <tr>
            <th scope="col" className="sortable-th" onClick={() => requestSort('symbol')}>Symbol{getSortIndicator('symbol')}</th>
            <th scope="col">Company</th>
            <th scope="col">Sector</th>
            <th scope="col" className="sortable-th number-col" onClick={() => requestSort('price')}>Price (1D %){getSortIndicator('price')}</th>
            <th scope="col" className="sortable-th number-col" onClick={() => requestSort('market_cap')}>Market Cap{getSortIndicator('market_cap')}</th>
            <th scope="col" className="sortable-th number-col" onClick={() => requestSort('pe_trailing')}>P/E{getSortIndicator('pe_trailing')}</th>
            <th scope="col" className="sortable-th number-col" onClick={() => requestSort('price_to_book')}>P/B{getSortIndicator('price_to_book')}</th>
            <th scope="col" className="sortable-th number-col" onClick={() => requestSort('peg_ratio')}>PEG{getSortIndicator('peg_ratio')}</th>
            <th scope="col" className="sortable-th number-col" onClick={() => requestSort('dividend_yield')}>Div Yield{getSortIndicator('dividend_yield')}</th>
            <th scope="col" className="sortable-th number-col" onClick={() => requestSort('roe')}>ROE{getSortIndicator('roe')}</th>
            <th scope="col" className="sortable-th number-col" onClick={() => requestSort('volume')}>Volume{getSortIndicator('volume')}</th>
            <th scope="col">Src</th>
          </tr>
        </thead>
        <tbody>
          {items.map((r) => {
            const mktCap = toNum(r.market_cap);
            const divYield = toNum(r.dividend_yield);
            return (
              <tr key={r.symbol}>
                <td className="symbol-cell">
                  <a href={`https://stockanalysis.com/stocks/${r.symbol.toLowerCase()}/`} target="_blank" rel="noopener noreferrer">{r.symbol}</a>
                </td>
                <td className="company-cell">{r.company_name || '-'}</td>
                <td>{r.sector ? <span className="sector-tag">{r.sector}</span> : '-'}</td>
                <td className="number-cell">{r.price != null ? `$${toNum(r.price).toFixed(2)}` : 'N/A'}</td>
                <td className="number-cell">{mktCap > 0 ? fmtMktCap(mktCap) : 'N/A'}</td>
                <td className="number-cell">{r.pe_trailing != null ? toNum(r.pe_trailing).toFixed(1) : 'N/A'}</td>
                <td className="number-cell">{r.price_to_book != null ? toNum(r.price_to_book).toFixed(2) : 'N/A'}</td>
                <td className="number-cell">{(r as any).peg_ratio != null ? toNum((r as any).peg_ratio).toFixed(2) : 'N/A'}</td>
                <td className="number-cell">{divYield > 0 ? <span className="text-positive">{formatPercent(divYield)}</span> : 'N/A'}</td>
                <td className="number-cell">{(r as any).roe != null ? <span className={toNum((r as any).roe) >= 15 ? 'text-positive' : ''}>{toNum((r as any).roe).toFixed(1)}%</span> : 'N/A'}</td>
                <td className="number-cell">{(r as any).volume ? fmtVol(toNum((r as any).volume)) : 'N/A'}</td>
                <td><span className={`provider-badge provider-${r.data_source}`}>{r.data_source?.slice(0, 3)}</span></td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function fmtMktCap(v: number): string {
  if (v >= 1e12) return `$${(v / 1e12).toFixed(2)}T`;
  if (v >= 1e9) return `$${(v / 1e9).toFixed(2)}B`;
  if (v >= 1e6) return `$${(v / 1e6).toFixed(0)}M`;
  return `$${v.toLocaleString()}`;
}

function fmtVol(v: number): string {
  if (v >= 1e9) return `${(v / 1e9).toFixed(1)}B`;
  if (v >= 1e6) return `${(v / 1e6).toFixed(1)}M`;
  if (v >= 1e3) return `${(v / 1e3).toFixed(0)}K`;
  return v.toLocaleString();
}

// ===== Save Preset Modal =====

function SavePresetModal({ onSave, onClose }: { onSave: (name: string) => void; onClose: () => void }) {
  const [name, setName] = useState('');
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content modal-sm" onClick={e => e.stopPropagation()}>
        <div className="modal-header"><h2>Save Preset</h2><button className="btn btn-icon" onClick={onClose}>✕</button></div>
        <div className="form-field">
          <label htmlFor="preset-name">Preset Name</label>
          <input id="preset-name" type="text" value={name} onChange={e => setName(e.target.value)} placeholder="My Strategy" maxLength={100} />
        </div>
        <div className="form-actions">
          <button className="btn btn-secondary" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" onClick={() => onSave(name)} disabled={!name.trim()}>Save</button>
        </div>
      </div>
    </div>
  );
}
