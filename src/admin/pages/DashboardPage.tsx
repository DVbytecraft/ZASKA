import { useEffect, useState } from 'react';
import { Briefcase, Users, CheckCircle, Clock } from 'lucide-react';
import { adminApi, type AdminStats, type AdminTask } from '../adminApi';
import { KPICard } from '../components/KPICard';
import { DataTable } from '../components/DataTable';

export function DashboardPage() {
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [tasks, setTasks] = useState<AdminTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const [s, t] = await Promise.all([adminApi.getStats(), adminApi.getTasks()]);
        setStats(s);
        setTasks(t.slice(0, 5));
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Erreur de chargement');
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading) {
    return (
      <div className="p-6 flex items-center justify-center h-64">
        <p className="text-gray-500 text-sm">Chargement...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <p className="text-red-600 text-sm bg-red-50 rounded-lg p-4">{error}</p>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">Dashboard</h2>
        <p className="text-sm text-gray-600">Vue d'ensemble de la plateforme</p>
      </div>

      <div className="grid grid-cols-4 gap-6">
        <KPICard label="Tâches ouvertes" value={String(stats?.open_tasks ?? 0)} icon={Briefcase} trend="up" />
        <KPICard label="En cours" value={String(stats?.assigned_tasks ?? 0)} icon={Clock} trend="up" />
        <KPICard label="Terminées" value={String(stats?.completed_tasks ?? 0)} icon={CheckCircle} trend="up" />
        <KPICard label="Utilisateurs" value={String(stats?.total_users ?? 0)} icon={Users} trend="up" />
      </div>

      <div>
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Tâches récentes</h3>
        {tasks.length === 0 ? (
          <p className="text-sm text-gray-500">Aucune tâche pour l'instant.</p>
        ) : (
          <DataTable
            columns={[
              { key: 'id', label: 'ID' },
              { key: 'title', label: 'Titre' },
              { key: 'status', label: 'Statut', render: (value) => (
                <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                  value === 'COMPLETED' ? 'bg-green-100 text-green-700' :
                  value === 'ASSIGNED' ? 'bg-blue-100 text-blue-700' :
                  'bg-gray-100 text-gray-700'
                }`}>{value}</span>
              )},
              { key: 'price', label: 'Prix', render: (value, row) => `${value} ${(row as AdminTask).currency}` },
            ]}
            data={tasks}
          />
        )}
      </div>
    </div>
  );
}
