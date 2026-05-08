import { useEffect, useState } from 'react';
import { Card } from '../components/Card';
import { Button } from '../components/Button';
import { CheckCircle2, Activity, Clock, AlertCircle, RefreshCw, Users } from 'lucide-react';
import { taskService } from '@zaska/shared-services';
import type { Task } from '@zaska/shared-services';

interface TasksTabScreenProps {
  onTaskClick: (taskId: string) => void;
  onViewApplicants?: (taskId: string) => void;
  onPostTask?: () => void;
}

export function TasksTabScreen({ onTaskClick, onViewApplicants, onPostTask }: TasksTabScreenProps) {
  const [filter, setFilter] = useState<'all' | 'active' | 'completed'>('all');
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    setLoading(true);
    setError(null);
    taskService.listMyTasks()
      .then(setTasks)
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load tasks'))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const filteredTasks = tasks.filter((task) => {
    if (filter === 'active') return task.status !== 'COMPLETED';
    if (filter === 'completed') return task.status === 'COMPLETED';
    return true;
  });

  return (
    <div className="h-full overflow-auto pb-24 bg-gray-50">
      <div className="px-6 pt-8 pb-6 bg-gradient-to-br from-[#6D28D9] to-[#5B21B6]">
        <div className="flex items-center justify-between mb-4">
          <h1 className="text-2xl font-bold text-white">My Tasks</h1>
          <button
            onClick={load}
            className="w-9 h-9 rounded-full bg-white/15 hover:bg-white/25 flex items-center justify-center transition-colors border border-white/10"
          >
            <RefreshCw size={16} className="text-white" />
          </button>
        </div>
        {onPostTask && <Button fullWidth onClick={onPostTask}>Post a new task</Button>}
      </div>

      <div className="px-6 py-4">
        <div className="flex gap-2 mb-4">
          {(['all', 'active', 'completed'] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                filter === f ? 'bg-[#6D28D9] text-white' : 'bg-white text-gray-700 border border-gray-200'
              }`}
            >
              {f === 'all' ? 'All' : f === 'active' ? 'Active' : 'Completed'}
            </button>
          ))}
        </div>

        {loading ? (
          <div className="space-y-3">
            {[1, 2, 3].map((i) => <div key={i} className="h-24 bg-gray-200 rounded-2xl animate-pulse" />)}
          </div>
        ) : error ? (
          <div className="flex flex-col items-center justify-center h-48 gap-3">
            <AlertCircle size={40} className="text-red-400" />
            <p className="text-sm text-red-600 text-center">{error}</p>
            <button onClick={load} className="flex items-center gap-2 text-sm font-medium text-[#6D28D9] hover:underline">
              <RefreshCw size={16} /> Retry
            </button>
          </div>
        ) : filteredTasks.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-48 gap-3">
            <Clock size={40} className="text-gray-200" />
            <p className="text-sm text-gray-400 text-center">No tasks yet.</p>
            {onPostTask && (
              <button onClick={onPostTask} className="text-sm font-semibold text-[#6D28D9] hover:underline">
                Post your first task
              </button>
            )}
          </div>
        ) : (
          <div className="space-y-3">
            {filteredTasks.map((task) => (
              <Card key={task.id} onClick={() => onTaskClick(task.id)} className="hover:shadow-lg transition-all cursor-pointer">
                <div className="flex items-start justify-between mb-2">
                  <div className="flex items-center gap-3">
                    <div className={`w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 ${
                      task.status === 'COMPLETED' ? 'bg-green-50' :
                      task.status === 'ASSIGNED' ? 'bg-blue-50' : 'bg-purple-50'
                    }`}>
                      {task.status === 'COMPLETED' ? (
                        <CheckCircle2 size={20} className="text-green-600" />
                      ) : task.status === 'ASSIGNED' ? (
                        <Activity size={20} className="text-blue-600" />
                      ) : (
                        <Clock size={20} className="text-purple-600" />
                      )}
                    </div>
                    <div className="min-w-0">
                      <p className="font-medium text-gray-900 truncate max-w-[160px]">
                        {task.title || task.description.slice(0, 40)}
                      </p>
                      <p className="text-xs text-gray-500">
                        {Number(task.price).toLocaleString()} {task.currency}
                      </p>
                    </div>
                  </div>
                  <span className={`text-xs font-semibold px-2.5 py-1 rounded-lg flex-shrink-0 ${
                    task.status === 'COMPLETED' ? 'bg-green-50 text-green-700' :
                    task.status === 'ASSIGNED' ? 'bg-blue-50 text-blue-700' :
                    'bg-purple-50 text-purple-700'
                  }`}>
                    {task.status === 'COMPLETED' ? 'Done' :
                     task.status === 'ASSIGNED' ? 'Active' : 'Open'}
                  </span>
                </div>

                {/* View applicants button for OPEN tasks */}
                {task.status === 'OPEN' && onViewApplicants && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onViewApplicants(task.id);
                    }}
                    className="w-full mt-2 flex items-center justify-center gap-2 px-4 py-2.5 bg-[#6D28D9] text-white rounded-lg font-medium text-sm hover:bg-[#5B21B6] transition-colors"
                  >
                    <Users size={16} />
                    View applicants
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
