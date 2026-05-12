import { apiClient } from "./apiClient";
import type {
  AuthSession,
  LoginPayload,
  RegisterPayload,
  RegisterResponse,
  VerifyOtpPayload,
  SetPasswordPayload,
} from "./types";

export const authService = {
  async register(payload: RegisterPayload): Promise<RegisterResponse> {
    return apiClient.post<RegisterResponse>("/auth/register", payload);
  },

  async verifyOtp(payload: VerifyOtpPayload): Promise<AuthSession> {
    const session = await apiClient.post<AuthSession>("/auth/verify-otp", payload);
    apiClient.setTokens({ accessToken: session.accessToken, refreshToken: session.refreshToken });
    apiClient.setCountry(session.country ?? null, session.currency ?? null);
    apiClient.setUserId(session.userId ?? null);
    return session;
  },

  async resendOtp(phone: string): Promise<void> {
    await apiClient.post("/auth/resend-otp", { phone });
  },

  async setPassword(payload: SetPasswordPayload): Promise<void> {
    await apiClient.post<{ passwordSet: boolean }>("/auth/set-password", payload);
  },

  async login(payload: LoginPayload): Promise<AuthSession> {
    const session = await apiClient.post<AuthSession>("/auth/login", payload);
    apiClient.setTokens({ accessToken: session.accessToken, refreshToken: session.refreshToken });
    apiClient.setCountry(session.country ?? null, session.currency ?? null);
    apiClient.setUserId(session.userId ?? null);
    return session;
  },

  async refresh(): Promise<AuthSession> {
    const refreshToken = apiClient.getRefreshToken();
    if (!refreshToken) {
      throw new Error("No active session");
    }
    const session = await apiClient.post<AuthSession>("/auth/refresh", { refresh_token: refreshToken });
    apiClient.setTokens({
      accessToken: session.accessToken,
      refreshToken: session.refreshToken,
    });
    return session;
  },

  async logout(): Promise<void> {
    try {
      const refreshToken = apiClient.getRefreshToken();
      if (refreshToken) {
        await apiClient.post("/auth/logout", { refresh_token: refreshToken });
      }
    } catch {
      // ignore
    }
    apiClient.clearTokens();
  },
};
