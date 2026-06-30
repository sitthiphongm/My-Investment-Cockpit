import { useEffect, useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { authApi } from '../api';
import type { User } from '../types';
import {
  LayoutDashboard,
  LineChart,
  Wallet,
  ClipboardList,
  TrendingUp,
  BookOpen,
  Star,
  Lightbulb,
  Shield,
  BarChart3,
  Grid3x3,
  Search,
  Bell,
  Scale,
  DollarSign,
  FileText,
  Brain,
  Bot,
  FlaskConical,
  Download,
  Settings,
  Sun,
  Moon,
  PanelLeftClose,
  PanelLeftOpen,
  LogOut,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  adminOnly?: boolean;
}

const mainNavItems: NavItem[] = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/trading', label: 'Trading Log', icon: ClipboardList },
  { to: '/transfers', label: 'Money Transfers', icon: Wallet },
  { to: '/portfolio', label: 'Portfolio Summary', icon: BarChart3 },
  { to: '/heatmap', label: 'Sector Heatmap', icon: Grid3x3 },
  { to: '/performance', label: 'Performance History', icon: LineChart },
  { to: '/journal', label: 'Trade Journal', icon: BookOpen },
  { to: '/watchlist', label: 'Watchlist', icon: Star },
  { to: '/ideas', label: 'Investment Ideas', icon: Lightbulb },
  { to: '/admin', label: 'Admin', icon: Shield, adminOnly: true },
];

const marketsItems: NavItem[] = [
  { to: '/trending', label: 'Trending Stocks', icon: TrendingUp },
  { to: '/screener', label: 'Stock Screener', icon: Search },
];

const toolsItems: NavItem[] = [
  { to: '/alerts', label: 'Alert Center', icon: Bell },
  { to: '/rebalancing', label: 'Rebalancing', icon: Scale },
  { to: '/dividends', label: 'Dividend Tracker', icon: DollarSign },
  { to: '/realized-pl', label: 'Realized P/L', icon: FileText },
  { to: '/behavioral', label: 'Behavioral Analytics', icon: Brain },
  { to: '/ai-insights', label: 'AI Insights', icon: Bot },
  { to: '/simulator', label: 'Scenario Simulator', icon: FlaskConical },
  { to: '/import-export', label: 'Import / Export', icon: Download },
  { to: '/settings', label: 'Settings', icon: Settings },
];

function getStoredTheme(): 'dark' | 'light' {
  if (typeof window === 'undefined') return 'dark';
  return (localStorage.getItem('theme') as 'dark' | 'light') || 'dark';
}

function getStoredCollapsed(): boolean {
  if (typeof window === 'undefined') return false;
  return localStorage.getItem('sidebar-collapsed') === 'true';
}

export default function NavigationMenu() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [collapsed, setCollapsed] = useState(getStoredCollapsed);
  const [theme, setTheme] = useState<'dark' | 'light'>(getStoredTheme);
  const navigate = useNavigate();

  useEffect(() => {
    authApi
      .getMe()
      .then((userData) => setUser(userData))
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
  }, []);

  // Apply theme on mount and change
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
  }, [theme]);

  const handleToggleTheme = () => {
    setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'));
  };

  const handleToggleCollapse = () => {
    setCollapsed((prev) => {
      const next = !prev;
      localStorage.setItem('sidebar-collapsed', String(next));
      return next;
    });
  };

  const handleLogout = async () => {
    try {
      await authApi.logout();
    } finally {
      navigate('/login');
    }
  };

  const visibleMainItems = mainNavItems.filter(
    (item) => !item.adminOnly || user?.is_admin
  );

  return (
    <nav
      className={`navigation-menu${collapsed ? ' collapsed' : ''}`}
      aria-label="Main navigation"
    >
      {/* User Profile Header */}
      <div className="nav-logo">
        {user ? (
          <div className="nav-profile-header">
            {user.profile_picture_url ? (
              <img src={user.profile_picture_url} alt="" className="nav-header-avatar" />
            ) : (
              <div className="nav-header-avatar-placeholder">
                {user.display_name.charAt(0).toUpperCase()}
              </div>
            )}
            {!collapsed && <span className="nav-profile-name">{user.display_name}</span>}
            <button
              className="nav-collapse-btn"
              type="button"
              onClick={handleToggleCollapse}
              aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
              title={collapsed ? 'Expand' : 'Collapse'}
            >
              {collapsed ? <PanelLeftOpen size={14} /> : <PanelLeftClose size={14} />}
            </button>
          </div>
        ) : (
          <span className="nav-logo-text">{collapsed ? 'MI' : 'My Investment'}</span>
        )}
      </div>

      <div className="nav-section-divider" />

      {/* Theme toggle */}
      <div className="theme-toggle">
        <button
          className="theme-toggle-btn"
          onClick={handleToggleTheme}
          type="button"
          aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
          title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
        >
          {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
          {!collapsed && (
            <span className="theme-toggle-label">
              {theme === 'dark' ? 'Light Mode' : 'Dark Mode'}
            </span>
          )}
        </button>
      </div>

      {/* Main nav */}
      <ul className="nav-links">
        {visibleMainItems.map((item) => {
          const IconComponent = item.icon;
          return (
            <li key={item.to}>
              <NavLink
                to={item.to}
                end={item.to === '/'}
                className={({ isActive }) =>
                  isActive ? 'nav-link active' : 'nav-link'
                }
                title={collapsed ? item.label : undefined}
              >
                <span className="nav-icon">
                  <IconComponent size={20} />
                </span>
                {!collapsed && <span className="nav-label">{item.label}</span>}
              </NavLink>
            </li>
          );
        })}
      </ul>

      <div className="nav-section-divider" />

      {/* Markets section */}
      {!collapsed && <div className="nav-section-label">Markets</div>}
      <ul className="nav-links nav-sub-links">
        {marketsItems.map((item) => {
          const IconComponent = item.icon;
          return (
            <li key={item.to}>
              <NavLink
                to={item.to}
                className={({ isActive }) =>
                  isActive ? 'nav-link active' : 'nav-link'
                }
                title={collapsed ? item.label : undefined}
              >
                <span className="nav-icon">
                  <IconComponent size={20} />
                </span>
                {!collapsed && <span className="nav-label">{item.label}</span>}
              </NavLink>
            </li>
          );
        })}
      </ul>

      <div className="nav-section-divider" />

      {/* Tools & Settings section */}
      {!collapsed && <div className="nav-section-label">Tools & Settings</div>}
      <ul className="nav-links nav-sub-links">
        {toolsItems.map((item) => {
          const IconComponent = item.icon;
          return (
            <li key={item.to}>
              <NavLink
                to={item.to}
                className={({ isActive }) =>
                  isActive ? 'nav-link active' : 'nav-link'
                }
                title={collapsed ? item.label : undefined}
              >
                <span className="nav-icon">
                  <IconComponent size={20} />
                </span>
                {!collapsed && <span className="nav-label">{item.label}</span>}
              </NavLink>
            </li>
          );
        })}
      </ul>

      <div className="nav-spacer" />

      {/* Bottom section - Logout only */}
      <div className="nav-user-section">
        {user && (
          <button
            className="nav-logout-btn"
            onClick={handleLogout}
            type="button"
            title="Logout"
          >
            {collapsed ? <LogOut size={16} /> : <><LogOut size={16} /> Logout</>}
          </button>
        )}
      </div>

      {/* Footer */}
      <div className="nav-footer">
        {!collapsed && (
          <div className="nav-footer-copyright">
            © 2025 My Investment
          </div>
        )}
      </div>
    </nav>
  );
}
