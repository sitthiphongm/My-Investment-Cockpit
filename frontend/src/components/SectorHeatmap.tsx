import { Treemap, ResponsiveContainer, Tooltip } from 'recharts';
import { formatTHB, formatPercent } from '../utils/format';

/**
 * SectorHeatmap - A treemap chart component for visualizing portfolio sectors.
 * Sized by allocation percentage, colored by ROI performance.
 */

export interface SectorHeatmapEntry {
  sector: string;
  allocation_percent: number;
  roi_percent: number;
  total_cost: number;
  total_market_value: number;
  position_count: number;
}

export interface SectorHeatmapProps {
  /** Sector data to display */
  data: SectorHeatmapEntry[];
  /** Chart height in pixels. Default 450. */
  height?: number;
  /** Optional className */
  className?: string;
}

interface TreemapNode {
  name: string;
  size: number;
  roi: number;
  cost: number;
  marketValue: number;
  positionCount: number;
  fill: string;
  [key: string]: string | number;
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

export default function SectorHeatmap({
  data,
  height = 450,
  className = '',
}: SectorHeatmapProps) {
  if (data.length === 0) {
    return (
      <div className={`sector-heatmap ${className}`} role="status">
        <p className="empty-table-message">No sector data available</p>
      </div>
    );
  }

  const treemapData: TreemapNode[] = data.map((entry) => ({
    name: entry.sector,
    size: entry.allocation_percent,
    roi: entry.roi_percent,
    cost: entry.total_cost,
    marketValue: entry.total_market_value,
    positionCount: entry.position_count,
    fill: getColor(entry.roi_percent),
  }));

  return (
    <div className={`sector-heatmap ${className}`} aria-label="Sector heatmap visualization">
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
      <div className="heatmap-chart" style={{ width: '100%', height }}>
        <ResponsiveContainer>
          <Treemap
            data={treemapData}
            dataKey="size"
            nameKey="name"
            stroke="#fff"
            content={<HeatmapCellContent />}
          >
            <Tooltip content={<HeatmapTooltip />} />
          </Treemap>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

/** Custom treemap cell content renderer */
function HeatmapCellContent(props: any) {
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
            {roi != null ? `${roi.toFixed(1)}%` : ''}
          </text>
        </>
      )}
    </g>
  );
}

/** Custom tooltip for heatmap hover */
function HeatmapTooltip({ active, payload }: any) {
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
