import { useEffect, useState } from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { authApi } from '../api';
import type { User } from '../types';

type AuthState =
  | { status: 'loading' }
  | { status: 'authenticated'; user: User }
  | { status: 'unauthenticated' }
  | { status: 'pending' }
  | { status: 'blocked' };

/**
 * ProtectedRoute wraps authenticated routes.
 * - Checks auth status via GET /api/auth/me
 * - Redirects unauthenticated users to /login
 * - Shows pending approval message for PENDING users
 * - Shows blocked error and redirects for BLOCKED users
 */
export default function ProtectedRoute() {
  const [authState, setAuthState] = useState<AuthState>({ status: 'loading' });
  const location = useLocation();

  useEffect(() => {
    authApi
      .getMe()
      .then((user) => {
        if (user.status === 'Pending') {
          setAuthState({ status: 'pending' });
        } else if (user.status === 'Blocked') {
          setAuthState({ status: 'blocked' });
        } else {
          setAuthState({ status: 'authenticated', user });
        }
      })
      .catch(() => {
        setAuthState({ status: 'unauthenticated' });
      });
  }, [location.pathname]);

  switch (authState.status) {
    case 'loading':
      return (
        <div className="auth-loading" aria-live="polite">
          <p>Loading...</p>
        </div>
      );

    case 'unauthenticated':
      return <Navigate to="/login" replace />;

    case 'pending':
      return (
        <div className="auth-pending-page" role="status">
          <div className="auth-pending-container">
            <span className="auth-pending-icon">⏳</span>
            <h1>Pending Approval</h1>
            <p>
              Your account is awaiting admin approval. You will be able to access
              the application once an administrator approves your account.
            </p>
            <button
              className="btn btn-secondary"
              onClick={() => {
                authApi.logout().finally(() => {
                  window.location.href = '/login';
                });
              }}
              type="button"
            >
              Back to Login
            </button>
          </div>
        </div>
      );

    case 'blocked':
      return (
        <div className="auth-blocked-page" role="alert">
          <div className="auth-blocked-container">
            <span className="auth-blocked-icon">🚫</span>
            <h1>Account Blocked</h1>
            <p>
              Your account has been blocked by an administrator. Please contact
              the administrator for more information.
            </p>
            <button
              className="btn btn-secondary"
              onClick={() => {
                authApi.logout().finally(() => {
                  window.location.href = '/login';
                });
              }}
              type="button"
            >
              Back to Login
            </button>
          </div>
        </div>
      );

    case 'authenticated':
      return <Outlet />;
  }
}
