import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type Task, type TaskApplication } from "../api";

type Tab = "all" | "open" | "mine" | "applications";

const STATUS_LABELS: Record<string, string> = {
  OPEN: "Ouvert", ASSIGNED: "Assigné", IN_PROGRESS: "En cours",
  COMPLETED: "Complété", CONFIRMED: "Confirmé", CANCELLED: "Annulé",
  DISPUTED: "Contesté", PAUSED: "En pause",
};
const STATUS_COLORS: Record<string, string> = {
  OPEN: "bg-blue-100 text-blue-700", ASSIGNED: "bg-amber-100 text-amber-700",
  IN_PROGRESS: "bg-amber-100 text-amber-700", COMPLETED: "bg-purple-100 text-purple-700",
  CONFIRMED: "bg-green-100 text-green-700", CANCELLED: "bg-gray-100 text-gray-500",
  DISPUTED: "bg-red-100 text-red-700", PAUSED: "bg-gray-100 text-gray-500",
};

export function TaskListPage() {
  const userId = localStorage.getItem("zaska_user_id") ?? "";
  const [tab, setTab] = useState<Tab>("all");
  const [tasks, setTasks] = useState<Task[]>([]);
  const [applications, setApplications] = useState<TaskApplication[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  useEffect(() => {
    setLoading(true);
    setError(null);
    void (async () => {
      if (tab === "applications") {
        const res = await api.getMyApplications();
        setLoading(false);
        if (!res.success) { setError(res.error ?? "Erreur"); return; }
        setApplications(res.data ?? []);
      } else {
        const params = tab === "open" ? { status: "OPEN" } : tab === "mine" ? { status: undefined } : undefined;
        const res = await api.listTasks(params);
        setLoading(false);
        if (!res.success) { setError(res.error ?? "Erreur"); return; }
        let list = res.data ?? [];
        if (tab === "mine") list = list.filter((t) => t.createdBy === userId || t.assignedTo === userId);
        setTasks(list);
      }
    })();
  }, [tab, userId]);

  const filtered = search.trim()
    ? tasks.filter((t) => t.title.toLowerCase().includes(search.toLowerCase()) || (t.city ?? "").toLowerCase().includes(search.toLowerCase()))
    : tasks;

  const tabs: { key: Tab; label: string }[] = [
    { key: "all", label: "Toutes" },
    { key: "open", label: "Disponibles" },
    { key: "mine", label: "Mes tâches" },
    { key: "applications", label: "Mes candidatures" },
  ];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">Tâches</h2>
        <Link to="/tasks/new" className="bg-gray-900 text-white px-3 py-1.5 rounded-lg text-sm font-medium">
          + Créer
        </Link>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-gray-100 rounded-lg p-1">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`flex-1 text-xs font-medium py-1.5 rounded-md transition-colors ${tab === t.key ? "bg-white text-gray-900 shadow-sm" : "text-gray-500 hover:text-gray-700"}`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Search (only for task tabs, not applications) */}
      {tab !== "applications" && (
        <input
          className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gray-900"
          placeholder="Rechercher par titre ou ville…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      )}

      {/* Content */}
      {loading ? (
        <div className="space-y-2">
          {[1, 2, 3].map((i) => <div key={i} className="h-20 bg-gray-100 rounded-xl animate-pulse" />)}
        </div>
      ) : error ? (
        <p className="text-red-600 text-sm">{error}</p>
      ) : tab === "applications" ? (
        applications.length === 0 ? (
          <div className="border rounded-xl p-8 text-center text-gray-400">
            <p className="text-3xl mb-2">📝</p>
            <p>Aucune candidature envoyée.</p>
          </div>
        ) : (
          <div className="space-y-2">
            {applications.map((app) => (
              <Link key={app.id} to={`/tasks/${app.taskId}`} className="block bg-white border rounded-xl p-4">
                <div className="flex items-center justify-between">
                  <p className="font-medium text-sm">{app.taskId}</p>
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${app.status === "accepted" ? "bg-green-100 text-green-700" : app.status === "rejected" ? "bg-red-100 text-red-700" : "bg-amber-100 text-amber-700"}`}>
                    {app.status === "accepted" ? "Accepté" : app.status === "rejected" ? "Refusé" : "En attente"}
                  </span>
                </div>
                {app.proposedPrice && (
                  <p className="text-sm text-amber-700 mt-1">Proposition : {app.proposedPrice} {app.currency}</p>
                )}
                <p className="text-xs text-gray-400 mt-1">{new Date(app.createdAt).toLocaleDateString("fr-FR")}</p>
              </Link>
            ))}
          </div>
        )
      ) : filtered.length === 0 ? (
        <div className="border rounded-xl p-8 text-center text-gray-400">
          <p className="text-3xl mb-2">🔍</p>
          <p>Aucune tâche trouvée.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {filtered.map((task) => (
            <Link key={task.id} to={`/tasks/${task.id}`} className="block bg-white border rounded-xl p-4 hover:border-gray-400 transition-colors">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="font-semibold truncate">{task.title}</p>
                  {(task.city || task.address) && (
                    <p className="text-xs text-gray-500 mt-0.5 truncate">{[task.city, task.address].filter(Boolean).join(" · ")}</p>
                  )}
                </div>
                <div className="text-right flex-shrink-0">
                  <p className="font-bold text-sm">{parseFloat(String(task.price)).toFixed(2)} {task.currency}</p>
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_COLORS[task.status] ?? "bg-gray-100 text-gray-500"}`}>
                    {STATUS_LABELS[task.status] ?? task.status}
                  </span>
                </div>
              </div>
              {task.createdBy === userId && (
                <p className="text-xs text-blue-600 mt-1">Votre tâche</p>
              )}
              {task.assignedTo === userId && (
                <p className="text-xs text-green-600 mt-1">Assigné à vous</p>
              )}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
