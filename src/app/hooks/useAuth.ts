import { useState } from "react";
import { authService } from "@zaska/shared-services";
import type { AuthSession, RegisterPayload } from "@zaska/shared-services";

export function useAuth() {
  const [session, setSession] = useState<AuthSession | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const register = async (payload: RegisterPayload) => {
    setLoading(true);
    setError(null);
    try {
      const data = await authService.register(payload);
      return data;
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Inscription échouée";
      setError(msg);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const verifyOtp = async (phone: string, code: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await authService.verifyOtp({ phone, code });
      setSession(data);
      return data;
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Code invalide";
      setError(msg);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const setPassword = async (email: string, password: string) => {
    setLoading(true);
    setError(null);
    try {
      await authService.setPassword({ email, password });
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Erreur lors de la création du mot de passe";
      setError(msg);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const login = async (phone: string, password: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await authService.login({ phone, password });
      setSession(data);
      return data;
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Connexion échouée";
      setError(msg);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const logout = async () => {
    await authService.logout();
    setSession(null);
  };

  return { session, loading, error, register, verifyOtp, setPassword, login, logout };
}
