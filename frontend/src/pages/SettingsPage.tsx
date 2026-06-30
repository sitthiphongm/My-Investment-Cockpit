import { useEffect, useState } from 'react';
import DarkCard from '../components/DarkCard';
import { Sun, Moon } from 'lucide-react';

type CostBasisMethod = 'FIFO' | 'LIFO' | 'AvgCost' | 'SpecificLot';
type Currency = 'USD' | 'THB';
type ThemeMode = 'dark' | 'light';

interface UserPreferences {
  theme: ThemeMode;
  costBasisMethod: CostBasisMethod;
  defaultBroker: string;
  defaultCurrency: Currency;
  aiMode: boolean;
}

const DEFAULT_PREFERENCES: UserPreferences = {
  theme: 'dark',
  costBasisMethod: 'FIFO',
  defaultBroker: '',
  defaultCurrency: 'USD',
  aiMode: false,
};

function loadPreferences(): UserPreferences {
  try {
    const stored = localStorage.getItem('user-preferences');
    if (stored) {
      return { ...DEFAULT_PREFERENCES, ...JSON.parse(stored) };
    }
  } catch {
    // Ignore parse errors
  }
  // Theme is stored separately by NavigationMenu
  const theme = (localStorage.getItem('theme') as ThemeMode) || 'dark';
  return { ...DEFAULT_PREFERENCES, theme };
}

function savePreferences(prefs: UserPreferences) {
  localStorage.setItem('user-preferences', JSON.stringify(prefs));
  // Keep theme in sync with NavigationMenu's localStorage key
  localStorage.setItem('theme', prefs.theme);
  document.documentElement.setAttribute('data-theme', prefs.theme);
}

export default function SettingsPage() {
  const [preferences, setPreferences] = useState<UserPreferences>(loadPreferences);
  const [saved, setSaved] = useState(false);

  // Apply theme on initial load
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', preferences.theme);
  }, []);

  const updatePreference = <K extends keyof UserPreferences>(
    key: K,
    value: UserPreferences[K]
  ) => {
    setPreferences((prev) => {
      const updated = { ...prev, [key]: value };
      savePreferences(updated);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
      return updated;
    });
  };

  const handleThemeToggle = () => {
    const newTheme: ThemeMode = preferences.theme === 'dark' ? 'light' : 'dark';
    updatePreference('theme', newTheme);
  };

  return (
    <div className="page settings-page">
      <h1>Settings</h1>
      <p className="settings-subtitle">Manage your application preferences.</p>

      {saved && (
        <div className="settings-saved-toast" role="status" aria-live="polite">
          ✓ Preferences saved
        </div>
      )}

      <div className="settings-grid">
        {/* Appearance Section */}
        <DarkCard title="Appearance">
          <div className="settings-field">
            <label className="settings-label" htmlFor="theme-toggle">
              Theme
            </label>
            <p className="settings-description">
              Switch between dark and light mode. Dark mode uses professional
              trading dashboard colors.
            </p>
            <button
              id="theme-toggle"
              type="button"
              className={`settings-toggle-btn ${preferences.theme === 'dark' ? 'active' : ''}`}
              onClick={handleThemeToggle}
              aria-label={`Switch to ${preferences.theme === 'dark' ? 'light' : 'dark'} mode`}
            >
              <span className="settings-toggle-icon">
                {preferences.theme === 'dark' ? <Moon size={16} /> : <Sun size={16} />}
              </span>
              <span className="settings-toggle-text">
                {preferences.theme === 'dark' ? 'Dark Mode' : 'Light Mode'}
              </span>
            </button>
          </div>
        </DarkCard>

        {/* Trading Defaults Section */}
        <DarkCard title="Trading Defaults">
          <div className="settings-field">
            <label className="settings-label" htmlFor="cost-basis-method">
              Default Cost Basis Method
            </label>
            <p className="settings-description">
              Select the default method for calculating realized P/L on sell
              transactions.
            </p>
            <select
              id="cost-basis-method"
              className="settings-select"
              value={preferences.costBasisMethod}
              onChange={(e) =>
                updatePreference('costBasisMethod', e.target.value as CostBasisMethod)
              }
            >
              <option value="FIFO">FIFO (First In, First Out)</option>
              <option value="LIFO">LIFO (Last In, First Out)</option>
              <option value="AvgCost">Average Cost</option>
              <option value="SpecificLot">Specific Lot</option>
            </select>
          </div>
        </DarkCard>

        {/* Broker & Currency Section */}
        <DarkCard title="Broker & Currency">
          <div className="settings-field">
            <label className="settings-label" htmlFor="default-broker">
              Default Broker
            </label>
            <p className="settings-description">
              Pre-fill this broker name when adding new transactions or transfers.
            </p>
            <input
              id="default-broker"
              type="text"
              className="settings-input"
              placeholder="e.g. Interactive Brokers, Schwab"
              value={preferences.defaultBroker}
              onChange={(e) => updatePreference('defaultBroker', e.target.value)}
              maxLength={100}
            />
          </div>

          <div className="settings-field">
            <label className="settings-label" htmlFor="default-currency">
              Default Currency
            </label>
            <p className="settings-description">
              Primary currency for portfolio display and new transactions.
            </p>
            <select
              id="default-currency"
              className="settings-select"
              value={preferences.defaultCurrency}
              onChange={(e) =>
                updatePreference('defaultCurrency', e.target.value as Currency)
              }
            >
              <option value="USD">USD — US Dollar</option>
              <option value="THB">THB — Thai Baht</option>
            </select>
          </div>
        </DarkCard>

        {/* AI Mode Section */}
        <DarkCard title="AI Mode">
          <div className="settings-field">
            <label className="settings-label" htmlFor="ai-mode-toggle">
              AI Insights
            </label>
            <p className="settings-description">
              AI-powered features are disabled for MVP. This will be enabled in a
              future release with rule-based insights and optional LLM support.
            </p>
            <div className="settings-ai-disabled">
              <button
                id="ai-mode-toggle"
                type="button"
                className="settings-toggle-btn disabled"
                disabled
                aria-label="AI mode is disabled for MVP"
              >
                <span className="settings-toggle-text">Disabled</span>
              </button>
              <span className="settings-badge-mvp">MVP — Coming Soon</span>
            </div>
          </div>
        </DarkCard>
      </div>
    </div>
  );
}
