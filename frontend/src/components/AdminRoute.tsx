import { useEffect, useState } from 'react';
import { Navigate } from 'react-router-dom';
import { authApi } from '../api';

interface AdminRouteProps {
  children: React.ReactNode;
}

/**
 * AdminRoute guard that checks if the current user has admin role.
 * Redirects non-admin users to the dashboard.
 * This is used in addition to ProtectedRoute (which handles auth).
 */
export default function AdminRoute({ children }: AdminRouteProps) {
  const [state, setState] = useState<'loading' | 'admin' | 'not-admin'>('loading');

  useEffect(() => {
    authApi
      .getMe()
      .then((user) => {
        setState(user.is_admin ? 'admin' : 'not-admin');
      })
      .catch(() => {
        setState('not-admin');
      });
  }, []);

  if (state === 'loading') {
    return (
      <div className="page admin-page">
        <h1>Admin</h1>
        <p className="loading-text" aria-live="polite">Checking permissions...</p>
      </div>
    );
  }

  if (state === 'not-admin') {
    return <Navigate to="/" replace />;
  }

  return <>{children}</>;
}
