import { apiClient } from '@zaska/shared-services';

const BASE_URL = (typeof import.meta !== 'undefined' && (import.meta as any).env?.VITE_API_URL)
  ? (import.meta as any).env.VITE_API_URL as string
  : 'http://localhost:6969/api';

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  // Use shared in-memory token (supports auto-refresh) instead of localStorage
  const token = apiClient.getAccessToken();
  const res = await fetch(`${BASE_URL}${path}`, {
    method,
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(body ? { 'Content-Type': 'application/json' } : {}),
    },
    ...(body ? { body: JSON.stringify(body) } : {}),
  });
  if (!res.ok) throw new Error(`${path} failed: ${res.status}`);
  const json = await res.json() as { success: boolean; data: T; error: string | null };
  if (!json.success) throw new Error(json.error ?? 'API error');
  return json.data;
}

const get = <T>(path: string) => request<T>('GET', path);
const post = <T>(path: string, body?: unknown) => request<T>('POST', path, body);
const patch = <T>(path: string, body?: unknown) => request<T>('PATCH', path, body);

// ─── Types ────────────────────────────────────────────────────────────────────

export interface AdminStats {
  total_tasks: number;
  open_tasks: number;
  assigned_tasks: number;
  completed_tasks: number;
  total_users: number;
  verified_users: number;
  total_revenue?: string;
  revenue_currency?: string;
}

export interface AdminTask {
  id: string;
  title: string;
  description: string;
  price: string;
  currency: string;
  status: string;
  created_by: string;
  assigned_to: string | null;
  latitude?: number;
  longitude?: number;
  created_at: string;
}

export interface AdminUser {
  id: string;
  email: string | null;
  phone: string | null;
  first_name: string | null;
  last_name: string | null;
  full_name: string | null;
  role: string;
  is_verified: boolean;
  country_code: string | null;
  created_at: string;
  is_suspended?: boolean;
  is_locked?: boolean;
  kyc_status?: 'not_submitted' | 'pending' | 'approved' | 'rejected';
}

export interface AdminTransaction {
  id: string;
  user_id: string;
  user_name?: string;
  user_phone?: string;
  type: 'deposit' | 'withdrawal' | 'transfer' | 'escrow' | 'release' | 'refund' | 'adjustment';
  amount: string;
  currency: string;
  status: 'completed' | 'pending' | 'failed' | 'cancelled';
  provider?: string;
  reference?: string;
  description?: string;
  created_at: string;
}

export interface AdminDispute {
  id: string;
  task_id: string;
  task_title?: string;
  reporter_id: string;
  reporter_name?: string;
  respondent_id?: string;
  respondent_name?: string;
  reason: string;
  description?: string;
  status: 'open' | 'under_review' | 'resolved' | 'closed';
  resolution?: 'in_favor_reporter' | 'in_favor_respondent' | 'partial_refund' | 'dismissed';
  resolution_note?: string;
  created_at: string;
  updated_at?: string;
}

export interface AdminSupportTicket {
  id: string;
  user_id: string;
  user_name: string;
  user_phone?: string;
  category: 'payment' | 'task' | 'account' | 'technical' | 'other';
  priority: 'low' | 'medium' | 'high' | 'urgent';
  status: 'open' | 'in_progress' | 'resolved' | 'escalated' | 'closed';
  subject: string;
  description: string;
  agent_id?: string;
  agent_name?: string;
  notes?: string;
  created_at: string;
  updated_at?: string;
  wait_minutes?: number;
}

export interface AdminWalletInfo {
  user_id: string;
  user_name?: string;
  currency: string;
  balance: string;
  locked_balance?: string;
}

export interface AdminEscrow {
  escrow_id: string;
  task_id: string;
  task_title?: string;
  client_id: string;
  client_name?: string;
  tasker_id: string | null;
  tasker_name?: string | null;
  amount: string;
  currency: string;
  status: 'funded' | 'released' | 'refunded' | 'disputed';
  created_at: string;
}

