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
      address: payload.address,
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

  browseAvailableTasks(lat?: number, lng?: number) {
    const params = new URLSearchParams({ status: "OPEN" });
    if (lat !== undefined && lng !== undefined) {
      params.set("lat", String(lat));
      params.set("lng", String(lng));
    }
    return apiClient.get<Task[]>(`/tasks?${params.toString()}`);
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

  getMyApplications() {
    return apiClient.get<TaskApplication[]>('/tasks/my-applications');
  },

  listAssignedToMe(status?: string) {
    const params = new URLSearchParams({ assigned_to_me: "true" });
    if (status) params.set("status", status);
    return apiClient.get<Task[]>(`/tasks?${params.toString()}`);
  },

  negotiateTask(taskId: string, proposedBudget: number) {
    return apiClient.post<Task>(`/tasks/${taskId}/negotiate`, { proposed_price: proposedBudget });
  },
};
