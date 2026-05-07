const BASE_URL = (typeof import.meta !== 'undefined' && (import.meta as any).env?.VITE_API_URL)
  ? (import.meta as any).env.VITE_API_URL as string
  : 'http://localhost:6969/api';

function getToken(): string | null {
  return localStorage.getItem('zaska_access_token');
}

async function get<T>(path: string): Promise<T> {
  const token = getToken();
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new Error(`${path} failed: ${res.status}`);
  const json = await res.json() as { success: boolean; data: T; error: string | null };
  if (!json.success) throw new Error(json.error ?? 'API error');
  return json.data;
}

export interface AdminStats {
  total_tasks: number;
  open_tasks: number;
  assigned_tasks: number;
  completed_tasks: number;
  total_users: number;
  verified_users: number;
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
}

export interface AdminCountry {
  code: string;
  currency: string;
  mobile_money_enabled: boolean;
  payment_providers: string[];
}

export const adminApi = {
  getStats: () => get<AdminStats>('/admin/stats'),
  getTasks: () => get<AdminTask[]>('/admin/tasks'),
  getUsers: () => get<AdminUser[]>('/admin/users'),
  getCountries: () => get<AdminCountry[]>('/admin/countries'),
};
