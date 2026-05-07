import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type Task } from "../api";

function StatCard({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className={`rounded-xl p-4 ${color}`}>
      <p className="text-3xl font-bold">{value}</p>
      <p className="text-sm font-medium mt-1">{label}</p>
    </div>
  );
}

export function DashboardPage() {
  const [stats, setStats] = useState({ open: 0, assigned: 0, completed: 0, total: 0 });
  const [myTasks, setMyTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      const res = await api.listTasks();
      setLoading(false);
      if (!res.success) {
        setError(res.error ?? "Impossible de charger les tâches");
        return;
      }
      const tasks = res.data;
      setStats({
        open: tasks.filter((t) => t.status === "OPEN").length,
        assigned: tasks.filter((t) => t.status === "ASSIGNED").length,
        completed: tasks.filter((t) => t.status === "COMPLETED").length,
        total: tasks.length,
      });
      setMyTasks(tasks.slice(0, 5));
    })();
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold">Dashboard</h2>
        <p className="text-sm text-gray-500">Vue d'ensemble de vos activités ZASKA.</p>
      </div>

      {loading ? (
        <p className="text-gray-400">Chargement...</p>
      ) : error ? (
        <p className="text-red-600 text-sm">{error}</p>
      ) : (
        <>
          <div className="grid grid-cols-3 gap-4">
            <StatCard label="Ouvertes" value={stats.open} color="bg-blue-50 text-blue-700" />
            <StatCard label="Assignées" value={stats.assigned} color="bg-amber-50 text-amber-700" />
            <StatCard label="Terminées" value={stats.completed} color="bg-green-50 text-green-700" />
          </div>

          <div className="flex gap-3">
            <Link to="/tasks/new" className="bg-black text-white rounded px-4 py-2 text-sm">
              Créer une tâche
            </Link>
            <Link to="/tasks" className="border rounded px-4 py-2 text-sm">
              Voir toutes ({stats.total})
            </Link>
          </div>

          {myTasks.length > 0 && (
            <div>
              <h3 className="font-semibold mb-2">Tâches récentes</h3>
              <div className="space-y-2">
                {myTasks.map((task) => (
                  <Link
                    key={task.id}
                    to={`/tasks/${task.id}`}
                    className="flex items-center justify-between border rounded p-3 bg-white hover:bg-gray-50"
                  >
                    <span className="font-medium text-sm">{task.title}</span>
                    <span
                      className={`text-xs px-2 py-0.5 rounded-full ${
                        task.status === "OPEN"
                          ? "bg-blue-100 text-blue-700"
                          : task.status === "ASSIGNED"
                          ? "bg-amber-100 text-amber-700"
                          : "bg-green-100 text-green-700"
                      }`}
                    >
                      {task.status}
                    </span>
                  </Link>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
