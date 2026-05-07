import { apiClient } from "./apiClient";
import type {
  Escrow,
  Transaction,
  WalletBalance,
  SavedPaymentMethod,
  WithdrawPayload,
  WithdrawResponse,
  AddPaymentMethodPayload,
} from "./types";

export type DepositProvider = "stripe" | "mobile_money" | "fedapay" | "flutterwave";

export interface DepositPayload {
  amount: string;
  currency: string;
  provider?: DepositProvider;
}

export interface DepositResponse {
  mode: "mock" | "stripe_checkout" | "mobile_money";
  // Stripe Checkout
  checkout_url?: string;
  session_id?: string;
  // Mobile Money
  payment_url?: string;
  provider?: string;
  provider_tx_id?: string;
  // All modes
  tx_id?: string;
  amount: string;
  currency: string;
  reference: string;
  status?: string;
}

export interface ConvertPayload {
  from_currency: string;
  to_currency: string;
  amount: string;
}

export interface ConvertResponse {
  from_currency: string;
  to_currency: string;
  from_amount: string;
  to_amount: string;
  fee_amount: string;
  rate: string;
  fee_bps: number;
  debit_tx_id: string;
  credit_tx_id: string;
  reference: string;
  status: string;
}

export interface DepositResponse {
  tx_id: string;
  type: string;
  amount: string;
  currency: string;
  reference: string;
  status: string;
}

export interface TransferPayload {
  to_user_id: string;
  amount: string;
  currency: string;
  note?: string;
}

export interface TransferResponse {
  reference: string;
  amount: string;
  currency: string;
  from_user_id: string;
  to_user_id: string;
  status: string;
}

export const walletService = {
  getBalance(currency: string) {
    return apiClient.get<WalletBalance>(`/wallet/balance/${currency}`);
  },

  getTransactions(currency: string) {
    return apiClient.get<Transaction[]>(`/wallet/transactions/${currency}`);
  },

  getEscrowForTask(taskId: string) {
    return apiClient.get<Escrow>(`/wallet/escrow/task/${taskId}`);
  },

  releaseEscrow(escrowId: string) {
    return apiClient.post<{ escrow_id: string; status: string; job_id: string }>(
      `/wallet/escrow/${escrowId}/release`,
      {}
    );
  },

  refundEscrow(escrowId: string) {
    return apiClient.post<{ escrow_id: string; status: string }>(
      `/wallet/escrow/${escrowId}/refund`,
      {}
    );
  },

  createWallet(currency: string) {
    return apiClient.post<WalletBalance>("/wallet/create", { currency });
  },

  deposit(payload: DepositPayload) {
    return apiClient.post<DepositResponse>("/wallet/deposit", payload);
  },

  depositMobileMoney(amount: string, currency: string, provider: "fedapay" | "flutterwave" = "fedapay") {
    return apiClient.post<DepositResponse>("/wallet/deposit", {
      amount,
      currency,
      provider,
    });
  },

  convert(payload: ConvertPayload) {
    return apiClient.post<ConvertResponse>("/wallet/convert", payload);
  },

  transfer(payload: TransferPayload) {
    return apiClient.post<TransferResponse>("/wallet/transfer", payload);
  },

  withdraw(payload: WithdrawPayload) {
    return apiClient.post<WithdrawResponse>("/wallet/withdraw", payload);
  },

  listPaymentMethods() {
    return apiClient.get<SavedPaymentMethod[]>("/wallet/payment-methods");
  },

  addPaymentMethod(payload: AddPaymentMethodPayload) {
    return apiClient.post<SavedPaymentMethod>("/wallet/payment-methods", payload);
  },

  deletePaymentMethod(id: string) {
    return apiClient.delete<{ deleted: boolean }>(`/wallet/payment-methods/${id}`);
  },
};
