/**
 * Dark Trading Dashboard — Design Tokens
 * Matches the spec design document for consistent theming across components.
 */

export const theme = {
  dark: {
    background: '#020617',
    surface: '#0F172A',
    surfaceElevated: '#111827',
    border: '#1E293B',
    textPrimary: '#F8FAFC',
    textSecondary: '#94A3B8',
    primary: '#3B82F6',
    positive: '#22C55E',
    negative: '#EF4444',
    warning: '#F59E0B',
    info: '#38BDF8',
  },
  light: {
    background: '#F6F8FB',
    surface: '#FFFFFF',
    surfaceElevated: '#FFFFFF',
    border: '#E2E8F0',
    textPrimary: '#0F172A',
    textSecondary: '#64748B',
    primary: '#0052FF',
    positive: '#16A34A',
    negative: '#DC2626',
    warning: '#F59E0B',
    info: '#2563EB',
  },
} as const;

export const typography = {
  fontFamily: "'Inter', 'Geist', system-ui, -apple-system, sans-serif",
  pageTitle: { size: '28px', weight: 700 },
  sectionTitle: { size: '18px', weight: 600 },
  metricValue: { size: '24px', weight: 700 },
  tableText: { size: '13px', weight: 400 },
  label: { size: '12px', weight: 600, transform: 'uppercase' as const },
} as const;

export const radius = {
  card: '16px',
  button: '10px',
  input: '10px',
  badge: '999px',
} as const;

export type ThemeMode = 'dark' | 'light';
