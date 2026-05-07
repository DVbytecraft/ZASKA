import { useEffect, useState } from 'react';
import { Button } from '../components/Button';
import { Card } from '../components/Card';
import { TaskProgressBar } from '../components/TaskProgressBar';
import { TaskStatusBadge } from '../components/TaskStatusBadge';
import { EscrowBadge } from '../components/EscrowBadge';
import { taskService, walletService } from '@zaska/shared-services';
import type { Task, Escrow } from '@zaska/shared-services';
import { ArrowLeft, MapPin, MessageCircle, Users, RefreshCw } from 'lucide-react';

interface TaskDetailScreenProps {
  taskId: string;
  onBack: () => void;
  onComplete: () => void;
  onChat: (taskerName?: string) => void;
  onViewApplicants?: () => void;
}

type ProgressStatus = 'posted' | 'applications' | 'in_progress' | 'completed' | 'paid';

function statusToProgressStatus(status: Task['status']): ProgressStatus {
  if (status === 'ASSIGNED') return 'in_progress';
  if (status === 'COMPLETED') return 'paid';
  return 'posted';
}

export function TaskDetailScreen({ taskId, onBack, onComplete, onChat, onViewApplicants }: TaskDetailScreenProps) {
  const [task, setTask] = useState<Task | null>(null);
  const [escrow, setEscrow] = useState<Escrow | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    if (!taskId) {
      setError('No task ID provided');
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);

    taskService
      .getTask(taskId)
      .then(async (t) => {
        setTask(t);
        try {
          const esc = await walletService.getEscrowForTask(taskId);
          setEscrow(esc);
        } catch {
          // Escrow may not exist yet for this task
        }
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : 'Failed to load task');
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [taskId]);

  if (loading) {
    return (
      <div className="h-full flex flex-col bg-gray-50">
        <div className="px-6 pt-8 pb-4 bg-white border-b border-gray-200">
          <div className="flex items-center gap-3">
            <button onClick={onBack} className="p-2 -ml-2 hover:bg-gray-100 rounded-full transition-colors">
              <ArrowLeft size={24} className="text-gray-700" />
            </button>
            <h2 className="text-2xl font-bold text-gray-900">Task details</h2>
          </div>
        </div>
        <div className="flex-1 px-6 py-4 space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-24 bg-gray-200 rounded-2xl animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  if (error || !task) {
    return (
      <div className="h-full flex flex-col bg-gray-50">
        <div className="px-6 pt-8 pb-4 bg-white border-b border-gray-200">
          <div className="flex items-center gap-3">
            <button onClick={onBack} className="p-2 -ml-2 hover:bg-gray-100 rounded-full transition-colors">
              <ArrowLeft size={24} className="text-gray-700" />
            </button>
            <h2 className="text-2xl font-bold text-gray-900">Task details</h2>
          </div>
        </div>
        <div className="flex-1 flex flex-col items-center justify-center px-6 gap-4">
          <p className="text-sm text-red-600 text-center">{error ?? 'Task not found'}</p>
          <button
            onClick={load}
            className="flex items-center gap-2 text-sm font-semibold text-[#6D28D9] hover:underline"
          >
            <RefreshCw size={16} /> Retry
          </button>
          <button onClick={onBack} className="text-sm text-gray-500 hover:underline">
            Go back
          </button>
        </div>
      </div>
    );
  }

  const progressStatus = statusToProgressStatus(task.status);
  const escrowStatus: 'held' | 'released' = escrow?.status === 'released' ? 'released' : 'held';
  const escrowAmount = escrow
    ? `${task.currency} ${parseFloat(escrow.amount).toFixed(2)}`
    : `${task.currency} ${task.price.toFixed(2)}`;

  return (
    <div className="h-full flex flex-col bg-gray-50">
      {/* Header */}
      <div className="px-6 pt-8 pb-4 bg-white border-b border-gray-200">
        <div className="flex items-center gap-3">
          <button onClick={onBack} className="p-2 -ml-2 hover:bg-gray-100 rounded-full transition-colors">
            <ArrowLeft size={24} className="text-gray-700" />
          </button>
          <div>
            <h2 className="text-2xl font-bold text-gray-900 mb-1">Task details</h2>
            <TaskStatusBadge
              status={
                progressStatus === 'paid' ? 'completed' :
                progressStatus === 'posted' ? 'posted' :
                progressStatus
              }
              size="md"
            />
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-auto px-6 py-4 space-y-3">
        {/* Progress bar */}
        <Card>
          <TaskProgressBar currentStatus={progressStatus} />
        </Card>

        {/* Task info */}
        <Card>
          <h3 className="text-lg font-semibold text-gray-900 mb-2">
            {task.title || task.description.slice(0, 60)}
          </h3>
          {task.title && (
            <p className="text-sm text-gray-600 mb-3">{task.description}</p>
          )}
          <div className="flex items-start gap-3 text-sm text-gray-500">
            <MapPin size={16} className="mt-0.5 flex-shrink-0" />
            <span>{task.latitude.toFixed(4)}, {task.longitude.toFixed(4)}</span>
          </div>
        </Card>

        {/* Applicants CTA — only for OPEN tasks */}
        {task.status === 'OPEN' && onViewApplicants && (
          <Card className="border-2 border-[#6D28D9]/20 bg-purple-50/50">
            <div className="flex items-center gap-3 mb-3">
              <div className="w-10 h-10 rounded-xl bg-[#6D28D9]/10 flex items-center justify-center">
                <Users size={20} className="text-[#6D28D9]" />
              </div>
              <div>
                <h4 className="font-semibold text-gray-900">Review applicants</h4>
                <p className="text-xs text-gray-500">Taskers who applied are waiting for your choice</p>
              </div>
            </div>
            <button
              onClick={onViewApplicants}
              className="w-full py-3 bg-[#6D28D9] text-white rounded-xl font-semibold text-sm hover:bg-[#5B21B6] transition-colors"
            >
              View applicants
            </button>
          </Card>
        )}

        {/* Assigned tasker — only for ASSIGNED tasks */}
        {task.status === 'ASSIGNED' && task.assignedTo && (
          <Card>
            <h4 className="font-semibold text-gray-900 mb-3 text-sm uppercase tracking-wide">Assigned Tasker</h4>
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-purple-100 flex items-center justify-center text-[#6D28D9] font-bold text-sm">
                {task.assignedTo.slice(0, 2).toUpperCase()}
              </div>
              <p className="text-sm text-gray-700 font-medium font-mono">
                {task.assignedTo.length > 20 ? task.assignedTo.slice(0, 20) + '…' : task.assignedTo}
              </p>
            </div>
            <button
              onClick={() => onChat(task.assignedTo ?? undefined)}
              className="w-full flex items-center justify-center gap-2 px-4 py-3 border-2 border-gray-200 rounded-xl hover:border-[#6D28D9] hover:text-[#6D28D9] transition-colors font-medium text-sm"
            >
              <MessageCircle size={18} />
              Chat with tasker
            </button>
          </Card>
        )}

        {/* Payment / Escrow */}
        <Card>
          <h4 className="font-semibold text-gray-900 mb-3 text-sm uppercase tracking-wide">Payment</h4>
          <div className="flex items-baseline justify-between mb-4">
            <span className="text-gray-600 text-sm">Total amount</span>
            <span className="text-2xl font-bold text-gray-900">
              {task.currency} {task.price.toFixed(2)}
            </span>
          </div>
          <EscrowBadge amount={escrowAmount} status={escrowStatus} />
          {task.status !== 'COMPLETED' && (
            <p className="text-xs text-gray-500 mt-3">
              Funds are held in escrow and will be released when you confirm completion.
            </p>
          )}
          {task.status === 'COMPLETED' && (
            <p className="text-xs text-green-600 mt-3 font-medium">
              Payment released to tasker.
            </p>
          )}
        </Card>
      </div>

      {/* Bottom CTA — only for ASSIGNED tasks (ready to complete) */}
      {task.status === 'ASSIGNED' && (
        <div className="px-6 py-4 bg-white border-t border-gray-200">
          <Button fullWidth onClick={onComplete}>
            Complete task
          </Button>
          <p className="text-xs text-gray-400 text-center mt-2">
            You'll confirm completion and release payment on the next screen
          </p>
        </div>
      )}
    </div>
  );
}
