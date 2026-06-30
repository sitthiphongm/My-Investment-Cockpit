/**
 * Global application state using Zustand.
 * Manages theme mode and common app-level state.
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { ThemeMode } from '../utils/theme';

interface AppState {
  /** Current theme mode (dark is default per spec) */
  themeMode: ThemeMode;
  /** Toggle between dark and light mode */
  toggleTheme: () => void;
  /** Set theme explicitly */
  setTheme: (mode: ThemeMode) => void;
  /** Whether sidebar is collapsed */
  sidebarCollapsed: boolean;
  /** Toggle sidebar collapse */
  toggleSidebar: () => void;
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      themeMode: 'dark',
      toggleTheme: () =>
        set((state) => ({
          themeMode: state.themeMode === 'dark' ? 'light' : 'dark',
        })),
      setTheme: (mode) => set({ themeMode: mode }),
      sidebarCollapsed: false,
      toggleSidebar: () =>
        set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
    }),
    {
      name: 'investment-cockpit-app',
    }
  )
);
