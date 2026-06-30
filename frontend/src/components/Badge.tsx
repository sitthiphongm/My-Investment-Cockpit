/**
 * Badge - Reusable status/category badge component.
 * Supports various variants: winner, loser, warning, info, neutral, etc.
 * Uses 999px border-radius (pill shape) per design spec.
 * Colors: positive #22C55E, negative #EF4444, warning #F59E0B, info #38BDF8.
 */

export type BadgeVariant =
  | 'positive'
  | 'negative'
  | 'warning'
  | 'info'
  | 'neutral'
  | 'primary'
  | 'purple';

export interface BadgeProps {
  /** Badge text content */
  children: React.ReactNode;
  /** Visual variant determining color scheme */
  variant?: BadgeVariant;
  /** Optional className for additional styling */
  className?: string;
  /** Optional size */
  size?: 'sm' | 'md';
}

const VARIANT_CLASSES: Record<BadgeVariant, string> = {
  positive: 'badge--positive',
  negative: 'badge--negative',
  warning: 'badge--warning',
  info: 'badge--info',
  neutral: 'badge--neutral',
  primary: 'badge--primary',
  purple: 'badge--purple',
};

export default function Badge({
  children,
  variant = 'neutral',
  className = '',
  size = 'sm',
}: BadgeProps) {
  const classes = [
    'badge',
    VARIANT_CLASSES[variant],
    size === 'md' ? 'badge--md' : '',
    className,
  ]
    .filter(Boolean)
    .join(' ');

  return <span className={classes}>{children}</span>;
}

/**
 * Pre-configured badge variants for common investment scenarios.
 */
export function WinnerBadge() {
  return <Badge variant="positive">Winner</Badge>;
}

export function LoserBadge() {
  return <Badge variant="negative">Loser</Badge>;
}

export function WarningBadge({ children = 'Warning' }: { children?: React.ReactNode }) {
  return <Badge variant="warning">{children}</Badge>;
}

export function HighBetaBadge() {
  return <Badge variant="warning">High Beta</Badge>;
}

export function DataWarningBadge() {
  return <Badge variant="warning">Data Warning</Badge>;
}

export function OverweightBadge() {
  return <Badge variant="info">Overweight</Badge>;
}

export function UnderweightBadge() {
  return <Badge variant="neutral">Underweight</Badge>;
}

export function DividendBadge() {
  return <Badge variant="primary">Dividend</Badge>;
}

export function SpeculativeBadge() {
  return <Badge variant="purple">Speculative</Badge>;
}
