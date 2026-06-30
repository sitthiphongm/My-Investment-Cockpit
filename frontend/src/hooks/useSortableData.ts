import { useMemo, useState } from 'react';
import { toNum } from '../utils/format';

type SortDirection = 'asc' | 'desc' | null;

interface SortConfig {
  key: string;
  direction: SortDirection;
}

export function useSortableData<T>(items: T[]) {
  const [sortConfig, setSortConfig] = useState<SortConfig>({ key: '', direction: null });

  const sortedItems = useMemo(() => {
    if (!sortConfig.key || !sortConfig.direction) return items;

    return [...items].sort((a: any, b: any) => {
      let aVal = a[sortConfig.key];
      let bVal = b[sortConfig.key];

      // Handle null/undefined
      if (aVal == null && bVal == null) return 0;
      if (aVal == null) return 1;
      if (bVal == null) return -1;

      // Try numeric comparison
      const aNum = toNum(aVal);
      const bNum = toNum(bVal);
      const isNumeric = (typeof aVal === 'number' || !isNaN(Number(aVal))) &&
                        (typeof bVal === 'number' || !isNaN(Number(bVal)));

      let comparison: number;
      if (isNumeric) {
        comparison = aNum - bNum;
      } else {
        comparison = String(aVal).localeCompare(String(bVal));
      }

      return sortConfig.direction === 'desc' ? -comparison : comparison;
    });
  }, [items, sortConfig]);

  const requestSort = (key: string) => {
    setSortConfig((prev) => {
      if (prev.key === key) {
        if (prev.direction === 'asc') return { key, direction: 'desc' };
        if (prev.direction === 'desc') return { key: '', direction: null };
      }
      return { key, direction: 'asc' };
    });
  };

  const getSortIndicator = (key: string): string => {
    if (sortConfig.key !== key) return '';
    return sortConfig.direction === 'asc' ? ' ▲' : ' ▼';
  };

  return { sortedItems, requestSort, getSortIndicator, sortConfig };
}
