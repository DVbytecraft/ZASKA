export type TaskMode = "fast" | "choose";

export interface AuthSession {
  accessToken: string;
  refreshToken: string;
  userId: string;
  country?: string;
  currency?: string;
  paymentProvider?: string;
  mobileMoneyEnabled?: boolean;
}

export interface LoginPayload {
  email: string;
  password: string;
}

export interface RegisterPayload {
  email?: string;
  firstName: string;
  lastName: string;
  phone: string;
  password: string;
  role: string;
  country?: string;
}

export interface RegisterResponse {
  userId: string;
  phone: string;
}

export interface SavedPaymentMethod {
  id: string;
  method_type: string;
  provider: string;
  phone_number: string;
  country_code: string;
  nickname: string;
  details: string;
  is_default: boolean;
}

export interface WithdrawPayload {
  amount: string;
  currency: string;
  provider: string;
  phone_number: string;
  country_code: string;
}

export interface WithdrawResponse {
  tx_id: string;
  status: string;
  amount: string;
  currency: string;
  provider: string;
  phone_number: string;
  reference: string;
}

export interface AddPaymentMethodPayload {
  method_type?: string;
  provider: string;
  phone_number: string;
  country_code: string;
  nickname?: string;
  is_default?: boolean;
}


export interface VerifyOtpPayload {
  phone: string;
  code: string;
}

export interface SetPasswordPayload {
  email: string;
  password: string;
}

export interface UpdateProfilePayload {
  full_name?: string;
  first_name?: string;
  last_name?: string;
  avatar_url?: string;
}

export interface UserProfile {
  id: string;
  email: string | null;
  role: string;
  first_name: string | null;
  last_name: string | null;
  full_name: string | null;
  phone: string | null;
  avatar_url: string | null;
  country_code: string | null;
  is_verified: boolean;
}

export interface TaskPayload {
  title?: string;
  description: string;
  price?: number;
  budget?: number;
  currency: string;
  latitude: number;
  longitude: number;
  mode?: TaskMode;
  status?: string;
}

export interface Task {
  id: string;
  title: string;
  description: string;
  price: number;
  currency: string;
  latitude: number;
  longitude: number;
  address?: string | null;
  status: "OPEN" | "ASSIGNED" | "COMPLETED";
  createdBy: string;
  assignedTo: string | null;
  mode?: TaskMode;
  createdAt?: string | null;
  negotiationStatus?: string | null;
  negotiatedPrice?: number | null;
  completionPercent?: number | null;
}

export interface TaskApplication {
  id: string;
  taskId: string;
  taskerId: string;
  taskerName?: string;
  taskerRating?: number;
  taskerReviews?: number;
  proposedPrice?: number;
  currency: string;
  status: "pending" | "accepted" | "rejected";
  createdAt: string;
}

export interface WalletBalance {
  currency: string;
  balance: string;
}

export interface Transaction {
  id: string;
  type: "credit" | "debit";
  amount: string;
  status: "pending" | "completed" | "failed" | "reversed";
  reference: string;
  provider: string;
  created_at: string;
}

export interface Escrow {
  escrow_id: string;
  task_id: string;
  payer_id?: string;
  payee_id?: string | null;
  amount: string;
  currency: string;
  status: "pending" | "funded" | "released" | "refunded" | "cancelled";
}

export interface PaymentIntent {
  mode: string;
  real_money_enabled: boolean;
  provider: string;
  provider_intent_id: string;
  client_secret: string | null;
  payment_url: string | null;
  escrow_id: string;
  amount: string;
  currency: string;
  commission: number;
  escrow_amount: number;
  idempotency_key: string;
}

export interface PaymentMethod {
  id: string;
  type: string;
  details: string;
  isDefault: boolean;
}
