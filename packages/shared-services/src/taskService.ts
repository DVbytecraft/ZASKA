import { apiClient } from "./apiClient";
import type { Task, TaskApplication, TaskPayload } from "./types";

export const taskService = {
  createTask(payload: TaskPayload) {
    return apiClient.post<Task>("/tasks", {
      title: payload.title,
      description: payload.description,
      price: payload.price ?? payload.budget,
      currency: payload.currency,
      latitude: payload.latitude,
      longitude: payload.longitude,
      mode: payload.mode,
      status: payload.status,
    });
  },

  listTasks(status?: string) {
    return apiClient.get<Task[]>(`/tasks${status ? `?status=${status}` : ""}`);
  },

  listMyTasks(status?: string) {
    const params = new URLSearchParams({ mine: "true" });
    if (status) params.set("status", status);
    return apiClient.get<Task[]>(`/tasks?${params.toString()}`);
  },

  browseAvailableTasks() {
    return apiClient.get<Task[]>("/tasks?status=OPEN");
  },

  getTask(taskId: string) {
    return apiClient.get<Task>(`/tasks/${taskId}`);
  },

  acceptTask(taskId: string) {
    return apiClient.post<Task>(`/tasks/${taskId}/accept`, {});
  },

  applyTask(taskId: string, payload?: { proposed_price?: number; currency?: string; message?: string }) {
    return apiClient.post(`/tasks/${taskId}/apply`, payload ?? {});
  },

  listApplications(taskId: string) {
    return apiClient.get<TaskApplication[]>(`/tasks/${taskId}/applications`);
  },

  acceptApplicant(taskId: string, applicantId: string) {
    return apiClient.post<Task>(`/tasks/${taskId}/accept`, { tasker_id: applicantId });
  },

  updateTaskStatus(taskId: string, status: string) {
    return apiClient.patch<Task>(`/tasks/${taskId}/status`, { status });
  },

  negotiateTask(taskId: string, proposedBudget: number) {
    return apiClient.post<Task>(`/tasks/${taskId}/negotiate`, { proposed_budget: proposedBudget });
  },
};
