/**
 * Safely convert any value (string, number, null, undefined) to a number.
 * Returns 0 for null, undefined, NaN, or non-numeric strings.
 * Useful when the backend returns Decimal values as strings (e.g. "12.50").
 */
export function toNum(value: any): number {
  if (value == null) return 0;
  const n = Number(value);
  return isNaN(n) ? 0 : n;
}

/**
 * Format a number as USD currency (default for all pages).
 * Example: formatUSD(1234567.89) => "$1,234,567.89"
 */
export function formatUSD(amount: number | string | null | undefined): string {
  if (amount == null) return '$0.00';
  const num = typeof amount === 'string' ? parseFloat(amount) : amount;
  if (isNaN(num)) return '$0.00';
  return `$${num.toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

/**
 * Format a number as Thai Baht currency (used for Money Transfers page only).
 * Example: formatBaht(1234567.89) => "฿1,234,567.89"
 */
export function formatBaht(amount: number | string | null | undefined): string {
  if (amount == null) return '฿0.00';
  const num = typeof amount === 'string' ? parseFloat(amount) : amount;
  if (isNaN(num)) return '฿0.00';
  return `฿${num.toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

/**
 * Default currency formatter — shows USD ($).
 * All pages use this via the `formatTHB` name for backward compatibility.
 */
export const formatTHB = formatUSD;

/**
 * Default currency formatter — USD for all pages except Transfers.
 * Alias for formatUSD.
 */
export const formatCurrency = formatUSD;

/**
 * Format a number as a percentage with 2 decimal places.
 * Example: formatPercent(12.5) => "12.50%"
 * Example: formatPercent(-3.21) => "-3.21%"
 */
export function formatPercent(value: number | string | null | undefined): string {
  if (value == null) return '0.00%';
  const num = typeof value === 'string' ? parseFloat(value) : value;
  if (isNaN(num)) return '0.00%';
  return `${num.toFixed(2)}%`;
}

/**
 * Format a date string (YYYY-MM-DD or ISO) into a readable format.
 * Example: formatDate("2024-03-15") => "15 Mar 2024"
 */
export function formatDate(date: string | null | undefined): string {
  if (!date) return '-';
  const d = new Date(date);
  if (isNaN(d.getTime())) return '-';
  return d.toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
}

/**
 * Format a datetime string (ISO) into a readable date + time format.
 * Example: formatDateTime("2024-03-15T14:30:00Z") => "15 Mar 2024, 14:30"
 */
export function formatDateTime(datetime: string | null | undefined): string {
  if (!datetime) return '-';
  const d = new Date(datetime);
  if (isNaN(d.getTime())) return '-';
  const datePart = d.toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
  const timePart = d.toLocaleTimeString('en-GB', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  });
  return `${datePart}, ${timePart}`;
}
