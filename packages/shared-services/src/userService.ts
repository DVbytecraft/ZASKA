import { apiClient } from "./apiClient";
import type { UpdateProfilePayload, UserProfile } from "./types";

export const userService = {
  async getMe(): Promise<UserProfile> {
    return apiClient.get<UserProfile>("/users/me");
  },

  async updateProfile(payload: UpdateProfilePayload): Promise<UserProfile> {
    return apiClient.patch<UserProfile>("/users/me", payload);
  },
};
