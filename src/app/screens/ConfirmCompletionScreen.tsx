import { useEffect, useState } from 'react';
import { Button } from '../components/Button';
import { Card } from '../components/Card';
import { EscrowBadge } from '../components/EscrowBadge';
import { taskService, walletService } from '@zaska/shared-services';
import type { Task, Escrow } from '@zaska/shared-services';
import { ArrowLeft, CheckCircle2, AlertCircle, Shield, Loader2 } from 'lucide-react';

interface ConfirmCompletionScreenProps {
  taskId: string;
  onBack: () => void;
  onSuccess: () => void;
  onReportIssue: () => void;
}

export function ConfirmCompletionScreen({ taskId, onBack, onSuccess, onReportIssue }: ConfirmCompletionScreenProps) {
  const [task, setTask] = useState<Task | null>(null);
  const [escrow, setEscrow] = useState<Escrow | null>(null);
  const [loadingData, setLoadingData] = useState(true);
  const [completing, setCompleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [otp, setOtp] = useState(['', '', '', '']);
  const [useOtp, setUseOtp] = useState(false);

  useEffect(() => {
    if (!taskId) {
      setLoadingData(false);
      return;
    }
    let cancelled = false;
    setLoadingData(true);
    setError(null);

    Promise.all([
      taskService.getTask(taskId),
      walletService.getEscrowForTask(taskId).catch(() => null),
    ])
      .then(([t, esc]) => {
        if (cancelled) return;
        setTask(t);
        setEscrow(esc);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to load task details');
      })
      .finally(() => {
        if (!cancelled) setLoadingData(false);
      });

    return () => { cancelled = true; };
  }, [taskId]);

  const handleConfirm = async () => {
    if (!task) return;
    setCompleting(true);
    setError(null);
    try {
      await taskService.updateTaskStatus(task.id, 'COMPLETED');
      if (escrow?.escrow_id) {
        await walletService.releaseEscrow(escrow.escrow_id);
      }
      onSuccess();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to complete task. Please try again.');
    } finally {
      setCompleting(false);
    }
  };

  const handleOtpChange = (index: number, value: string) => {
    if (value.length <= 1 && /^\d*$/.test(value)) {
      const newOtp = [...otp];
      newOtp[index] = value;
      setOtp(newOtp);
      if (value && index < 3) {
        document.getElementById(`otp-completion-${index + 1}`)?.focus();
      }
    }
  };

  const escrowAmount = escrow
    ? `${task?.currency ?? ''} ${parseFloat(escrow.amount).toFixed(2)}`
    : task
    ? `${task.currency} ${task.price.toFixed(2)}`
    : '—';

  const isOtpComplete = otp.every((d) => d !== '');
  const canConfirm = !completing && (!useOtp || isOtpComplete);

  return (
    <div className="h-full flex flex-col bg-gray-50">
      <div className="px-6 pt-8 pb-4 bg-white border-b border-gray-200">
        <div className="flex items-center gap-3">
          <button
            onClick={onBack}
            className="p-2 -ml-2 hover:bg-gray-100 rounded-full transition-colors"
            disabled={completing}
          >
            <ArrowLeft size={24} className="text-gray-700" />
          </button>
          <h2 className="text-2xl font-bold text-gray-900">Confirm completion</h2>
        </div>
      </div>

      <div className="flex-1 overflow-auto px-6 py-6 flex flex-col gap-4">
        {loadingData ? (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center">
              <Loader2 size={36} className="text-[#6D28D9] animate-spin mx-auto mb-3" />
              <p className="text-sm text-gray-500">Loading task details…</p>
            </div>
          </div>
        ) : (
          <>
            {/* Task + amount summary */}
            <Card>
              <div className="flex items-center gap-3 mb-4">
                <div className="w-12 h-12 rounded-xl bg-green-50 flex items-center justify-center flex-shrink-0">
                  <CheckCircle2 size={24} className="text-green-600" strokeWidth={2.5} />
                </div>
                <div className="flex-1 min-w-0">
                  <h3 className="font-semibold text-gray-900">Mark as completed</h3>
                  {task?.assignedTo && (
                    <p className="text-sm text-gray-500 truncate">
                      Tasker: {task.assignedTo.length > 16 ? task.assignedTo.slice(0, 16) + '…' : task.assignedTo}
                    </p>
                  )}
                </div>
              </div>

              <div className="bg-gray-50 rounded-xl p-4">
                {task && (
                  <p className="text-sm font-medium text-gray-700 mb-3 line-clamp-2">
                    {task.title || task.description.slice(0, 80)}
                  </p>
                )}
                <div className="flex items-baseline justify-between">
                  <span className="text-sm text-gray-500">Amount to release</span>
                  <span className="text-2xl font-bold text-gray-900">{escrowAmount}</span>
                </div>
                {escrow && (
                  <p className="text-xs text-gray-400 mt-1 text-right">
                    Escrow #{escrow.escrow_id.slice(0, 8)}…
                  </p>
                )}
              </div>
            </Card>

            {/* Optional OTP section */}
            {useOtp && (
              <Card>
                <h4 className="font-semibold text-gray-900 mb-1">Completion code</h4>
                <p className="text-sm text-gray-500 mb-4">Ask the tasker for their 4-digit code</p>
                <div className="flex gap-3 justify-center">
                  {otp.map((digit, index) => (
                    <input
                      key={index}
                      id={`otp-completion-${index}`}
                      type="text"
                      inputMode="numeric"
                      maxLength={1}
                      value={digit}
                      onChange={(e) => handleOtpChange(index, e.target.value)}
                      className="w-14 h-14 text-center text-2xl font-bold border-2 border-gray-200 rounded-xl focus:border-[#6D28D9] focus:outline-none focus:ring-4 focus:ring-[#6D28D9]/10 transition-all"
                    />
                  ))}
                </div>
              </Card>
            )}

            {/* Escrow protection info */}
            <Card>
              <div className="flex items-start gap-3 mb-3">
                <div className="w-10 h-10 rounded-xl bg-blue-50 flex items-center justify-center flex-shrink-0">
                  <Shield size={20} className="text-blue-600" />
                </div>
                <div>
                  <h4 className="font-semibold text-gray-900 mb-1">Escrow protection</h4>
                  <p className="text-sm text-gray-600">
                    Confirming releases secured funds to the tasker immediately and cannot be undone.
                  </p>
                </div>
              </div>
              <EscrowBadge amount={escrowAmount} status="held" />
            </Card>

            {/* Error banner */}
            {error && (
              <div className="bg-red-50 border border-red-100 rounded-xl p-3 flex items-start gap-2">
                <AlertCircle size={16} className="text-red-500 flex-shrink-0 mt-0.5" />
                <p className="text-sm text-red-600">{error}</p>
              </div>
            )}

            {/* Actions */}
            <div className="space-y-3 pt-2">
              {!useOtp && (
                <button
                  onClick={() => setUseOtp(true)}
                  className="w-full text-[#6D28D9] font-medium text-sm hover:underline"
                >
                  Use completion code instead
                </button>
              )}

              <Button fullWidth onClick={handleConfirm} disabled={!canConfirm}>
                {completing ? (
                  <span className="flex items-center justify-center gap-2">
                    <Loader2 size={16} className="animate-spin" />
                    Releasing payment…
                  </span>
                ) : (
                  'Confirm & release payment'
                )}
              </Button>

              <button
                onClick={onReportIssue}
                disabled={completing}
                className="w-full px-6 py-3.5 border-2 border-red-200 rounded-xl font-semibold text-red-600 hover:bg-red-50 transition-all flex items-center justify-center gap-2 disabled:opacity-50"
              >
                <AlertCircle size={18} />
                Report an issue
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
