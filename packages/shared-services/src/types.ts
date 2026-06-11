export type TaskMode = "fast" | "choose";

export interface TaskStop {
  address: string;
  latitude: number;
  longitude: number;
}

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
  cf_turnstile_response?: string;
}

export interface RegisterPayload {
  email?: string;
  firstName: string;
  lastName: string;
  phone: string;
  password: string;
  role: string;
  country?: string;
  cf_turnstile_response?: string;
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
  tasker_security_verified?: boolean;
  biometric_enabled?: boolean;
  criminal_record_status?: string | null;
  countryLaunchStatus?: string;
  countryActive?: boolean;
  foodDeliveryEnabled?: boolean;
  badges?: Array<{
    code: string;
    label: string;
    description: string;
    icon: string;
    awarded_at: string;
  }>;
  trustScore?: {
    totalScore: number;
    level: string;
    computedAt: string;
  };
}

export interface TaskPayload {
  title?: string;
  description: string;
  price?: number;
  budget?: number;
  currency: string;
  latitude?: number;
  longitude?: number;
  address?: string;
  mode?: TaskMode;
  status?: string;
  stops?: TaskStop[];
  scheduledAt?: string | null;
  anySchedule?: boolean;
  idempotencyKey?: string;
  city?: string;
  country?: string;
}

export interface UserAddress {
  id: string;
  label: string;
  street: string;
  city: string;
  country: string;
  latitude: number | null;
  longitude: number | null;
  isDefault: boolean;
  createdAt: string;
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
  status: "OPEN" | "ASSIGNED" | "PENDING_VALIDATION" | "COMPLETED" | "PAUSED" | "CANCELLED";
  createdBy: string;
  assignedTo: string | null;
  mode?: TaskMode;
  createdAt?: string | null;
  negotiationStatus?: string | null;
  originalPrice?: number | null;
  negotiatedPrice?: number | null;
  negotiatedBy?: string | null;
  completionPercent?: number | null;
  distanceKm?: number | null;
  scheduledAt?: string | null;
  anySchedule?: boolean | null;
  stops?: TaskStop[] | null;
  city?: string | null;
  country?: string | null;
  creatorRated?: boolean;
  proofPhotoUrl?: string | null;
}

export interface VirtualCard {
  id: string;
  cardType: "visa" | "mastercard";
  cardNumberMasked: string;
  expiryMonth: number;
  expiryYear: number;
  status: "active" | "frozen" | "cancelled";
  walletCurrency: string;
  createdAt: string;
}

export interface VirtualCardCreateResult extends VirtualCard {
  cardNumber: string;
  cvv: string;
  expiryFormatted: string;
  notice: string;
}

export interface TaskApplication {
  id: string;
  taskId: string;
  taskerId: string;
  taskerName?: string;
  taskerEmail?: string;
  taskerRating?: number;
  taskerReviews?: number;
  proposedPrice?: number | null;
  currency: string;
  status: "pending" | "accepted" | "rejected";
  message?: string | null;
  createdAt: string;
}

export interface WalletBalance {
  currency: string;
  balance: string;
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
  balances: WalletBalance[];
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

export interface Transaction {
  id: string;
  type: "credit" | "debit";
  amount: string;
  currency: string;
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

export interface NegotiationEvent {
  id: string;
  taskId: string;
  actorId: string;
  actorName: string;
  /** "proposed" | "accepted" | "rejected" | "abandoned" | "counter" */
  eventType: string;
  price: number | null;
  currency: string;
  createdAt: string;
}
