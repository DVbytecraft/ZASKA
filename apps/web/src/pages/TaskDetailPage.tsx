import { Link, useParams } from "react-router-dom";
import { useEffect, useState } from "react";
import { api } from "../api";

export function TaskDetailPage() {
  const { taskId = "" } = useParams();
  const [task, setTask] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      const res = await api.getTask(taskId);
      if (!res.success) {
        setError(res.error ?? "Failed to load task");
        return;
      }
      setTask(res.data);
    })();
  }, [taskId]);

  if (error) return <p className="text-red-600">{error}</p>;
  if (!task) return <p>Loading task...</p>;

  return (
    <div className="space-y-3">
      <h2 className="text-2xl font-bold">{task.title}</h2>
      <p>{task.description}</p>
      <p className="text-sm text-gray-600">
        {task.price} {task.currency} - {task.status}
      </p>
      <Link className="text-blue-600 underline" to={`/chat/${task.id}`}>
        Open Chat
      </Link>
    </div>
  );
}
