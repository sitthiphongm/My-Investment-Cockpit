import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { adminApi, authApi } from '../api';
import type { AdminUser, User, UserStatus } from '../types';
import { UserStatus as UserStatusEnum } from '../types';
import { formatDate } from '../utils/format';
import { useSortableData } from '../hooks/useSortableData';
import toast from 'react-hot-toast';

// ===== Main Component =====

export default function AdminPage() {
  const navigate = useNavigate();
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionInProgress, setActionInProgress] = useState<string | null>(null);

  // Load current user info (AdminRoute already guarantees we're admin)
  useEffect(() => {
    authApi
      .getMe()
      .then((user) => {
        setCurrentUser(user);
      })
      .catch(() => {
        navigate('/', { replace: true });
      });
  }, [navigate]);

  const fetchUsers = useCallback(async () => {
    try {
      const result = await adminApi.listUsers();
      setUsers(result ?? []);
    } catch {
      // Error handled by interceptor
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (currentUser) {
      fetchUsers();
    }
  }, [currentUser, fetchUsers]);

  // ===== Action Handlers =====

  const handleApprove = async (userId: string) => {
    setActionInProgress(userId);
    try {
      await adminApi.approveUser(userId);
      toast.success('User approved successfully', { duration: 4000 });
      fetchUsers();
    } catch {
      // Error handled by interceptor
    } finally {
      setActionInProgress(null);
    }
  };

  const handleBlock = async (userId: string) => {
    setActionInProgress(userId);
    try {
      await adminApi.blockUser(userId);
      toast.success('User blocked successfully', { duration: 4000 });
      fetchUsers();
    } catch {
      // Error handled by interceptor
    } finally {
      setActionInProgress(null);
    }
  };

  const handleStatusChange = async (userId: string, status: UserStatus) => {
    setActionInProgress(userId);
    try {
      await adminApi.setUserStatus(userId, status);
      toast.success(`User status changed to ${status}`, { duration: 4000 });
      fetchUsers();
    } catch {
      // Error handled by interceptor
    } finally {
      setActionInProgress(null);
    }
  };

  // ===== Render =====

  if (loading) {
    return (
      <div className="page admin-page">
        <h1>Admin</h1>
        <p className="loading-text" aria-live="polite">Loading users...</p>
      </div>
    );
  }

  return (
    <div className="page admin-page">
      <h1>Admin</h1>
      <p>Manage user accounts and access.</p>

      {users.length === 0 ? (
        <div className="empty-state" role="status">
          <div className="empty-state-icon">👥</div>
          <h2>No Users</h2>
          <p>No registered users found.</p>
        </div>
      ) : (
        <UserTable
          users={users}
          currentUserId={currentUser?.id ?? ''}
          actionInProgress={actionInProgress}
          onApprove={handleApprove}
          onBlock={handleBlock}
          onStatusChange={handleStatusChange}
        />
      )}
    </div>
  );
}

// ===== User Table Component =====

interface UserTableProps {
  users: AdminUser[];
  currentUserId: string;
  actionInProgress: string | null;
  onApprove: (userId: string) => void;
  onBlock: (userId: string) => void;
  onStatusChange: (userId: string, status: UserStatus) => void;
}

function UserTable({
  users,
  currentUserId,
  actionInProgress,
  onApprove,
  onBlock,
  onStatusChange,
}: UserTableProps) {
  const { sortedItems, requestSort, getSortIndicator } = useSortableData(users);

  return (
    <div className="table-container">
      <table className="data-table" aria-label="Registered users">
        <thead>
          <tr>
            <th scope="col" className="sortable-th" onClick={() => requestSort('display_name')}>User{getSortIndicator('display_name')}</th>
            <th scope="col" className="sortable-th" onClick={() => requestSort('email')}>Email{getSortIndicator('email')}</th>
            <th scope="col">Provider</th>
            <th scope="col" className="sortable-th" onClick={() => requestSort('registered_at')}>Registered{getSortIndicator('registered_at')}</th>
            <th scope="col" className="sortable-th" onClick={() => requestSort('status')}>Status{getSortIndicator('status')}</th>
            <th scope="col">Actions</th>
          </tr>
        </thead>
        <tbody>
          {sortedItems.map((user) => (
            <tr key={user.id}>
              <td>
                <div className="user-cell">
                  {user.profile_picture_url ? (
                    <img
                      src={user.profile_picture_url}
                      alt={`${user.display_name}'s profile`}
                      className="user-avatar"
                    />
                  ) : (
                    <div className="user-avatar-placeholder" aria-hidden="true">
                      {user.display_name.charAt(0).toUpperCase()}
                    </div>
                  )}
                  <span className="user-display-name">
                    {user.display_name}
                    {user.is_admin && <span className="admin-badge">Admin</span>}
                  </span>
                </div>
              </td>
              <td>{user.email}</td>
              <td>
                <span className="provider-badge">
                  {user.oauth_provider === 'google' ? '🔵 Google' : '🔷 Facebook'}
                </span>
              </td>
              <td>{formatDate(user.registered_at)}</td>
              <td>
                <StatusBadge status={user.status} />
              </td>
              <td className="actions-cell">
                <UserActions
                  user={user}
                  currentUserId={currentUserId}
                  actionInProgress={actionInProgress}
                  onApprove={onApprove}
                  onBlock={onBlock}
                  onStatusChange={onStatusChange}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ===== Status Badge Component =====

function StatusBadge({ status }: { status: UserStatus }) {
  const className = `status-badge status-${status.toLowerCase()}`;
  return <span className={className}>{status}</span>;
}

// ===== User Actions Component =====

interface UserActionsProps {
  user: AdminUser;
  currentUserId: string;
  actionInProgress: string | null;
  onApprove: (userId: string) => void;
  onBlock: (userId: string) => void;
  onStatusChange: (userId: string, status: UserStatus) => void;
}

function UserActions({
  user,
  currentUserId,
  actionInProgress,
  onApprove,
  onBlock,
  onStatusChange,
}: UserActionsProps) {
  const isDisabled = actionInProgress === user.id;
  const isSelf = user.id === currentUserId;

  // Don't show actions for the current admin user (can't change own status)
  if (isSelf) {
    return <span className="actions-self-label">—</span>;
  }

  return (
    <div className="user-actions-group">
      {user.status !== UserStatusEnum.APPROVED && (
        <button
          className="btn btn-sm btn-success"
          onClick={() => onApprove(user.id)}
          disabled={isDisabled}
          title="Approve user"
          aria-label={`Approve ${user.display_name}`}
        >
          ✓ Approve
        </button>
      )}
      {user.status !== UserStatusEnum.BLOCKED && (
        <button
          className="btn btn-sm btn-danger"
          onClick={() => onBlock(user.id)}
          disabled={isDisabled}
          title="Block user"
          aria-label={`Block ${user.display_name}`}
        >
          ✕ Block
        </button>
      )}
      {user.status !== UserStatusEnum.PENDING && (
        <button
          className="btn btn-sm btn-secondary"
          onClick={() => onStatusChange(user.id, UserStatusEnum.PENDING)}
          disabled={isDisabled}
          title="Revert to pending"
          aria-label={`Set ${user.display_name} to pending`}
        >
          ⏳ Pending
        </button>
      )}
    </div>
  );
}
