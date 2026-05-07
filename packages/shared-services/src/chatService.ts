import { apiClient } from "./apiClient";

export interface ChatMessage {
  id: string;
  taskId: string;
  senderId: string;
  message: string;
  createdAt: string;
}

export const chatService = {
  listMessages(taskId: string) {
    return apiClient.get<ChatMessage[]>(`/chat/${taskId}`);
  },

  sendMessage(taskId: string, message: string) {
    return apiClient.post<ChatMessage>("/chat", { task_id: taskId, message });
  },
};
