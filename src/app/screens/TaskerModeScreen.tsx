import { useEffect, useState } from 'react';
import { Button } from '../components/Button';
import { Card } from '../components/Card';
import { MapPin, Clock, RefreshCw, AlertCircle, Loader2 } from 'lucide-react';
import { taskService, apiClient } from '@zaska/shared-services';
import type { Task } from '@zaska/shared-services';

interface TaskerModeScreenProps {
  onApply: (taskId: string) => void;
  onBack?: () => void;
}

export function TaskerModeScreen({ onApply, onBack }: TaskerModeScreenProps) {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const myId = apiClient.getUserId();

  const load = () => {
    setLoading(true);
    setError(null);
    taskService
      .browseAvailableTasks()
      .then((data) => {
        setTasks(data.filter((t) => t.createdBy !== myId));
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Impossible de charger les tâches'))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  return (
    <div className="h-full overflow-auto pb-24 bg-gray-50">
      <div className="px-6 pt-8 pb-8 bg-gradient-to-br from-[#1E40AF] to-[#1E3A8A]">
        <div className="flex items-center justify-between mb-2">
          <div>
            <h1 className="text-2xl font-bold text-white">Tâches disponibles</h1>
            <p className="text-white/75 text-sm">Postule et commence à gagner</p>
          </div>
          <button
            onClick={load}
            className="w-10 h-10 rounded-full bg-white/15 hover:bg-white/25 flex items-center justify-center transition-colors border border-white/10"
          >
            <RefreshCw size={16} className="text-white" />
          </button>
        </div>
      </div>

      <div className="px-6 py-4 space-y-3">
        {loading && (
          <div className="flex items-center justify-center h-48">
            <Loader2 size={32} className="animate-spin text-blue-600" />
          </div>
        )}

        {error && !loading && (
          <div className="flex flex-col items-center justify-center h-48 gap-3">
            <AlertCircle size={36} className="text-red-400" />
            <p className="text-sm text-red-600 text-center">{error}</p>
            <button onClick={load} className="text-sm font-semibold text-blue-700 hover:underline flex items-center gap-1">
              <RefreshCw size={14} /> Réessayer
            </button>
          </div>
        )}

        {!loading && !error && tasks.length === 0 && (
          <div className="flex flex-col items-center justify-center h-48 gap-3 text-gray-400">
            <Clock size={40} className="text-gray-300" />
            <p className="text-sm font-medium text-center">Aucune tâche disponible pour le moment</p>
            <p className="text-xs text-gray-400 text-center">Reviens plus tard ou active les notifications</p>
          </div>
        )}

        {!loading && !error && tasks.map((task) => (
          <Card key={task.id} className="hover:shadow-lg transition-all">
            <div className="flex items-start justify-between mb-3">
              <h3 className="text-base font-semibold text-gray-900 flex-1">
                {task.title || task.description?.slice(0, 50)}
              </h3>
            </div>

            <div className="flex items-center gap-4 mb-4 text-sm text-gray-500">
              {task.address && (
                <div className="flex items-center gap-1.5">
                  <MapPin size={14} strokeWidth={2.5} />
                  <span className="truncate max-w-[140px]">{task.address}</span>
                </div>
              )}
              {task.createdAt && (
                <div className="flex items-center gap-1.5">
                  <Clock size={14} strokeWidth={2.5} />
                  <span>{new Date(task.createdAt).toLocaleDateString('fr-FR')}</span>
                </div>
              )}
            </div>

            <div className="flex items-center justify-between">
              <div>
                <div className="flex items-baseline gap-1.5">
                  <span className="text-2xl font-bold text-gray-900">
                    {Number(task.price).toLocaleString()}
                  </span>
                  <span className="text-sm text-gray-500">{task.currency}</span>
                </div>
                <p className="text-xs text-gray-400 mt-0.5">Budget ou propose ton prix</p>
              </div>
              <Button size="md" onClick={() => onApply(task.id)}>
                Postuler
              </Button>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
