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
  status: "OPEN" | "ASSIGNED" | "COMPLETED";
  createdBy: string;
  assignedTo: string | null;
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
}

export const api = {
  register: (payload: { email: string; firstName: string; lastName: string; phone: string; role: string; password: string; country?: string }) =>
    request<{ userId: string; email: string }>("/auth/register", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  verifyOtp: (email: string, code: string) =>
    request<{ accessToken: string; refreshToken: string; userId: string }>("/auth/verify-otp", {
      method: "POST",
      body: JSON.stringify({ email, code }),
    }),
  getMe: () => request<UserProfile>("/users/me"),
  getWalletBalance: (currency: string) =>
    request<{ currency: string; balance: string }>(`/wallet/balance/${currency}`),
  getWalletTransactions: (currency: string) =>
    request<{ id: string; type: string; amount: string; status: string; reference: string; provider: string; created_at: string }[]>(`/wallet/transactions/${currency}`),
  deposit: (amount: string, currency: string) =>
    request<unknown>("/wallet/deposit", {
      method: "POST",
      body: JSON.stringify({ amount, currency }),
    }),
  login: (email: string, password: string) =>
    request<{ accessToken: string; refreshToken: string; userId: string }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  issueWsTicket: () => request<{ ticket: string }>("/auth/ws-ticket", { method: "POST", body: "{}" }),
  logout: () =>
    request<{ loggedOut: boolean }>("/auth/logout", {
      method: "POST",
      body: JSON.stringify({ refresh_token: refreshToken }),
    }),
  createTask: (payload: TaskCreateInput) =>
    request<Task>("/tasks", { method: "POST", body: JSON.stringify(payload) }),
  listTasks: (status?: string) =>
    request<Task[]>(`/tasks${status ? `?status=${status}` : ""}`),
  getTask: (taskId: string) => request<Task>(`/tasks/${taskId}`),
  acceptTask: (taskId: string) =>
    request<Task>(`/tasks/${taskId}/accept`, { method: "POST", body: "{}" }),
  updateTaskStatus: (taskId: string, status: string) =>
    request<Task>(`/tasks/${taskId}/status`, { method: "PATCH", body: JSON.stringify({ status }) }),
  sendChat: (taskId: string, message: string) =>
    request<ChatMessage>("/chat", { method: "POST", body: JSON.stringify({ task_id: taskId, message }) }),
  listChat: (taskId: string) => request<ChatMessage[]>(`/chat/${taskId}`),
  listFlags: () => request<FeatureFlag[]>("/feature-flags"),
};
