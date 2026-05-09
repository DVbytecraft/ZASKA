import { apiClient } from "./apiClient";

export interface ChatMessage {
  id: string;
  taskId: string;
  senderId: string;
  message: string;
  mediaUrl?: string | null;
  mediaType?: "image" | "video" | "document" | null;
  createdAt: string;
}

export interface MediaUploadResult {
  secure_url: string;
  media_type: "image" | "video" | "document";
  bytes: number;
  format: string;
}

export const chatService = {
  listMessages(taskId: string) {
    return apiClient.get<ChatMessage[]>(`/chat/${taskId}`);
  },

  sendMessage(
    taskId: string,
    message: string,
    mediaUrl?: string,
    mediaType?: ChatMessage["mediaType"],
  ) {
    return apiClient.post<ChatMessage>("/chat", {
      task_id: taskId,
      message,
      ...(mediaUrl ? { media_url: mediaUrl, media_type: mediaType } : {}),
    });
  },

  async uploadMedia(file: File, taskId: string): Promise<MediaUploadResult> {
    const formData = new FormData();
    formData.append("task_id", taskId);
    formData.append("file", file);
    return apiClient.postFormData<MediaUploadResult>("/chat/upload", formData);
  },
};
