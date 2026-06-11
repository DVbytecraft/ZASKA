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
const put = <T>(path: string, body?: unknown) => request<T>('PUT', path, body);

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
  name_en?: string;
  name_fr?: string;
  currency: string;
  mobile_money_enabled: boolean;
  payment_providers: string[];
  is_active: boolean;
  signup_enabled: boolean;
  launch_status: 'PLANNED' | 'CONFIGURED' | 'ACTIVE' | 'SUSPENDED';
  food_delivery_enabled: boolean;
  food_delivery_escrow_minutes: number;
}

export interface AdminPlatformModule {
  code: string;
  label: string;
  description: string;
  module_group: string;
  default_enabled: boolean;
  is_public: boolean;
  requires_country_active: boolean;
}

export interface AdminModuleSetting {
  module_code: string;
  scope_type: string;
  scope_value: string;
  enabled: boolean;
  config?: Record<string, unknown> | null;
  reason?: string | null;
  updated_at?: string | null;
}

export interface AdminModuleRuntimeEntry {
  enabled: boolean;
  source?: string;
  country_active?: boolean;
  config?: Record<string, unknown> | null;
}

export interface AdminGeoContinent {
  code: string;
  name?: string | null;
  name_en?: string | null;
  name_fr?: string | null;
  pricing_profile?: Record<string, unknown> | null;
  launch_status?: string | null;
}

export interface AdminGeoCountryRuntime {
  code?: string;
  country_code?: string;
  countryCode?: string;
  name?: string | null;
  name_en?: string | null;
  name_fr?: string | null;
  continent_code?: string | null;
  continentCode?: string | null;
  primary_city_name?: string | null;
  primaryCityName?: string | null;
  pricing_profile?: Record<string, unknown> | null;
  pricingProfile?: Record<string, unknown> | null;
  launch_status?: string | null;
  is_active?: boolean;
}

export interface AdminPricingTemplate {
  continent_code?: string;
  country_code?: string;
  pricing_profile: Record<string, unknown>;
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
  approved_at?: string | null;
  expires_at?: string | null;
  is_expired?: boolean;
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

export interface AdminSocialProtectionCurrency {
  currency: string;
  pension_balance_total: string;
  health_balance_total: string;
  smoothing_balance_total: string;
  pension_contributions_total: string;
  health_contributions_total: string;
  smoothing_contributions_total: string;
  smoothing_interventions_month: number;
  smoothing_outstanding_total: string;
  simulated_interest_month: string;
}

export interface AdminSocialProtectionCountryRow {
  country_code: string;
  users: number;
  taskers: number;
  protected_taskers: number;
}

export interface AdminSocialProtectionTaskerRow {
  tasker_id: string;
  tasker_name: string;
  country_code: string | null;
  badge?: string | null;
  active_months: number;
  completed_tasks: number;
  currencies: Array<{
    currency: string;
    badge?: string | null;
    pension_total: string;
    health_status: string;
    smoothing_outstanding: string;
  }>;
}

export interface AdminSocialProtectionOverview {
  totals: {
    countries_active: number;
    registered_users: number;
    taskers: number;
    taskers_protected: number;
    kyc_due_soon: number;
  };
  currencies: AdminSocialProtectionCurrency[];
  countries: AdminSocialProtectionCountryRow[];
  taskers: AdminSocialProtectionTaskerRow[];
  generated_at: string;
}

export interface AdminTaskerBadgeCount {
  code: string;
  label: string;
  description: string;
  count: number;
}

export interface AdminTaskerBadgeRow {
  tasker_id: string;
  tasker_name: string;
  country_code: string | null;
  rating_avg: number | null;
  rating_count: number;
  completed_tasks: number;
  active_months: number;
  tasker_security_verified: boolean;
  criminal_record_status: string;
  social_badge?: {
    code: string;
    label: string;
    description: string;
  } | null;
  public_badges: Array<{
    code: string;
    label: string;
    description: string;
    icon: string;
    awarded_at: string;
  }>;
}

export interface AdminAccountingCurrencyOverview {
  currency: string;
  lifetime: Record<string, string>;
  today: Record<string, string>;
  month: Record<string, string>;
  year: Record<string, string>;
  fund_balances: Record<string, {
    wallet_balance: string;
    ledger_balance: string;
    drift: string;
  }>;
  event_totals: {
    smoothing_interventions_total: string;
    smoothing_reimbursements_total: string;
    smoothing_interventions_month: number;
    smoothing_reimbursements_month: number;
  };
  simulated_interest: {
    pension_month: string;
    smoothing_month: string;
  };
}

export interface AdminAccountingOverview {
  summary: {
    released_tasks_count: number;
    currencies_count: number;
  };
  currencies: AdminAccountingCurrencyOverview[];
  tasker_badges: {
    counts: AdminTaskerBadgeCount[];
    taskers: AdminTaskerBadgeRow[];
    generated_at: string;
  };
  generated_at: string;
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
  updateCountry: (countryCode: string, data: Partial<Pick<AdminCountry, 'is_active' | 'signup_enabled' | 'launch_status' | 'food_delivery_enabled' | 'food_delivery_escrow_minutes'>>) =>
    patch<AdminCountry>(`/admin/countries/${countryCode}`, data),
  getModuleCatalog: () => get<{ modules: AdminPlatformModule[] }>('/admin/modules/catalog'),
  getModuleSettings: (params?: { module_code?: string; scope_type?: string; scope_value?: string }) => {
    const entries = Object.entries(params ?? {}).filter(([, v]) => v != null && v !== '');
    const q = entries.length ? `?${new URLSearchParams(entries as [string, string][]).toString()}` : '';
    return get<AdminModuleSetting[]>(`/admin/modules/settings${q}`);
  },
  getModuleRuntime: (countryCode: string) =>
    get<Record<string, AdminModuleRuntimeEntry>>(`/admin/modules/runtime/${countryCode}`),
  updateModuleSetting: (
    moduleCode: string,
    data: { scope_type: string; scope_value: string; enabled: boolean; config?: Record<string, unknown> | null; reason?: string | null }
  ) => put<AdminModuleSetting>(`/admin/modules/${moduleCode}/settings`, data),
  getGeoContinents: () => get<AdminGeoContinent[]>('/admin/geo/continents'),
  getGeoCountriesRuntime: () => get<AdminGeoCountryRuntime[]>('/admin/geo/countries'),
  getGeoCountryRuntime: (countryCode: string) => get<AdminGeoCountryRuntime>(`/admin/geo/countries/${countryCode}`),
  getContinentPricingTemplate: (continentCode: string) =>
    get<AdminPricingTemplate>(`/admin/pricing/templates/continents/${continentCode}`),
  getCountryPricingTemplate: (countryCode: string) =>
    get<AdminPricingTemplate>(`/admin/pricing/templates/countries/${countryCode}`),
  updateContinentPricing: (continentCode: string, pricingProfile: Record<string, unknown> | null) =>
    put<AdminGeoContinent>(`/admin/geo/continents/${continentCode}/pricing`, { pricing_profile: pricingProfile }),
  updateCountryPricing: (countryCode: string, pricingProfile: Record<string, unknown> | null) =>
    put<AdminGeoCountryRuntime>(`/admin/geo/countries/${countryCode}/pricing`, { pricing_profile: pricingProfile }),
  getSocialProtectionOverview: () =>
    get<AdminSocialProtectionOverview>('/admin/social-protection/overview'),
  getAccountingOverview: () =>
    get<AdminAccountingOverview>('/admin/accounting/overview'),

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
