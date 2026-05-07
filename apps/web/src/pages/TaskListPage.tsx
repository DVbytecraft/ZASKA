import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";

export function TaskListPage() {
  const [tasks, setTasks] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      const res = await api.listTasks();
      setLoading(false);
      if (!res.success) {
        setError(res.error ?? "Failed to load tasks");
        return;
      }
      setTasks(res.data ?? []);
    })();
  }, []);

  if (loading) return <p>Loading tasks...</p>;
  if (error) return <p className="text-red-600">{error}</p>;
  if (!tasks.length) return <p>No tasks found.</p>;

  return (
    <div className="space-y-3">
      <h2 className="text-xl font-semibold">Task List</h2>
      {tasks.map((task) => (
        <Link key={task.id} className="block border rounded p-3 bg-white" to={`/tasks/${task.id}`}>
          <p className="font-semibold">{task.title}</p>
          <p className="text-sm text-gray-600">{task.status}</p>
        </Link>
      ))}
    </div>
  );
}
