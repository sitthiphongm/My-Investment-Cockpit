import { useCallback, useEffect, useState } from 'react';
import { Treemap, ResponsiveContainer, Tooltip } from 'recharts';
import { portfolioApi } from '../api';
import type { SectorHeatmapEntry } from '../types';
import { formatTHB, formatPercent, toNum } from '../utils/format';
import { useSortableData } from '../hooks/useSortableData';
import { usePagination } from '../hooks/usePagination';
import Pagination from '../components/Pagination';

interface TreemapNode {
  name: string;
  size: number;
  roi: number;
  cost: number;
  marketValue: number;
  positionCount: number;
  fill: string;
  [key: string]: unknown;
}

function getColor(roi: number): string {
  if (roi >= 20) return '#16a34a';
  if (roi >= 10) return '#22c55e';
  if (roi >= 5) return '#4ade80';
  if (roi >= 0) return '#86efac';
  if (roi >= -5) return '#fca5a5';
  if (roi >= -10) return '#f87171';
  if (roi >= -20) return '#ef4444';
  return '#dc2626';
}

export default function HeatmapPage() {
  const [data, setData] = useState<SectorHeatmapEntry[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    try {
      const result = await portfolioApi.getSectorHeatmap();
      setData(result ?? []);
    } catch {
      // Error handled by interceptor
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  if (loading) {
    return (
      <div className="page heatmap-page">
        <h1>Sector Heatmap</h1>
        <p className="loading-text" aria-live="polite">Loading heatmap data...</p>
      </div>
    );
  }

  if (data.length === 0) {
    return (
      <div className="page heatmap-page">
        <h1>Sector Heatmap</h1>
        <div className="empty-state" role="status">
          <div className="empty-state-icon">🗺️</div>
          <h2>No Sector Data</h2>
          <p>Add positions with market data to see the sector heatmap visualization.</p>
        </div>
      </div>
    );
  }

  const treemapData: TreemapNode[] = data.map((entry) => ({
    name: entry.sector,
    size: toNum(entry.allocation_percent),
    roi: toNum(entry.roi_percent),
    cost: toNum(entry.total_cost),
    marketValue: toNum(entry.total_market_value),
    positionCount: toNum(entry.position_count),
    fill: getColor(toNum(entry.roi_percent)),
  }));

  return (
    <div className="page heatmap-page">
      <h1>Sector Heatmap</h1>
      <p>Visual breakdown of your portfolio by sector. Sized by allocation, colored by ROI.</p>

      {/* Color Legend */}
      <div className="heatmap-legend">
        <span className="legend-item">
          <span className="legend-swatch" style={{ backgroundColor: '#dc2626' }} /> {'< -20%'}
        </span>
        <span className="legend-item">
          <span className="legend-swatch" style={{ backgroundColor: '#f87171' }} /> -10% to -20%
        </span>
        <span className="legend-item">
          <span className="legend-swatch" style={{ backgroundColor: '#fca5a5' }} /> -5% to -10%
        </span>
        <span className="legend-item">
          <span className="legend-swatch" style={{ backgroundColor: '#86efac' }} /> 0% to 5%
        </span>
        <span className="legend-item">
          <span className="legend-swatch" style={{ backgroundColor: '#4ade80' }} /> 5% to 10%
        </span>
        <span className="legend-item">
          <span className="legend-swatch" style={{ backgroundColor: '#22c55e' }} /> 10% to 20%
        </span>
        <span className="legend-item">
          <span className="legend-swatch" style={{ backgroundColor: '#16a34a' }} /> {'> 20%'}
        </span>
      </div>

      {/* Treemap Chart */}
      <div className="heatmap-chart" style={{ width: '100%', height: 450 }}>
        <ResponsiveContainer>
          <Treemap
            data={treemapData}
            dataKey="size"
            nameKey="name"
            stroke="#fff"
            content={<CustomTreemapContent />}
          >
            <Tooltip content={<CustomTooltip />} />
          </Treemap>
        </ResponsiveContainer>
      </div>

      {/* Summary Table */}
      <h3>Sector Details</h3>
      <SectorDetailsTable data={data} />
    </div>
  );
}

// ===== Sector Details Table Component =====

function SectorDetailsTable({ data }: { data: SectorHeatmapEntry[] }) {
  const { sortedItems, requestSort, getSortIndicator } = useSortableData(data);
  const { paginatedItems, currentPage, totalItems, itemsPerPage, setPage, setPerPage } = usePagination(sortedItems);

  return (
    <div className="table-container">
      <table className="data-table" aria-label="Sector heatmap details">
        <thead>
          <tr>
            <th scope="col" className="sortable-th" onClick={() => requestSort('sector')}>Sector{getSortIndicator('sector')}</th>
            <th scope="col" className="sortable-th number-col" onClick={() => requestSort('allocation_percent')}>Allocation{getSortIndicator('allocation_percent')}</th>
            <th scope="col" className="sortable-th number-col" onClick={() => requestSort('total_cost')}>Total Cost{getSortIndicator('total_cost')}</th>
            <th scope="col" className="sortable-th number-col" onClick={() => requestSort('total_market_value')}>Market Value{getSortIndicator('total_market_value')}</th>
            <th scope="col" className="sortable-th number-col" onClick={() => requestSort('roi_percent')}>ROI{getSortIndicator('roi_percent')}</th>
            <th scope="col" className="number-col">Positions</th>
          </tr>
        </thead>
        <tbody>
          {paginatedItems.map((entry) => (
            <tr key={entry.sector}>
              <td>{entry.sector}</td>
              <td className="number-cell">{formatPercent(entry.allocation_percent)}</td>
              <td className="number-cell">{formatTHB(entry.total_cost)}</td>
              <td className="number-cell">{formatTHB(entry.total_market_value)}</td>
              <td className="number-cell">
                <span className={toNum(entry.roi_percent) >= 0 ? 'text-positive' : 'text-negative'}>
                  {formatPercent(entry.roi_percent)}
                </span>
              </td>
              <td className="number-cell">{entry.position_count}</td>
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

// Custom Treemap cell content
function CustomTreemapContent(props: any) {
  const { x, y, width, height, name, fill, roi } = props;
  if (width < 40 || height < 30) return null;
  return (
    <g>
      <rect x={x} y={y} width={width} height={height} fill={fill} stroke="#fff" strokeWidth={2} />
      {width > 60 && height > 40 && (
        <>
          <text
            x={x + width / 2}
            y={y + height / 2 - 8}
            textAnchor="middle"
            fill="#fff"
            fontSize={12}
            fontWeight="bold"
          >
            {name}
          </text>
          <text
            x={x + width / 2}
            y={y + height / 2 + 10}
            textAnchor="middle"
            fill="#fff"
            fontSize={11}
          >
            {roi != null ? `${toNum(roi).toFixed(1)}%` : ''}
          </text>
        </>
      )}
    </g>
  );
}

// Custom tooltip for hover
function CustomTooltip({ active, payload }: any) {
  if (!active || !payload || !payload.length) return null;
  const item = payload[0].payload;
  return (
    <div className="heatmap-tooltip">
      <strong>{item.name}</strong>
      <div>Allocation: {formatPercent(item.size)}</div>
      <div>ROI: {formatPercent(item.roi)}</div>
      <div>Cost: {formatTHB(item.cost)}</div>
      <div>Market Value: {formatTHB(item.marketValue)}</div>
      <div>Positions: {item.positionCount}</div>
    </div>
  );
}
