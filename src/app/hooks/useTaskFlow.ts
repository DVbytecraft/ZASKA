import { useState } from "react";
import { taskService, apiClient } from "@zaska/shared-services";
import type { TaskMode } from "@zaska/shared-services";

interface CreateTaskInput {
  description: string;
  budget: string;
  mode: TaskMode;
  latitude: number;
  longitude: number;
  currency?: string;
  title?: string;
  address?: string;
}

export function useTaskFlow() {
  const [loading, setLoading] = useState(false);

  const createTask = async (input: CreateTaskInput) => {
    setLoading(true);
    try {
      return await taskService.createTask({
        title: input.title,
        description: input.description,
        price: Number(input.budget),
        currency: input.currency ?? apiClient.getCurrency() ?? "USD",
        latitude: input.latitude,
        longitude: input.longitude,
        address: input.address,
        mode: input.mode,
      });
    } finally {
      setLoading(false);
    }
  };

  return { loading, createTask };
}

export function requestGeolocation(): Promise<{ latitude: number; longitude: number }> {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) {
      reject(new Error("Geolocation not supported"));
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => resolve({ latitude: pos.coords.latitude, longitude: pos.coords.longitude }),
      () => reject(new Error("Geolocation denied")),
      { timeout: 8000 }
    );
  });
}