export interface AdminPaymentProvider {
  id: string;
  name: string;
  type: 'card' | 'mobile_money' | 'bank';
  countries: string[];
  status: 'operational' | 'degraded' | 'down';
  success_rate: number;
  last_checked?: string;
}

export interface AdminCountry {
  code: string;
  currency: string;
  mobile_money_enabled: boolean;
  payment_providers: string[];
}

export interface AdminUserDetail extends AdminUser {
  wallet?: AdminWalletInfo;
  recent_transactions?: AdminTransaction[];
  active_tasks?: AdminTask[];
}

export interface AdminKycSubmission {
  id: string;
  user_id: string;
  status: 'pending' | 'approved' | 'rejected';
  id_document_url?: string | null;
  selfie_url?: string | null;
  reviewed_by?: string | null;
  reviewer_note?: string | null;
  created_at: string;
}

export interface AdminAuditLog {
  id: string;
  action: string;
  user_id: string;
  payment_id?: string | null;
  transaction_id?: string | null;
  amount: string;
  currency: string;
  provider?: string | null;
  status: string;
  country_code?: string | null;
  created_at: string;
}

export interface AdminFraudFlags {
  payout_blocked: { user_id: string; consecutive_failures: number }[];
  rapid_cycle_candidates: { user_id: string }[];
}

// ─── API ──────────────────────────────────────────────────────────────────────

