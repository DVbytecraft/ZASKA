export interface ApiEnvelope<T> {
  success: boolean;
  data: T;
  error: string | null;
}

export interface Task {
  id: string;
  title: string;
  description: string;
  price: number;
  currency: string;
  latitude: number;
  longitude: number;
  address?: string;
  city?: string;
  country?: string;
  status: "OPEN" | "ASSIGNED" | "IN_PROGRESS" | "COMPLETED" | "CONFIRMED" | "CANCELLED" | "DISPUTED" | "PAUSED";
  createdBy: string;
  assignedTo: string | null;
  mode?: string;
  negotiatedPrice?: number;
  completionPercent?: number;
  proofPhotoUrl?: string;
}

export interface TaskApplication {
  id: string;
  taskId: string;
  taskerId: string;
  proposedPrice?: number;
  currency: string;
  status: "pending" | "accepted" | "rejected";
  message?: string;
  createdAt: string;
}

export interface NegotiationEvent {
  id: string;
  taskId: string;
  userId: string;
  type: string;
  proposedPrice?: number;
  createdAt: string;
}

export interface ChatMessage {
  taskId: string;
  senderId: string;
  message: string;
}

export interface FeatureFlag {
  id: string;
  feature: string;
  enabled: boolean;
}

export interface UserProfile {
  id: string;
  email: string;
  role: string;
  first_name: string | null;
  last_name: string | null;
  full_name: string | null;
  phone: string | null;
  avatar_url: string | null;
  country_code: string | null;
  is_verified: boolean;
  tasker_security_verified?: boolean;
  biometric_enabled?: boolean;
  criminal_record_status?: string | null;
  countryLaunchStatus?: string;
  countryActive?: boolean;
  foodDeliveryEnabled?: boolean;
  badges?: UserBadge[];
  trustScore?: UserTrustScore;
}

export interface Transaction {
  id: string;
  type: string;
  amount: string;
  status: string;
  reference: string;
  provider: string;
  created_at: string;
}

export interface PaymentMethod {
  id: string;
  type: string;
  details: Record<string, string>;
  isDefault: boolean;
}

export interface VirtualCard {
  id: string;
  card_type: string;
  currency: string;
  status: string;
  masked_number?: string;
  created_at: string;
}

export interface WalletSummary {
  balances: Record<string, { balance: string; pending: string }>;
}

export interface NotificationItem {
  id: string;
  type: string;
  title: string;
  body: string;
  read: boolean;
  task_id: string | null;
  created_at: string;
}

export interface KycStatus {
  status: string;
  reviewerNote?: string | null;
  reviewedAt?: string | null;
  approvedAt?: string | null;
  expiresAt?: string | null;
  isExpired?: boolean;
  daysRemaining?: number | null;
  createdAt?: string | null;
}

export interface UserBadge {
  code: string;
  label: string;
  description: string;
  icon: string;
  awarded_at: string;
}

export interface UserTrustScore {
  totalScore: number;
  level: string;
  computedAt: string;
}

export interface SplitHistoryEntry {
  transaction_id: string;
  task_id: string | null;
  task_title: string | null;
  escrow_id: string | null;
  currency: string;
  gross_amount: string;
  released_at: string;
  reference: string;
  split: {
    tasker_net: string;
    zaska_operations: string;
    pension_fund: string;
    health_fund: string;
    smoothing_fund: string;
  };
}

export interface SocialProtectionCurrencySummary {
  currency: string;
  pension: {
    total_contributed: string;
    simulated_interest: string;
    projected_monthly_pension: string;
    projection_basis: string;
    progress_percent_to_guarantee: number;
  };
  health: {
    status: "ACTIVE" | "INACTIVE";
    activation_date: string | null;
    active_days_this_month: number;
    total_paid_to_authorities: string;
  };
  smoothing: {
    available_balance: string;
    total_contributed: string;
    interest_redirected_to_pension: string;
    interventions: Array<Record<string, string>>;
  };
}

