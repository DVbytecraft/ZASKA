import { apiClient } from "./apiClient";
import type { Task, TaskApplication, TaskPayload, NegotiationEvent } from "./types";

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
      stops: payload.stops,
      scheduled_at: payload.scheduledAt ?? null,
      any_schedule: payload.anySchedule ?? false,
      idempotency_key: payload.idempotencyKey ?? null,
      city: payload.city ?? null,
      country: payload.country ?? null,
    });
  },

  listTasks(status?: string, lat?: number, lng?: number) {
    const params = new URLSearchParams();
    if (status) params.set("status", status);
    if (lat !== undefined && lng !== undefined) {
      params.set("lat", String(lat));
      params.set("lng", String(lng));
    }
    const q = params.toString();
    return apiClient.get<Task[]>(`/tasks${q ? `?${q}` : ""}`);
  },

  listMyTasks(status?: string) {
    const params = new URLSearchParams({ mine: "true" });
    if (status) params.set("status", status);
    return apiClient.get<Task[]>(`/tasks?${params.toString()}`);
  },

  /** Tasks I created that are still open for applications */
  listMyOpenTasks() {
    const params = new URLSearchParams({ mine: "true", status: "OPEN" });
    return apiClient.get<Task[]>(`/tasks?${params.toString()}`);
  },

  /** Tasks I created that are active (ASSIGNED or PENDING_VALIDATION) — "archived" */
  listMyActiveTasks() {
    return taskService.listMyTasks().then((tasks) =>
      tasks.filter((t) => t.status === "ASSIGNED" || t.status === "PENDING_VALIDATION")
    );
  },

  browseAvailableTasks(lat?: number, lng?: number, country?: string, city?: string) {
    const params = new URLSearchParams({ status: "OPEN" });
    if (lat !== undefined && lng !== undefined) {
      params.set("lat", String(lat));
      params.set("lng", String(lng));
    }
    if (country) params.set("country", country);
    if (city) params.set("city", city);
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

  completeTask(taskId: string, partial?: boolean, completionPercent?: number, proofPhotoUrl?: string) {
    return apiClient.post<{ task_id: string; status: string; completion_percent: number; partial: boolean; message: string }>(
      `/tasks/${taskId}/complete`,
      {
        partial: partial ?? false,
        completion_percent: completionPercent ?? 100,
        proof_photo_url: proofPhotoUrl ?? null,
      },
    );
  },

  confirmTask(taskId: string) {
    return apiClient.post<{ message: string }>(`/tasks/${taskId}/confirm`, {});
  },

  cancelTask(taskId: string, republish: boolean, reason?: string) {
    return apiClient.post<Task>(`/tasks/${taskId}/cancel`, { republish, reason: reason ?? null });
  },

  contestTask(taskId: string, reason: string) {
    return apiClient.post<{ escrow_status: string }>(`/tasks/${taskId}/contest`, { reason });
  },

  pauseTask(taskId: string) {
    return apiClient.post<Task>(`/tasks/${taskId}/pause`, {});
  },

  reactivateTask(taskId: string) {
    return apiClient.post<Task>(`/tasks/${taskId}/reactivate`, {});
  },

  deleteTask(taskId: string) {
    return apiClient.delete<{ deleted: boolean }>(`/tasks/${taskId}`);
  },

  listAssignedToMe(status?: string) {
    const params = new URLSearchParams({ assigned_to_me: "true" });
    if (status) params.set("status", status);
    return apiClient.get<Task[]>(`/tasks?${params.toString()}`);
  },

  negotiateTask(taskId: string, proposedBudget: number) {
    return apiClient.post<Task>(`/tasks/${taskId}/negotiate`, { proposed_price: proposedBudget });
  },

  respondToNegotiation(taskId: string, accept: boolean) {
    return apiClient.post<Task>(`/tasks/${taskId}/negotiate/respond`, { accept });
  },

  abandonNegotiation(taskId: string) {
    return apiClient.post<Task>(`/tasks/${taskId}/negotiate/abandon`, {});
  },

  getNegotiationHistory(taskId: string) {
    return apiClient.get<NegotiationEvent[]>(`/tasks/${taskId}/negotiate/history`);
  },

  counterPropose(taskId: string, proposedPrice: number) {
    return apiClient.post<Task>(`/tasks/${taskId}/negotiate/counter`, { proposed_price: proposedPrice });
  },

  rateTask(taskId: string, score: number) {
    return apiClient.post<{ rated: boolean; score: number }>(`/tasks/${taskId}/rate`, { score });
  },

  /**
   * Exécutant se désiste.
   * completionPercent = 0 → remboursement intégral au client.
   * completionPercent 1–99 → exécutant payé proportionnellement, client remboursé du reste.
   */
  taskerAbandon(taskId: string, completionPercent = 0) {
    return apiClient.post<Task & { completion_percent_declared: number; payment_summary: string; message: string }>(
      `/tasks/${taskId}/tasker-abandon`,
      { completion_percent: completionPercent },
    );
  },
};