export const adminApi = {
  // Stats
  getStats: () => get<AdminStats>('/admin/stats'),

  // Tasks
  getTasks: () => get<AdminTask[]>('/admin/tasks'),
  forceAssignTask: (taskId: string, taskerId: string) =>
    post<AdminTask>(`/admin/tasks/${taskId}/assign`, { tasker_id: taskerId }),
  cancelTask: (taskId: string, reason: string) =>
    post<AdminTask>(`/admin/tasks/${taskId}/cancel`, { reason }),

  // Users
  getUsers: () => get<AdminUser[]>('/admin/users'),
  getUserDetail: (id: string) =>
    get<AdminUserDetail>(`/admin/users/${id}`).catch(async () => {
      const base = await get<AdminUser>(`/admin/users/${id}`);
      return base as AdminUserDetail;
    }),
  lookupByPhone: (phone: string) =>
    get<AdminUserDetail>(`/admin/users/lookup?phone=${encodeURIComponent(phone)}`),
  suspendUser: (id: string, reason: string) =>
    post<void>(`/admin/users/${id}/suspend`, { reason }),
  unsuspendUser: (id: string) =>
    post<void>(`/admin/users/${id}/unsuspend`, {}),
  banUser: (id: string, reason: string) =>
    post<void>(`/admin/users/${id}/ban`, { reason }),
  verifyUser: (id: string) =>
    post<void>(`/admin/users/${id}/verify`, {}),
  lockAccount: (id: string, reason: string) =>
    post<void>(`/admin/users/${id}/lock`, { reason }),
  unlockAccount: (id: string) =>
    post<void>(`/admin/users/${id}/unlock`, {}),

  // Wallet & finance
  adjustBalance: (userId: string, amount: string, currency: string, reason: string) =>
    post<void>('/admin/wallet/adjust', { user_id: userId, amount, currency, reason }),
  getTransactions: (params?: { user_id?: string; status?: string; type?: string }) => {
    const entries = Object.entries(params ?? {}).filter(([, v]) => v != null) as [string, string][];
    const q = entries.length ? '?' + new URLSearchParams(entries).toString() : '';
    return get<AdminTransaction[]>(`/admin/transactions${q}`);
  },
  getEscrows: (status?: string) =>
    get<AdminEscrow[]>(`/admin/escrows${status ? `?status=${status}` : ''}`),
  releaseEscrow: (escrowId: string) =>
    post<void>(`/admin/escrows/${escrowId}/release`, {}),
  refundEscrow: (escrowId: string, reason: string) =>
    post<void>(`/admin/escrows/${escrowId}/refund`, { reason }),
  retryTransaction: (txId: string) =>
    post<void>(`/admin/transactions/${txId}/retry`, {}),

  // Disputes
  getDisputes: (status?: string) =>
    get<AdminDispute[]>(`/admin/disputes${status ? `?status=${status}` : ''}`),
  resolveDispute: (id: string, resolution: string, note: string) =>
    post<AdminDispute>(`/admin/disputes/${id}/resolve`, { resolution: resolution === 'in_favor_reporter' ? 'resolved' : resolution === 'dismissed' ? 'rejected' : 'resolved', admin_notes: note }),

  // Support tickets
  getSupportTickets: (status?: string) =>
    get<AdminSupportTicket[]>(`/admin/support${status ? `?status=${status}` : ''}`),
  createSupportTicket: (data: {
    user_id: string; category: string; priority: string; subject: string; description: string;
  }) => post<AdminSupportTicket>('/admin/support', data),
  updateTicket: (id: string, data: Partial<Pick<AdminSupportTicket, 'notes' | 'status' | 'priority'>>) =>
    patch<AdminSupportTicket>(`/admin/support/${id}`, data),
  resolveTicket: (id: string, notes: string) =>
    post<AdminSupportTicket>(`/admin/support/${id}/resolve`, { notes }),
  escalateTicket: (id: string) =>
    post<AdminSupportTicket>(`/admin/support/${id}/escalate`, {}),
  triggerRefund: (userId: string, amount: string, currency: string, reason: string, ticketId?: string) =>
    post<{ reference: string }>('/admin/support/refund', {
      user_id: userId, amount, currency, reason, ticket_id: ticketId,
    }),
  sendNotification: (userId: string, message: string, channel: 'sms' | 'push') =>
    post<void>('/admin/notifications/send', { user_id: userId, message, channel }),

  // Providers & countries
  getPaymentProviders: () =>
    get<AdminPaymentProvider[]>('/admin/providers').catch(() => [] as AdminPaymentProvider[]),
  getCountries: () => get<AdminCountry[]>('/admin/countries'),

  // KYC
  getKycSubmissions: (status?: string) =>
    get<AdminKycSubmission[]>(`/admin/kyc${status ? `?status=${status}` : ''}`),
  approveKyc: (submissionId: string) =>
    post<{ submission_id: string; status: string }>(`/admin/kyc/${submissionId}/approve`),
  rejectKyc: (submissionId: string, reason: string) =>
    post<{ submission_id: string; status: string }>(`/admin/kyc/${submissionId}/reject`, { reason }),

  // Audit logs
  getAuditLogs: (params?: { user_id?: string; action?: string; limit?: number; offset?: number }) => {
    const entries = Object.entries(params ?? {}).filter(([, v]) => v != null).map(([k, v]) => [k === 'user_id' ? 'user_id_filter' : k === 'action' ? 'action_filter' : k, String(v)]);
    const q = entries.length ? '?' + new URLSearchParams(entries as [string, string][]).toString() : '';
    return get<AdminAuditLog[]>(`/admin/audit-logs${q}`);
  },

  // Fraud flags
  getFraudFlags: () => get<AdminFraudFlags>('/admin/fraud/flags'),
  clearFraudFlags: async (userId: string) => {
    const token = apiClient.getAccessToken();
    const BASE = (typeof import.meta !== 'undefined' && (import.meta as any).env?.VITE_API_URL)
      ? (import.meta as any).env.VITE_API_URL as string
      : 'http://localhost:6969/api';
    const r = await fetch(`${BASE}/admin/fraud/flags/${userId}`, {
      method: 'DELETE',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!r.ok) throw new Error(`DELETE fraud flags failed: ${r.status}`);
    const j = await r.json() as { success: boolean; data: unknown; error: string | null };
    if (!j.success) throw new Error(j.error ?? 'API error');
    return j.data;
  },
};
