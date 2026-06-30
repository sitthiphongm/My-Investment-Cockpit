import { createBrowserRouter } from 'react-router-dom';
import { Layout, ProtectedRoute, AdminRoute } from './components';
import {
  LoginPage,
  DashboardPage,
  TradingPage,
  TransfersPage,
  PortfolioPage,
  PerformancePage,
  JournalPage,
  WatchlistPage,
  IdeasPage,
  AdminPage,
  TrendingPage,
  HeatmapPage,
  ScreenerPage,
  RebalancingPage,
  AlertsPage,
  DividendsPage,
  RealizedPLPage,
  AIInsightsPage,
  BehavioralPage,
  ImportExportPage,
  SimulatorPage,
  SettingsPage,
  StockDetailPage,
} from './pages';

export const router = createBrowserRouter([
  {
    path: '/login',
    element: <LoginPage />,
  },
  {
    // All authenticated routes are wrapped by ProtectedRoute
    element: <ProtectedRoute />,
    children: [
      {
        path: '/',
        element: <Layout />,
        children: [
          { index: true, element: <DashboardPage /> },
          { path: 'trading', element: <TradingPage /> },
          { path: 'transfers', element: <TransfersPage /> },
          { path: 'portfolio', element: <PortfolioPage /> },
          { path: 'performance', element: <PerformancePage /> },
          { path: 'journal', element: <JournalPage /> },
          { path: 'watchlist', element: <WatchlistPage /> },
          { path: 'ideas', element: <IdeasPage /> },
          {
            path: 'admin',
            element: (
              <AdminRoute>
                <AdminPage />
              </AdminRoute>
            ),
          },
          { path: 'trending', element: <TrendingPage /> },
          { path: 'heatmap', element: <HeatmapPage /> },
          { path: 'screener', element: <ScreenerPage /> },
          { path: 'rebalancing', element: <RebalancingPage /> },
          { path: 'alerts', element: <AlertsPage /> },
          { path: 'dividends', element: <DividendsPage /> },
          { path: 'realized-pl', element: <RealizedPLPage /> },
          { path: 'behavioral', element: <BehavioralPage /> },
          { path: 'ai-insights', element: <AIInsightsPage /> },
          { path: 'simulator', element: <SimulatorPage /> },
          { path: 'import-export', element: <ImportExportPage /> },
          { path: 'settings', element: <SettingsPage /> },
          { path: 'stock/:symbol', element: <StockDetailPage /> },
        ],
      },
    ],
  },
]);
