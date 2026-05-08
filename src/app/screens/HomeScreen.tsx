import { useCallback, useEffect, useState } from 'react';
import { Button } from '../components/Button';
import { Card } from '../components/Card';
import { taskService } from '@zaska/shared-services';
import type { Task } from '@zaska/shared-services';
import { Sparkles, Package, FileText, Users, CheckCircle2, Activity, Search, Bell } from 'lucide-react';

interface HomeScreenProps {
  onPostTask: () => void;
  onViewApplicants?: (taskId: string) => void;
  onTaskDetail?: (taskId: string) => void;
  onCategories?: () => void;
  onSearch?: () => void;
  onNotifications?: () => void;
}

const CATEGORIES = [
  { id: 1, name: 'Ménage', icon: Sparkles, gradient: 'from-purple-500 to-purple-600' },
  { id: 2, name: 'Livraison', icon: Package, gradient: 'from-blue-500 to-blue-600' },
  { id: 3, name: 'Assistant', icon: FileText, gradient: 'from-green-500 to-green-600' },
  { id: 4, name: 'Personnel', icon: Users, gradient: 'from-pink-500 to-pink-600' },
];

function statusLabel(status: Task['status']) {
  if (status === 'COMPLETED') return 'Terminé';
  if (status === 'ASSIGNED') return 'En cours';
  return 'Ouvert';
}

function statusClass(status: Task['status']) {
  if (status === 'COMPLETED') return 'bg-green-50 text-green-700';
  if (status === 'ASSIGNED') return 'bg-blue-50 text-blue-700';
  return 'bg-purple-50 text-purple-700';
}

function statusIconClass(status: Task['status']) {
  if (status === 'COMPLETED') return 'bg-green-50';
  if (status === 'ASSIGNED') return 'bg-blue-50';
  return 'bg-purple-50';
}

function formatAmount(price: number, currency: string) {
  return `${currency} ${price.toFixed(2)}`;
}

export function HomeScreen({
  onPostTask,
  onViewApplicants,
  onTaskDetail,
  onCategories,
  onSearch,
  onNotifications,
}: HomeScreenProps) {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    taskService
      .listMyTasks()
      .then(setTasks)
      .catch((err) => setError(err instanceof Error ? err.message : 'Erreur de chargement'))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  const recentTasks = tasks.slice(0, 10);

  return (
    <div className="h-full overflow-auto pb-24 bg-gray-50">
      <div className="px-6 pt-8 pb-8 bg-gradient-to-br from-[#6D28D9] to-[#5B21B6]">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-white">Que faut-il faire ?</h1>
          </div>
          <div className="flex items-center gap-2">
            {onSearch && (
              <button
                onClick={onSearch}
                className="w-10 h-10 rounded-full bg-white/15 hover:bg-white/25 backdrop-blur-sm flex items-center justify-center transition-colors border border-white/10"
              >
                <Search size={20} className="text-white" />
              </button>
            )}
            {onNotifications && (
              <button
                onClick={onNotifications}
                className="w-10 h-10 rounded-full bg-white/15 hover:bg-white/25 backdrop-blur-sm flex items-center justify-center transition-colors border border-white/10 relative"
              >
                <Bell size={20} className="text-white" />
                <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-red-500 rounded-full border border-white"></span>
              </button>
            )}
          </div>
        </div>

        <Button fullWidth onClick={onPostTask}>
          Poster une tâche
        </Button>
      </div>

      <div className="px-6 pt-4">
        <div className="flex items-center justify-between mb-3 px-1">
          <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Catégories populaires</h3>
          {onCategories && (
            <button onClick={onCategories} className="text-xs font-semibold text-[#6D28D9] hover:text-[#5B21B6]">
              Voir tout
            </button>
          )}
        </div>
        <div className="grid grid-cols-2 gap-3">
          {CATEGORIES.map((category) => {
            const Icon = category.icon;
            return (
              <Card key={category.id} onClick={onCategories} className="hover:shadow-lg transition-all active:scale-[0.98]">
                <div className="flex flex-col items-center py-5">
                  <div className={`w-14 h-14 rounded-2xl bg-gradient-to-br ${category.gradient} flex items-center justify-center mb-3 shadow-lg`}>
                    <Icon size={26} className="text-white" strokeWidth={2.5} />
                  </div>
                  <span className="font-semibold text-gray-900 text-sm">{category.name}</span>
                </div>
              </Card>
            );
          })}
        </div>
      </div>

      <div className="px-6 mt-6 pb-6">
        <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3 px-1">Activité récente</h3>

        {loading && (
          <div className="space-y-2">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-20 bg-gray-200 rounded-2xl animate-pulse" />
            ))}
          </div>
        )}

        {error && !loading && (
          <div className="bg-red-50 border border-red-100 rounded-2xl p-4 text-center">
            <p className="text-sm text-red-600">Impossible de charger l'activité</p>
            <button
              onClick={load}
              className="mt-2 text-xs text-red-700 font-semibold underline"
            >
              Réessayer
            </button>
          </div>
        )}

        {!loading && !error && recentTasks.length === 0 && (
          <div className="bg-gray-100 rounded-2xl p-8 text-center">
            <p className="text-sm text-gray-500">Aucune activité. Publiez votre première tâche !</p>
          </div>
        )}

        {!loading && !error && (
          <div className="space-y-2">
            {recentTasks.map((task) => (
              <Card
                key={task.id}
                className="hover:shadow-lg transition-all cursor-pointer"
                onClick={() => onTaskDetail?.(task.id)}
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-3">
                    <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${statusIconClass(task.status)}`}>
                      {task.status === 'COMPLETED' ? (
                        <CheckCircle2 size={18} className="text-green-600" strokeWidth={2.5} />
                      ) : task.status === 'ASSIGNED' ? (
                        <Activity size={18} className="text-blue-600" strokeWidth={2.5} />
                      ) : (
                        <Users size={18} className="text-purple-600" strokeWidth={2.5} />
                      )}
                    </div>
                    <div>
                      <p className="font-medium text-gray-900 truncate max-w-[160px]">
                        {task.title || task.description.slice(0, 40)}
                      </p>
                      <p className="text-xs text-gray-500">{formatAmount(task.price, task.currency)}</p>
                    </div>
                  </div>
                  <span className={`text-xs font-semibold px-2.5 py-1 rounded-lg ${statusClass(task.status)}`}>
                    {statusLabel(task.status)}
                  </span>
                </div>
                {task.status === 'OPEN' && onViewApplicants && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onViewApplicants(task.id);
                    }}
                    className="w-full mt-2 px-4 py-2 bg-[#6D28D9] text-white rounded-lg font-medium text-sm hover:bg-[#5B21B6] transition-colors"
                  >
                    Voir les candidatures
                  </button>
                )}
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
