import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { formatTHB } from '../utils/format';

/**
 * PerformanceChart - A line chart component for displaying portfolio value over time.
 * Uses recharts LineChart with responsive container.
 */

export interface PerformanceDataPoint {
  /** Date string (YYYY-MM-DD or similar) */
  date: string;
  /** Portfolio value at this date */
  value: number;
}

export interface PerformanceChartProps {
  /** Array of data points to plot */
  data: PerformanceDataPoint[];
  /** Chart height in pixels. Default 300. */
  height?: number;
  /** Title shown above the chart. Default "Portfolio Value Over Time" */
  title?: string;
  /** Line color. Default "#4f46e5" */
  lineColor?: string;
  /** Optional className */
  className?: string;
}

export default function PerformanceChart({
  data,
  height = 300,
  title = 'Portfolio Value Over Time',
  lineColor = '#4f46e5',
  className = '',
}: PerformanceChartProps) {
  if (data.length === 0) {
    return (
      <div className={`performance-chart-container ${className}`} role="status">
        <h3>{title}</h3>
        <p className="empty-table-message">No data available for chart</p>
      </div>
    );
  }

  return (
    <div
      className={`performance-chart-container ${className}`}
      aria-label={title}
    >
      <h3>{title}</h3>
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={data} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="date" tick={{ fontSize: 12 }} />
          <YAxis
            tick={{ fontSize: 12 }}
            tickFormatter={(value: number) => `฿${(value / 1000).toFixed(0)}k`}
          />
          <Tooltip
            formatter={(value) => [formatTHB(value as number), 'Portfolio Value']}
            labelFormatter={(label) => `Date: ${label}`}
          />
          <Line
            type="monotone"
            dataKey="value"
            stroke={lineColor}
            strokeWidth={2}
            dot={{ r: 3 }}
            activeDot={{ r: 5 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
