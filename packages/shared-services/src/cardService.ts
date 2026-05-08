import { apiClient } from "./apiClient";
import type { VirtualCard, VirtualCardCreateResult } from "./types";

export const cardService = {
  listCards() {
    return apiClient.get<VirtualCard[]>("/cards");
  },

  createCard(cardType: "visa" | "mastercard", walletCurrency: string) {
    return apiClient.post<VirtualCardCreateResult>("/cards", {
      card_type: cardType,
      wallet_currency: walletCurrency,
    });
  },

  updateCardStatus(cardId: string, status: "active" | "frozen" | "cancelled") {
    return apiClient.patch<VirtualCard>(`/cards/${cardId}/status`, { status });
  },
};
