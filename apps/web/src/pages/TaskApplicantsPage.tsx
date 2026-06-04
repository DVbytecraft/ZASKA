import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, type Task, type TaskApplication } from "../api";

export function TaskApplicantsPage() {
  const { taskId = "" } = useParams();
  const navigate = useNavigate();

  const [task, setTask] = useState<Task | null>(null);
  const [apps, setApps] = useState<TaskApplication[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [accepting, setAccepting] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      const [taskRes, appsRes] = await Promise.all([api.getTask(taskId), api.listApplications(taskId)]);
      setLoading(false);
      if (!taskRes.success) { setError(taskRes.error ?? "Erreur"); return; }
      setTask(taskRes.data);
      if (appsRes.success) setApps(appsRes.data ?? []);
    })();
  }, [taskId]);

  async function handleAccept(applicantId: string) {
    setAccepting(applicantId);
    const res = await api.acceptApplicant(taskId, applicantId);
    setAccepting(null);
    if (res.success) {
      setMsg("Tasker sélectionné, tâche assignée !");
      navigate(`/tasks/${taskId}`);
    } else {
      setMsg(res.error ?? "Erreur lors de la sélection");
    }
  }

  const statusLabel: Record<string, string> = {
    pending: "En attente",
    accepted: "Accepté",
    rejected: "Refusé",
  };
  const statusColor: Record<string, string> = {
    pending: "bg-amber-100 text-amber-700",
    accepted: "bg-green-100 text-green-700",
    rejected: "bg-red-100 text-red-700",
  };

  if (loading) return <p className="text-gray-500">Chargement…</p>;
  if (error) return <p className="text-red-600">{error}</p>;

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <button onClick={() => navigate(`/tasks/${taskId}`)} className="text-sm text-gray-500 hover:text-gray-800">← Retour</button>
        <h2 className="text-xl font-bold">{task?.title}</h2>
      </div>

      <p className="text-sm text-gray-600">{apps.length} candidature{apps.length !== 1 ? "s" : ""}</p>

      {msg && (
        <div className="text-sm bg-green-50 border border-green-200 text-green-800 px-4 py-3 rounded-xl">
          {msg}
        </div>
      )}

      {apps.length === 0 ? (
        <div className="border rounded-xl p-8 text-center text-gray-400">
          <p className="text-3xl mb-2">📭</p>
          <p>Aucune candidature pour l'instant.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {apps.map((app) => (
            <div key={app.id} className="bg-white border rounded-xl p-4 space-y-2">
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium text-sm">{app.taskerId}</p>
                  {app.proposedPrice && (
                    <p className="text-sm text-amber-700 font-semibold">
                      Propose : {app.proposedPrice} {app.currency}
                    </p>
                  )}
                </div>
                <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${statusColor[app.status] ?? "bg-gray-100 text-gray-500"}`}>
                  {statusLabel[app.status] ?? app.status}
                </span>
              </div>
              {app.message && (
                <p className="text-sm text-gray-600 bg-gray-50 rounded-lg px-3 py-2">{app.message}</p>
              )}
              <p className="text-xs text-gray-400">
                {new Date(app.createdAt).toLocaleDateString("fr-FR", { day: "2-digit", month: "long", year: "numeric" })}
              </p>
              {app.status === "pending" && task?.status === "OPEN" && (
                <button
                  className="bg-gray-900 text-white px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-40"
                  disabled={accepting === app.taskerId}
                  onClick={() => void handleAccept(app.taskerId)}
                >
                  {accepting === app.taskerId ? "…" : "Sélectionner ce tasker"}
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
