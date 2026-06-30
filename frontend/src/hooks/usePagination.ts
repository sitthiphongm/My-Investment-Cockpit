import { useState, useMemo, useCallback } from 'react';

export interface UsePaginationOptions {
  /** Default items per page. Defaults to 10. */
  defaultPerPage?: number;
}

export interface UsePaginationResult<T> {
  /** Current page (1-indexed) */
  currentPage: number;
  /** Items per page */
  itemsPerPage: number;
  /** Total number of items */
  totalItems: number;
  /** Sliced items for the current page */
  paginatedItems: T[];
  /** Total pages */
  totalPages: number;
  /** Navigate to a specific page */
  setPage: (page: number) => void;
  /** Change items per page (resets to page 1) */
  setPerPage: (perPage: number) => void;
}

/**
 * Reusable pagination hook. Takes sorted/filtered data and returns
 * paginated slice + controls.
 */
export function usePagination<T>(
  data: T[],
  options: UsePaginationOptions = {}
): UsePaginationResult<T> {
  const { defaultPerPage = 10 } = options;
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage, setItemsPerPage] = useState(defaultPerPage);

  const totalItems = data.length;
  const totalPages = Math.max(1, Math.ceil(totalItems / itemsPerPage));

  // Clamp current page if data shrinks
  const safePage = Math.min(currentPage, totalPages);

  const paginatedItems = useMemo(() => {
    const start = (safePage - 1) * itemsPerPage;
    return data.slice(start, start + itemsPerPage);
  }, [data, safePage, itemsPerPage]);

  const setPage = useCallback((page: number) => {
    setCurrentPage(Math.max(1, page));
  }, []);

  const setPerPage = useCallback((perPage: number) => {
    setItemsPerPage(perPage);
    setCurrentPage(1);
  }, []);

  return {
    currentPage: safePage,
    itemsPerPage,
    totalItems,
    paginatedItems,
    totalPages,
    setPage,
    setPerPage,
  };
}
