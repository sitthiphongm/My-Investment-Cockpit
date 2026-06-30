import type { ReactNode } from 'react';

/**
 * MetricCard - Dashboard metric display component.
 * Shows a value with label and optional change indicator.
 * Uses dark surface background with proper border radius (16px).
 */

export interface MetricCardProps {
  /** Metric label (e.g., "Total Portfolio Value") */
  label: string;
  /** Formatted value to display prominently */
  value: string;
  /** Optional change indicator text (e.g., "+5.2%") */
  change?: string;
  /** Change direction for coloring: positive (green), negative (red), or neutral */
  changeDirection?: 'positive' | 'negative' | 'neutral';
  /** Optional icon or emoji displayed above label */
  icon?: ReactNode;
  /** Optional className for additional styling */
  className?: string;
}

export default function MetricCard({
  label,
  value,
  change,
  changeDirection = 'neutral',
  icon,
  className = '',
}: MetricCardProps) {
  const changeClass =
    changeDirection === 'positive'
      ? 'metric-card__change--positive'
      : changeDirection === 'negative'
        ? 'metric-card__change--negative'
        : 'metric-card__change--neutral';

  return (
    <div className={`metric-card ${className}`}>
      {icon && <div className="metric-card__icon">{icon}</div>}
      <div className="metric-card__label">{label}</div>
      <div className="metric-card__value">{value}</div>
      {change && (
        <div className={`metric-card__change ${changeClass}`}>
          {changeDirection === 'positive' && '▲ '}
          {changeDirection === 'negative' && '▼ '}
          {change}
        </div>
      )}
    </div>
  );
}