export interface SocialProtectionOverview {
  balances: Array<{ currency: string; balance: string }>;
  total_completed_tasks: number;
  first_task_at: string | null;
  active_months: number;
  badge: {
    code: string;
    label: string;
    description: string;
  };
  currencies: SocialProtectionCurrencySummary[];
}

const BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:6969/api";

let accessToken: string | null = localStorage.getItem("zaska_access_token");
let refreshToken: string | null = localStorage.getItem("zaska_refresh_token");

export function setTokens(tokens: { accessToken: string; refreshToken: string }) {
  accessToken = tokens.accessToken;
  refreshToken = tokens.refreshToken;
  localStorage.setItem("zaska_access_token", tokens.accessToken);
  localStorage.setItem("zaska_refresh_token", tokens.refreshToken);
}

export function clearTokens() {
  accessToken = null;
  refreshToken = null;
  localStorage.removeItem("zaska_access_token");
  localStorage.removeItem("zaska_refresh_token");
}

export function getWsBaseUrl(): string {
  const raw = import.meta.env.VITE_WS_URL as string | undefined;
  if (raw?.trim()) return raw.replace(/\/$/, "");
  try {
    const u = new URL(BASE_URL);
    const wsProto = u.protocol === "https:" ? "wss:" : "ws:";
    return `${wsProto}//${u.host}`;
  } catch {
    return "ws://localhost:6969";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<ApiEnvelope<T>> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
  let response = await fetch(`${BASE_URL}${path}`, { ...init, headers: { ...headers, ...(init?.headers ?? {}) } });
  if (response.status === 401 && refreshToken) {
    const refreshed = await fetch(`${BASE_URL}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (refreshed.ok) {
      const payload = (await refreshed.json()) as ApiEnvelope<{ accessToken: string; refreshToken: string }>;
      if (payload.success) {
        setTokens(payload.data);
        headers.Authorization = `Bearer ${payload.data.accessToken}`;
        response = await fetch(`${BASE_URL}${path}`, { ...init, headers: { ...headers, ...(init?.headers ?? {}) } });
      } else {
        clearTokens();
        localStorage.removeItem("zaska_user_id");
        window.location.href = "/auth";
        return { success: false, data: null as T, error: "Session expirée" };
      }
    } else {
      clearTokens();
      localStorage.removeItem("zaska_user_id");
      window.location.href = "/auth";
      return { success: false, data: null as T, error: "Session expirée" };
    }
  }
  return (await response.json()) as ApiEnvelope<T>;
}

export interface TaskCreateInput {
  title: string;
  description: string;
  price: number;
  currency: string;
  latitude: number;
  longitude: number;
  status?: string;
}

export const api = {
  // ── Auth ──────────────────────────────────────────────────────────────────
  register: (payload: { email?: string; firstName: string; lastName: string; phone: string; role: string; password: string; country?: string }) =>
    request<{ userId: string; email: string }>("/auth/register", { method: "POST", body: JSON.stringify(payload) }),
  verifyOtp: (email: string, code: string) =>
    request<{ accessToken: string; refreshToken: string; userId: string }>("/auth/verify-otp", {
      method: "POST",
      body: JSON.stringify({ email, code }),
    }),
  login: (email: string, password: string) =>
    request<{ accessToken: string; refreshToken: string; userId: string }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  logout: () =>
    request<{ loggedOut: boolean }>("/auth/logout", { method: "POST", body: JSON.stringify({ refresh_token: refreshToken }) }),
  issueWsTicket: () => request<{ ticket: string }>("/auth/ws-ticket", { method: "POST", body: "{}" }),

  // ── User ──────────────────────────────────────────────────────────────────
  getMe: () => request<UserProfile>("/users/me"),
  getUserProfile: (userId: string) => request<UserProfile>(`/users/${userId}`),
  getKycStatus: () => request<KycStatus>("/kyc/status"),

  // ── Tasks ─────────────────────────────────────────────────────────────────
  createTask: (payload: TaskCreateInput) =>
    request<Task>("/tasks", { method: "POST", body: JSON.stringify(payload) }),
  listTasks: (params?: { status?: string; city?: string; country?: string }) => {
    const qs = new URLSearchParams();
    if (params?.status) qs.set("status", params.status);
    if (params?.city) qs.set("city", params.city);
    if (params?.country) qs.set("country", params.country);
    const q = qs.toString();
    return request<Task[]>(`/tasks${q ? `?${q}` : ""}`);
  },
  getTask: (taskId: string) => request<Task>(`/tasks/${taskId}`),
  acceptTask: (taskId: string) =>
    request<Task>(`/tasks/${taskId}/accept`, { method: "POST", body: "{}" }),
  updateTaskStatus: (taskId: string, status: string) =>
    request<Task>(`/tasks/${taskId}/status`, { method: "PATCH", body: JSON.stringify({ status }) }),
  cancelTask: (taskId: string, reason?: string) =>
    request<Task>(`/tasks/${taskId}/cancel`, { method: "POST", body: JSON.stringify({ republish: false, reason: reason ?? "" }) }),
  deleteTask: (taskId: string) =>
    request<{ deleted: boolean }>(`/tasks/${taskId}`, { method: "DELETE" }),

  // Task applications
  applyTask: (taskId: string, message?: string, proposedPrice?: number) =>
    request<{ applied: boolean }>(`/tasks/${taskId}/apply`, {
      method: "POST",
      body: JSON.stringify({ message: message ?? "", proposed_price: proposedPrice }),
    }),
  listApplications: (taskId: string) =>
    request<TaskApplication[]>(`/tasks/${taskId}/applications`),
  acceptApplicant: (taskId: string, applicantId: string) =>
    request<Task>(`/tasks/${taskId}/accept`, { method: "POST", body: JSON.stringify({ applicant_id: applicantId }) }),
  getMyApplications: () => request<TaskApplication[]>("/tasks/my-applications"),

  // Task lifecycle
  completeTask: (taskId: string, completionPercent?: number, proofPhotoUrl?: string) =>
    request<Task>(`/tasks/${taskId}/complete`, {
      method: "POST",
      body: JSON.stringify({ completion_percent: completionPercent ?? 100, proof_photo_url: proofPhotoUrl }),
    }),
  confirmTask: (taskId: string) =>
    request<Task>(`/tasks/${taskId}/confirm`, { method: "POST", body: "{}" }),
  contestTask: (taskId: string, reason: string) =>
    request<Task>(`/tasks/${taskId}/contest`, { method: "POST", body: JSON.stringify({ reason }) }),
  rateTask: (taskId: string, score: number) =>
    request<{ rated: boolean }>(`/tasks/${taskId}/rate`, { method: "POST", body: JSON.stringify({ score }) }),

  // Negotiation
  negotiateTask: (taskId: string, proposedBudget: number) =>
    request<Task>(`/tasks/${taskId}/negotiate`, { method: "POST", body: JSON.stringify({ proposed_budget: proposedBudget }) }),
  respondNegotiation: (taskId: string, accept: boolean) =>
    request<Task>(`/tasks/${taskId}/negotiate/respond`, { method: "POST", body: JSON.stringify({ accept }) }),
  counterPropose: (taskId: string, proposedPrice: number) =>
    request<Task>(`/tasks/${taskId}/negotiate/counter`, { method: "POST", body: JSON.stringify({ proposed_price: proposedPrice }) }),
  abandonNegotiation: (taskId: string) =>
    request<Task>(`/tasks/${taskId}/negotiate/abandon`, { method: "POST", body: "{}" }),
  getNegotiationHistory: (taskId: string) =>
    request<NegotiationEvent[]>(`/tasks/${taskId}/negotiate/history`),

  // ── Wallet ────────────────────────────────────────────────────────────────
  getWalletBalance: (currency: string) =>
    request<{ currency: string; balance: string }>(`/wallet/balance/${currency}`),
  getWalletTransactions: (currency: string) =>
    request<Transaction[]>(`/wallet/transactions/${currency}`),
  getWalletSummary: () => request<WalletSummary>("/wallet/summary"),
  getWalletSplits: (currency?: string, limit = 20, offset = 0) => {
    const qs = new URLSearchParams();
    if (currency) qs.set("currency", currency);
    qs.set("limit", String(limit));
    qs.set("offset", String(offset));
    return request<SplitHistoryEntry[]>(`/wallet/splits?${qs.toString()}`);
  },
  getSocialProtection: () =>
    request<SocialProtectionOverview>("/wallet/social-protection"),
  deposit: (amount: string, currency: string) =>
    request<{ checkout_url?: string; status?: string; mode?: string }>("/wallet/deposit", {
      method: "POST",
      body: JSON.stringify({ amount, currency }),
    }),
  withdraw: (amount: string, currency: string, destinationPhone: string, destinationCountry: string, destinationName?: string) =>
    request<{ status: string; reference: string }>("/wallet/withdraw", {
      method: "POST",
      body: JSON.stringify({
        amount,
        currency,
        destination_phone: destinationPhone,
        destination_country: destinationCountry,
        destination_name: destinationName,
      }),
    }),
  transfer: (toUserId: string, amount: string, currency: string, note?: string) =>
    request<{ status: string }>("/wallet/transfer", {
      method: "POST",
      body: JSON.stringify({ to_user_id: toUserId, amount, currency, note }),
    }),
  convert: (fromCurrency: string, toCurrency: string, amount: string) =>
    request<{ converted_amount: string; rate: string }>("/wallet/convert", {
      method: "POST",
      body: JSON.stringify({ from_currency: fromCurrency, to_currency: toCurrency, amount }),
    }),

  // Payment methods
  listPaymentMethods: () => request<PaymentMethod[]>("/wallet/payment-methods"),
  deletePaymentMethod: (id: string) =>
    request<{ deleted: boolean }>(`/wallet/payment-methods/${id}`, { method: "DELETE" }),

  // ── Virtual Cards ─────────────────────────────────────────────────────────
  listCards: () => request<VirtualCard[]>("/cards"),
  createCard: (cardType: "visa" | "mastercard", walletCurrency: string) =>
    request<VirtualCard>("/cards", { method: "POST", body: JSON.stringify({ card_type: cardType, wallet_currency: walletCurrency }) }),
  updateCardStatus: (cardId: string, status: "active" | "frozen" | "cancelled") =>
    request<VirtualCard>(`/cards/${cardId}/status`, { method: "PATCH", body: JSON.stringify({ status }) }),

  // ── Chat ──────────────────────────────────────────────────────────────────
  sendChat: (taskId: string, message: string) =>
    request<ChatMessage>("/chat", { method: "POST", body: JSON.stringify({ task_id: taskId, message }) }),
  listChat: (taskId: string) => request<ChatMessage[]>(`/chat/${taskId}`),
  getNotifications: () => request<NotificationItem[]>("/notifications"),
  getUnreadNotificationsCount: () => request<{ count: number }>("/notifications/unread-count"),
  markNotificationRead: (notificationId: string) =>
    request<NotificationItem>(`/notifications/${notificationId}/read`, { method: "PATCH", body: "{}" }),
  markAllNotificationsRead: () =>
    request<{ marked: boolean }>("/notifications/mark-all-read", { method: "POST", body: "{}" }),

  // ── Feature Flags ─────────────────────────────────────────────────────────
  listFlags: () => request<FeatureFlag[]>("/feature-flags"),
};
