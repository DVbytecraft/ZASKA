import { useEffect, useState } from 'react';
import { ArrowLeft, Package, Clock, CheckCircle2, XCircle, AlertCircle, RefreshCw } from 'lucide-react';
import { Card } from '../components/Card';
import { taskService } from '@zaska/shared-services';
import type { Task } from '@zaska/shared-services';

interface TaskHistoryScreenProps {
  onBack: () => void;
  onTaskDetails: (taskId: string) => void;
}

function StatusBadge({ status }: { status: string }) {
  if (status === 'COMPLETED') {
    return (
      <div className="flex items-center gap-1 text-green-700">
        <CheckCircle2 size={16} />
        <span className="text-sm font-medium">Completed</span>
      </div>
    );
  }
  if (status === 'CANCELLED') {
    return (
      <div className="flex items-center gap-1 text-red-700">
        <XCircle size={16} />
        <span className="text-sm font-medium">Cancelled</span>
      </div>
    );
  }
  return (
    <div className="flex items-center gap-1 text-orange-700">
      <Clock size={16} />
      <span className="text-sm font-medium">In Progress</span>
    </div>
  );
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
  } catch {
    return iso;
  }
}

export function TaskHistoryScreen({ onBack, onTaskDetails }: TaskHistoryScreenProps) {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    setLoading(true);
    setError(null);
    taskService.listTasks()
      .then((all) => setTasks(all.filter((t) => t.status === 'COMPLETED' || (t.status as string) === 'CANCELLED')))
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load task history'))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  return (
    <div className="h-full flex flex-col bg-gray-50">
      <div className="px-6 pt-8 pb-4 bg-white border-b border-gray-200">
        <div className="flex items-center gap-3">
          <button onClick={onBack} className="p-2 -ml-2 hover:bg-gray-100 rounded-full transition-colors" aria-label="Go back">
            <ArrowLeft size={24} className="text-gray-700" />
          </button>
          <h2 className="text-2xl font-bold text-gray-900">Task History</h2>
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
              <RefreshCw size={16} /> Retry
            </button>
          </div>
        ) : tasks.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-48 text-gray-400">
            <Package size={40} className="mb-3 text-gray-200" />
            <p className="text-sm">No completed tasks yet.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {tasks.map((task) => (
              <Card key={task.id} onClick={() => onTaskDetails(task.id)} className="hover:shadow-md transition-all cursor-pointer">
                <div className="flex items-start gap-4">
                  <div className="w-12 h-12 rounded-xl bg-purple-50 flex items-center justify-center flex-shrink-0">
                    <Package size={24} className="text-[#6D28D9]" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between gap-2 mb-1">
                      <h4 className="font-semibold text-gray-900 truncate">{task.title}</h4>
                      <StatusBadge status={task.status} />
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-gray-500">
                        {task.createdAt ? formatDate(task.createdAt as unknown as string) : ''}
                      </span>
                      <span className="font-semibold text-gray-900">
                        {Number(task.price).toLocaleString()} {task.currency}
                      </span>
                    </div>
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
