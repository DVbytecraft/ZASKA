import { useEffect, useState } from 'react';
import { Card } from '../components/Card';
import { apiClient } from '@zaska/shared-services';
import {
  TrendingUp, Users, DollarSign, AlertTriangle, CheckCircle,
  RefreshCw, Loader2, Clock, Activity,
} from 'lucide-react';

interface AdminMetrics {
  total_tasks: number;
  open_tasks: number;
  assigned_tasks: number;
  completed_tasks: number;
  total_users: number;
  active_users_today: number;
  total_volume: string;
  currency: string;
  open_disputes: number;
}

interface RecentTask {
  id: string;
  title: string;
  status: string;
  price: number;
  currency: string;
  created_at: string;
}

function statusLabel(status: string): string {
  const map: Record<string, string> = {
    OPEN: 'Ouverte',
    ASSIGNED: 'En cours',
    PENDING_VALIDATION: 'En validation',
    COMPLETED: 'Terminée',
    PAUSED: 'En pause',
  };
  return map[status] ?? status;
}

function statusClass(status: string): string {
  if (status === 'COMPLETED') return 'bg-green-50 text-green-700';
  if (status === 'ASSIGNED') return 'bg-blue-50 text-blue-700';
  if (status === 'PENDING_VALIDATION') return 'bg-amber-50 text-amber-700';
  if (status === 'OPEN') return 'bg-purple-50 text-purple-700';
  return 'bg-gray-50 text-gray-600';
}

function formatDate(iso: string) {
  try {
    return new Date(iso).toLocaleDateString('fr-FR', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  } catch { return iso; }
}

export function AdminDashboardScreen() {
  const [metrics, setMetrics] = useState<AdminMetrics | null>(null);
  const [recentTasks, setRecentTasks] = useState<RecentTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    setLoading(true);
    setError(null);
    Promise.all([
      apiClient.get<AdminMetrics>('/admin/metrics').catch(() => null),
      apiClient.get<RecentTask[]>('/admin/tasks/recent').catch(() => [] as RecentTask[]),
    ]).then(([m, tasks]) => {
      setMetrics(m);
      setRecentTasks(tasks ?? []);
    }).catch((err) => {
      setError(err instanceof Error ? err.message : 'Erreur de chargement');
    }).finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const metricCards = metrics ? [
    {
      label: 'Tâches aujourd\'hui',
      value: String(metrics.total_tasks),
      sub: `${metrics.open_tasks} ouvertes`,
      icon: CheckCircle,
      gradient: 'from-green-500 to-emerald-600',
    },
    {
      label: 'Volume total',
      value: `${metrics.currency} ${Number(metrics.total_volume || 0).toLocaleString('fr-FR')}`,
      sub: `${metrics.completed_tasks} terminées`,
      icon: DollarSign,
      gradient: 'from-purple-500 to-purple-600',
    },
    {
      label: 'Utilisateurs actifs',
      value: String(metrics.total_users),
      sub: `${metrics.active_users_today} aujourd\'hui`,
      icon: Users,
      gradient: 'from-blue-500 to-blue-600',
    },
    {
      label: 'Litiges ouverts',
      value: String(metrics.open_disputes),
      sub: 'en attente de traitement',
      icon: AlertTriangle,
      gradient: 'from-red-500 to-red-600',
    },
  ] : [];

  return (
    <div className="h-full overflow-auto pb-24 bg-gray-50">
      {/* Header */}
      <div className="px-6 pt-8 pb-6 bg-gradient-to-br from-[#6D28D9] to-[#5B21B6]">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white mb-1">Tableau de bord</h1>
            <p className="text-white/75 text-sm">Vue d'ensemble de la plateforme</p>
          </div>
          <button
            onClick={load}
            disabled={loading}
            className="w-10 h-10 rounded-full bg-white/15 hover:bg-white/25 flex items-center justify-center"
          >
            {loading
              ? <Loader2 size={18} className="text-white animate-spin" />
              : <RefreshCw size={18} className="text-white" />}
          </button>
        </div>
      </div>

      <div className="px-6 py-4">
        {error && (
          <div className="mb-4 bg-red-50 border border-red-100 rounded-xl p-3 flex items-center gap-2">
            <AlertTriangle size={16} className="text-red-500" />
            <p className="text-sm text-red-600 flex-1">{error}</p>
            <button onClick={load} className="text-xs font-semibold text-red-700 underline">Réessayer</button>
          </div>
        )}

        {/* Metrics grid */}
        <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3 px-1">Indicateurs clés</h3>
        {loading ? (
          <div className="grid grid-cols-2 gap-3 mb-6">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-28 bg-gray-200 rounded-2xl animate-pulse" />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-3 mb-6">
            {metricCards.map((m) => {
              const Icon = m.icon;
              return (
                <Card key={m.label}>
                  <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${m.gradient} flex items-center justify-center mb-3`}>
                    <Icon size={20} className="text-white" strokeWidth={2.5} />
                  </div>
                  <p className="text-xs text-gray-500 mb-0.5">{m.label}</p>
                  <p className="text-xl font-bold text-gray-900 leading-tight">{m.value}</p>
                  <p className="text-xs text-gray-400 mt-0.5">{m.sub}</p>
                </Card>
              );
            })}

            {/* Live task status summary */}
            {metrics && (
              <>
                <Card>
                  <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-indigo-600 flex items-center justify-center mb-3">
                    <Activity size={20} className="text-white" strokeWidth={2.5} />
                  </div>
                  <p className="text-xs text-gray-500 mb-0.5">Tâches en cours</p>
                  <p className="text-xl font-bold text-gray-900">{metrics.assigned_tasks}</p>
                  <p className="text-xs text-gray-400 mt-0.5">prestataires actifs</p>
                </Card>
                <Card>
                  <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-500 to-orange-500 flex items-center justify-center mb-3">
                    <Clock size={20} className="text-white" strokeWidth={2.5} />
                  </div>
                  <p className="text-xs text-gray-500 mb-0.5">En validation</p>
                  <p className="text-xl font-bold text-gray-900">
                    {metrics.total_tasks - metrics.open_tasks - metrics.assigned_tasks - metrics.completed_tasks}
                  </p>
                  <p className="text-xs text-gray-400 mt-0.5">en attente de confirmation</p>
                </Card>
              </>
            )}
          </div>
        )}

        {/* Recent tasks */}
        <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3 px-1">Activité récente</h3>
        {loading ? (
          <div className="space-y-2">
            {[1, 2, 3].map((i) => <div key={i} className="h-16 bg-gray-200 rounded-2xl animate-pulse" />)}
          </div>
        ) : recentTasks.length === 0 ? (
          <div className="bg-gray-100 rounded-2xl p-6 text-center">
            <p className="text-sm text-gray-500">Aucune activité récente.</p>
          </div>
        ) : (
          <div className="space-y-2">
            {recentTasks.map((task) => (
              <Card key={task.id} className="hover:shadow-lg transition-all">
                <div className="flex items-center justify-between">
                  <div className="min-w-0 flex-1">
                    <h4 className="font-semibold text-gray-900 truncate">{task.title}</h4>
                    <p className="text-xs text-gray-500 mt-0.5">{formatDate(task.created_at)}</p>
                  </div>
                  <div className="flex items-center gap-2 ml-2 flex-shrink-0">
                    <span className="font-semibold text-gray-900 text-sm">
                      {task.currency} {Number(task.price).toLocaleString('fr-FR')}
                    </span>
                    <span className={`text-xs font-semibold px-2 py-1 rounded-lg ${statusClass(task.status)}`}>
                      {statusLabel(task.status)}
                    </span>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
