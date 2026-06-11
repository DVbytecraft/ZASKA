import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type Task } from "../api";

function StatCard({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className={`rounded-2xl p-4 ${color}`}>
      <p className="text-3xl font-bold">{value}</p>
      <p className="mt-1 text-sm font-medium">{label}</p>
    </div>
  );
}

export function DashboardPage() {
  const [stats, setStats] = useState({ open: 0, assigned: 0, completed: 0, total: 0 });
  const [myTasks, setMyTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    const load = async () => {
      const res = await api.listTasks();
      if (!active) return;
      setLoading(false);
      if (!res.success) {
        setError(res.error ?? "Impossible de charger les tâches");
        return;
      }
      const tasks = res.data;
      setStats({
        open: tasks.filter((task) => task.status === "OPEN").length,
        assigned: tasks.filter((task) => task.status === "ASSIGNED").length,
        completed: tasks.filter((task) => task.status === "COMPLETED").length,
        total: tasks.length,
      });
      setMyTasks(tasks.slice(0, 5));
    };

    void load();

    return () => {
      active = false;
    };
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-bold text-gray-900">Dashboard</h2>
        <p className="mt-1 text-sm text-gray-500">
          Vue d&apos;ensemble de vos activités Zaska, localement ou à distance.
        </p>
      </div>

      {loading ? (
        <p className="text-gray-400">Chargement...</p>
      ) : error ? (
        <p className="text-sm text-red-600">{error}</p>
      ) : (
        <>
          <div className="grid gap-4 md:grid-cols-3">
            <StatCard label="Tâches ouvertes" value={stats.open} color="bg-blue-50 text-blue-700" />
            <StatCard label="Tâches assignées" value={stats.assigned} color="bg-amber-50 text-amber-700" />
            <StatCard label="Tâches terminées" value={stats.completed} color="bg-green-50 text-green-700" />
          </div>

          <div className="overflow-hidden rounded-3xl bg-gradient-to-r from-gray-950 via-black to-gray-800 p-6 text-white">
            <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
              <div className="max-w-3xl space-y-3">
                <p className="text-xs uppercase tracking-[0.24em] text-gray-300">Plateforme mondiale</p>
                <h3 className="text-3xl font-bold leading-tight">
                  Commandez pour vous ou pour quelqu&apos;un, dans votre zone ou dans un autre pays.
                </h3>
                <p className="text-sm text-gray-300">
                  Zaska vous aide à trouver les bons services, restaurants, marchands et chauffeurs selon le pays,
                  la ville, le quartier et l&apos;adresse ciblée.
                </p>
              </div>
              <div className="flex flex-wrap gap-3">
                <Link
                  to="/marketplace"
                  className="rounded-xl bg-white px-4 py-2 text-sm font-semibold text-gray-900"
                >
                  Explorer tous les modules
                </Link>
                <Link
                  to="/tasks/new"
                  className="rounded-xl border border-white/25 px-4 py-2 text-sm font-medium text-white"
                >
                  Publier une tâche
                </Link>
              </div>
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <Link to="/food" className="rounded-2xl border bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md">
              <p className="text-xs font-semibold uppercase tracking-wide text-rose-500">Local & distance</p>
              <h3 className="mt-2 text-lg font-semibold text-gray-900">Commander à manger</h3>
              <p className="mt-2 text-sm text-gray-500">
                Recherchez des restaurants proches de vous ou proches de la personne que vous souhaitez servir.
              </p>
            </Link>

            <Link to="/shop" className="rounded-2xl border bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md">
              <p className="text-xs font-semibold uppercase tracking-wide text-indigo-500">Local & distance</p>
              <h3 className="mt-2 text-lg font-semibold text-gray-900">Acheter des articles</h3>
              <p className="mt-2 text-sm text-gray-500">
                Achetez auprès de vendeurs locaux selon le pays, la ville, la zone ou l&apos;adresse ciblée.
              </p>
            </Link>

            <Link to="/vtc" className="rounded-2xl border bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md">
              <p className="text-xs font-semibold uppercase tracking-wide text-emerald-500">Mobilité</p>
              <h3 className="mt-2 text-lg font-semibold text-gray-900">Réserver un VTC</h3>
              <p className="mt-2 text-sm text-gray-500">
                Demandez une course locale ou envoyez un trajet pour un proche dans une autre ville.
              </p>
            </Link>

            <Link to="/tasks/new" className="rounded-2xl border bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md">
              <p className="text-xs font-semibold uppercase tracking-wide text-amber-500">Services</p>
              <h3 className="mt-2 text-lg font-semibold text-gray-900">Publier une tâche</h3>
              <p className="mt-2 text-sm text-gray-500">
                Publiez un besoin, recevez des réponses de taskers et négociez le bon tarif si nécessaire.
              </p>
            </Link>
          </div>

          <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
            <div className="rounded-2xl border bg-white p-5">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <h3 className="text-lg font-semibold text-gray-900">Raccourcis opérationnels</h3>
                  <p className="text-sm text-gray-500">
                    Passez rapidement entre vos besoins locaux et les commandes à distance.
                  </p>
                </div>
                <Link to="/tasks" className="text-sm font-medium text-gray-900 underline underline-offset-4">
                  Voir toutes les tâches
                </Link>
              </div>
              <div className="mt-4 grid gap-3 md:grid-cols-2">
                <Link to="/marketplace" className="rounded-xl border border-gray-200 bg-gray-50 p-4 text-sm font-medium text-gray-800">
                  Hub local & distance
                </Link>
                <Link to="/wallet" className="rounded-xl border border-gray-200 bg-gray-50 p-4 text-sm font-medium text-gray-800">
                  Portefeuille & historique
                </Link>
                <Link to="/food/partner" className="rounded-xl border border-rose-100 bg-rose-50 p-4 text-sm font-medium text-rose-700">
                  Interface restaurant
                </Link>
                <Link to="/shop/partner" className="rounded-xl border border-indigo-100 bg-indigo-50 p-4 text-sm font-medium text-indigo-700">
                  Interface vendeur
                </Link>
                <Link to="/vtc/driver" className="rounded-xl border border-emerald-100 bg-emerald-50 p-4 text-sm font-medium text-emerald-700">
                  Interface chauffeur
                </Link>
              </div>
            </div>

            <div className="rounded-2xl border bg-white p-5">
              <h3 className="text-lg font-semibold text-gray-900">Résumé</h3>
              <p className="mt-1 text-sm text-gray-500">
                Vos dernières tâches restent visibles ici pendant que l’on enrichit le cockpit global.
              </p>
              <div className="mt-4 space-y-2">
                {myTasks.length === 0 ? (
                  <p className="text-sm text-gray-400">Aucune tâche récente pour le moment.</p>
                ) : (
                  myTasks.map((task) => (
                    <Link
                      key={task.id}
                      to={`/tasks/${task.id}`}
                      className="flex items-center justify-between rounded-xl border p-3 transition hover:bg-gray-50"
                    >
                      <span className="text-sm font-medium text-gray-900">{task.title}</span>
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs ${
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
                  ))
                )}
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
