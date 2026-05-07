import { apiClient } from "./apiClient";
import type { PaymentIntent, PaymentMethod } from "./types";

export const paymentService = {
  getPaymentMethods() {
    return apiClient.get<PaymentMethod[]>("/payments/methods");
  },

  createIntent(taskId: string) {
    return apiClient.post<PaymentIntent>("/payments/create-intent", { task_id: taskId });
  },

  mockSuccess(escrowId: string) {
    return apiClient.post<{ escrow_id: string; status: string; mode: string }>(
      "/payments/mock/success",
      { escrow_id: escrowId }
    );
  },

  mockFailure(escrowId: string) {
    return apiClient.post<{ escrow_id: string; status: string; mode: string }>(
      "/payments/mock/failure",
      { escrow_id: escrowId }
    );
  },
};
