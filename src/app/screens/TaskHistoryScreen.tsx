import { useEffect, useState } from 'react';
import { ArrowLeft, Package, Clock, CheckCircle2, Activity, AlertCircle, RefreshCw } from 'lucide-react';
import { Card } from '../components/Card';
import { taskService } from '@zaska/shared-services';
import type { Task } from '@zaska/shared-services';

interface TaskHistoryScreenProps {
  onBack: () => void;
  onTaskDetails: (taskId: string) => void;
}

type Tab = 'active' | 'completed';

function StatusBadge({ status }: { status: string }) {
  if (status === 'COMPLETED') {
    return (
      <div className="flex items-center gap-1 text-green-700 bg-green-50 px-2 py-0.5 rounded-lg">
        <CheckCircle2 size={14} />
        <span className="text-xs font-semibold">Terminée</span>
      </div>
    );
  }
  if (status === 'ASSIGNED') {
    return (
      <div className="flex items-center gap-1 text-blue-700 bg-blue-50 px-2 py-0.5 rounded-lg">
        <Activity size={14} />
        <span className="text-xs font-semibold">En cours</span>
      </div>
    );
  }
  if (status === 'PENDING_VALIDATION') {
    return (
      <div className="flex items-center gap-1 text-amber-700 bg-amber-50 px-2 py-0.5 rounded-lg">
        <Clock size={14} />
        <span className="text-xs font-semibold">En validation</span>
      </div>
    );
  }
  return (
    <div className="flex items-center gap-1 text-gray-600 bg-gray-100 px-2 py-0.5 rounded-lg">
      <Clock size={14} />
      <span className="text-xs font-semibold">Autre</span>
    </div>
  );
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString('fr-FR', { year: 'numeric', month: 'short', day: 'numeric' });
  } catch {
    return iso;
  }
}

export function TaskHistoryScreen({ onBack, onTaskDetails }: TaskHistoryScreenProps) {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>('active');

  const load = () => {
    setLoading(true);
    setError(null);
    taskService
      .listMyTasks()
      .then(setTasks)
      .catch((err) => setError(err instanceof Error ? err.message : 'Impossible de charger l\'historique'))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const activeTasks = tasks.filter((t) => t.status === 'ASSIGNED' || t.status === 'PENDING_VALIDATION');
  const completedTasks = tasks.filter((t) => t.status === 'COMPLETED' || (t.status as string) === 'CANCELLED');
  const displayed = tab === 'active' ? activeTasks : completedTasks;

  return (
    <div className="h-full flex flex-col bg-gray-50">
      <div className="px-6 pt-8 pb-4 bg-white border-b border-gray-200">
        <div className="flex items-center gap-3 mb-4">
          <button onClick={onBack} className="p-2 -ml-2 hover:bg-gray-100 rounded-full transition-colors">
            <ArrowLeft size={24} className="text-gray-700" />
          </button>
          <h2 className="text-2xl font-bold text-gray-900">Mes tâches</h2>
        </div>
        {/* Tabs */}
        <div className="flex gap-1 bg-gray-100 rounded-xl p-1">
          <button
            onClick={() => setTab('active')}
            className={`flex-1 py-2 rounded-lg text-sm font-semibold transition-all ${
              tab === 'active' ? 'bg-white text-[#6D28D9] shadow-sm' : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            En cours {activeTasks.length > 0 && `(${activeTasks.length})`}
          </button>
          <button
            onClick={() => setTab('completed')}
            className={`flex-1 py-2 rounded-lg text-sm font-semibold transition-all ${
              tab === 'completed' ? 'bg-white text-[#6D28D9] shadow-sm' : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            Terminées {completedTasks.length > 0 && `(${completedTasks.length})`}
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-auto p-6">
        {loading ? (
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-24 bg-gray-200 rounded-2xl animate-pulse" />
            ))}
          </div>
        ) : error ? (
          <div className="flex flex-col items-center justify-center h-48 gap-3">
            <AlertCircle size={40} className="text-red-400" />
            <p className="text-sm text-red-600 text-center">{error}</p>
            <button onClick={load} className="flex items-center gap-2 text-sm font-medium text-[#6D28D9] hover:underline">
              <RefreshCw size={16} /> Réessayer
            </button>
          </div>
        ) : displayed.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-48 text-gray-400">
            <Package size={40} className="mb-3 text-gray-200" />
            <p className="text-sm font-medium text-gray-500">
              {tab === 'active' ? 'Aucune tâche en cours.' : 'Aucune tâche terminée.'}
            </p>
            <p className="text-xs text-gray-400 mt-1">
              {tab === 'active'
                ? 'Les tâches acceptées par un prestataire apparaîtront ici.'
                : 'Les tâches complétées seront archivées ici.'}
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {displayed.map((task) => (
              <Card key={task.id} onClick={() => onTaskDetails(task.id)} className="hover:shadow-md transition-all cursor-pointer">
                <div className="flex items-start gap-4">
                  <div className={`w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0 ${
                    task.status === 'ASSIGNED' ? 'bg-blue-50' :
                    task.status === 'PENDING_VALIDATION' ? 'bg-amber-50' :
                    'bg-purple-50'
                  }`}>
                    <Package size={24} className={
                      task.status === 'ASSIGNED' ? 'text-blue-600' :
                      task.status === 'PENDING_VALIDATION' ? 'text-amber-600' :
                      'text-[#6D28D9]'
                    } />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between gap-2 mb-1">
                      <h4 className="font-semibold text-gray-900 truncate">{task.title || task.description.slice(0, 40)}</h4>
                      <StatusBadge status={task.status} />
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-gray-500">
                        {task.createdAt ? formatDate(task.createdAt as unknown as string) : ''}
                      </span>
                      <span className="font-semibold text-gray-900">
                        {Number(task.price).toLocaleString('fr-FR')} {task.currency}
                      </span>
                    </div>
                    {task.negotiationStatus && task.negotiationStatus !== 'none' && task.negotiatedPrice && (
                      <p className="text-xs text-amber-600 mt-1">
                        Prix négocié : {task.currency} {Number(task.negotiatedPrice).toFixed(2)}
                      </p>
                    )}
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
