import { create } from "zustand";
import { api, clearTokens, setTokens, type UserProfile } from "./api";

interface RegisterPayload {
  email: string;
  firstName: string;
  lastName: string;
  phone: string;
  role: string;
  password: string;
  country?: string;
}

interface AuthState {
  userId: string | null;
  profile: UserProfile | null;
  loading: boolean;
  error: string | null;
  login: (email: string, password: string) => Promise<boolean>;
  register: (payload: RegisterPayload) => Promise<{ ok: boolean }>;
  verifyOtp: (email: string, code: string) => Promise<boolean>;
  logout: () => Promise<void>;
  loadProfile: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  userId: localStorage.getItem("zaska_user_id"),
  profile: null,
  loading: false,
  error: null,

  async loadProfile() {
    const res = await api.getMe();
    if (res.success) set({ profile: res.data });
  },

  async login(email, password) {
    set({ loading: true, error: null });
    const res = await api.login(email, password);
    if (!res.success) {
      set({ loading: false, error: res.error ?? "Login failed" });
      return false;
    }
    setTokens(res.data);
    localStorage.setItem("zaska_user_id", res.data.userId);
    set({ userId: res.data.userId, loading: false });
    void get().loadProfile();
    return true;
  },

  async register(payload) {
    set({ loading: true, error: null });
    const res = await api.register(payload);
    if (!res.success) {
      set({ loading: false, error: res.error ?? "Register failed" });
      return { ok: false };
    }
    set({ loading: false });
    return { ok: true };
  },

  async verifyOtp(email, code) {
    set({ loading: true, error: null });
    const res = await api.verifyOtp(email, code);
    if (!res.success) {
      set({ loading: false, error: res.error ?? "Code invalide" });
      return false;
    }
    setTokens({ accessToken: res.data.accessToken, refreshToken: res.data.refreshToken });
    localStorage.setItem("zaska_user_id", res.data.userId);
    set({ userId: res.data.userId, loading: false });
    void get().loadProfile();
    return true;
  },

  async logout() {
    await api.logout();
    clearTokens();
    localStorage.removeItem("zaska_user_id");
    set({ userId: null, profile: null });
  },
}));
