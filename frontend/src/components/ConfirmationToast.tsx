import toast from 'react-hot-toast';

/**
 * ConfirmationToast - Wrapper around react-hot-toast for consistent
 * success/error messages across the app.
 *
 * Messages are visible for at least 3 seconds and dismissible by the user.
 */

export interface ToastOptions {
  /** Duration in ms (minimum 3000). Default: 4000 */
  duration?: number;
}

/**
 * Show a success toast message.
 * Visible for at least 3 seconds, dismissible by clicking.
 * Uses dark theme tokens: positive-bg background, positive text color.
 */
export function showSuccessToast(message: string, options?: ToastOptions) {
  const duration = Math.max(options?.duration ?? 4000, 3000);
  toast.success(message, {
    duration,
    position: 'top-right',
    style: {
      background: '#0F172A',
      color: '#22C55E',
      border: '1px solid rgba(34, 197, 94, 0.3)',
      borderRadius: '10px',
      fontSize: '0.85rem',
      fontWeight: 500,
    },
  });
}

/**
 * Show an error toast message.
 * Visible for at least 3 seconds, dismissible by clicking.
 * Uses dark theme tokens: negative-bg background, negative text color.
 */
export function showErrorToast(message: string, options?: ToastOptions) {
  const duration = Math.max(options?.duration ?? 5000, 3000);
  toast.error(message, {
    duration,
    position: 'top-right',
    style: {
      background: '#0F172A',
      color: '#EF4444',
      border: '1px solid rgba(239, 68, 68, 0.3)',
      borderRadius: '10px',
      fontSize: '0.85rem',
      fontWeight: 500,
    },
  });
}

/**
 * Dismiss all currently visible toasts.
 */
export function dismissAllToasts() {
  toast.dismiss();
}

const ConfirmationToast = {
  success: showSuccessToast,
  error: showErrorToast,
  dismissAll: dismissAllToasts,
};

export default ConfirmationToast;
