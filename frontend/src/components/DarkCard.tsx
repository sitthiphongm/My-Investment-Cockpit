import type { ReactNode } from 'react';

/**
 * DarkCard - Elevated card component using dark theme surface tokens.
 * Uses --color-card-bg (#0F172A) background with --color-border (#1E293B) border.
 * Applies 16px border-radius per design spec.
 */

export interface DarkCardProps {
  /** Card content */
  children: ReactNode;
  /** Optional className for additional styling */
  className?: string;
  /** Optional title displayed at the top of the card */
  title?: string;
  /** Whether to add hover elevation effect */
  hoverable?: boolean;
  /** Optional padding override (default uses standard card padding) */
  noPadding?: boolean;
}

export default function DarkCard({
  children,
  className = '',
  title,
  hoverable = false,
  noPadding = false,
}: DarkCardProps) {
  const classes = [
    'dark-card',
    hoverable ? 'dark-card--hoverable' : '',
    noPadding ? 'dark-card--no-padding' : '',
    className,
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <div className={classes}>
      {title && <h3 className="dark-card__title">{title}</h3>}
      {children}
    </div>
  );
}
