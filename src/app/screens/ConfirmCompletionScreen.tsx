import { useEffect, useState } from 'react';
import { Button } from '../components/Button';
import { Card } from '../components/Card';
import { EscrowBadge } from '../components/EscrowBadge';
import { taskService, walletService, apiClient } from '@zaska/shared-services';
import type { Task, Escrow } from '@zaska/shared-services';
import { ArrowLeft, CheckCircle2, AlertCircle, Shield, Loader2, Clock, Mail } from 'lucide-react';

interface ConfirmCompletionScreenProps {
  taskId: string;
  onBack: () => void;
  onSuccess: () => void;
  onReportIssue: () => void;
}

type Step = 'idle' | 'code_sent' | 'code_entry' | 'hold_24h' | 'done';

export function ConfirmCompletionScreen({ taskId, onBack, onSuccess, onReportIssue }: ConfirmCompletionScreenProps) {
  const [task, setTask] = useState<Task | null>(null);
  const [escrow, setEscrow] = useState<Escrow | null>(null);
  const [loadingData, setLoadingData] = useState(true);
  const [step, setStep] = useState<Step>('idle');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [code, setCode] = useState(['', '', '', '', '', '']);
  const [completionPct, setCompletionPct] = useState(100);
  const [bothValidated, setBothValidated] = useState(false);

  useEffect(() => {
    if (!taskId) { setLoadingData(false); return; }
    let cancelled = false;
    setLoadingData(true);
    setError(null);
    Promise.all([
      taskService.getTask(taskId),
      walletService.getEscrowForTask(taskId).catch(() => null),
    ])
      .then(([t, esc]) => { if (!cancelled) { setTask(t); setEscrow(esc); } })
      .catch((err) => { if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to load'); })
      .finally(() => { if (!cancelled) setLoadingData(false); });
    return () => { cancelled = true; };
  }, [taskId]);

  const handleMarkComplete = async () => {
    if (!task) return;
    setSubmitting(true);
    setError(null);
    try {
      await apiClient.post(`/tasks/${task.id}/complete`, { completion_percent: completionPct });
      setStep('code_sent');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to mark task complete');
    } finally {
      setSubmitting(false);
    }
  };

  const handleSubmitCode = async () => {
    if (!task) return;
    const fullCode = code.join('').trim().toUpperCase();
    if (fullCode.length < 4) { setError('Entrez votre code complet.'); return; }
    setSubmitting(true);
    setError(null);
    try {
      const res = await apiClient.post<{
        both_validated: boolean;
        completion_percent?: number;
        message: string;
        payout_available_in_hours?: number;
      }>(`/tasks/${task.id}/finalize`, { code: fullCode });
      if (res.both_validated) {
        setBothValidated(true);
        if (res.payout_available_in_hours) {
          setStep('hold_24h');
        } else {
          setStep('done');
          setTimeout(onSuccess, 1500);
        }
      } else {
        setStep('code_entry');
        setError('Votre code est validé. En attente du code de l\'autre partie.');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Code incorrect');
    } finally {
      setSubmitting(false);
    }
  };

  const handleCodeChange = (index: number, value: string) => {
    const v = value.toUpperCase().replace(/[^A-Z0-9]/g, '');
    if (v.length <= 1) {
      const next = [...code];
      next[index] = v;
      setCode(next);
      if (v && index < 5) document.getElementById(`fc-${index + 1}`)?.focus();
    }
  };

  const escrowAmount = escrow
    ? `${task?.currency ?? ''} ${parseFloat(escrow.amount).toFixed(2)}`
    : task
    ? `${task.currency} ${task.price.toFixed(2)}`
    : '—';

  const codeComplete = code.every(d => d !== '');

  return (
    <div className="h-full flex flex-col bg-gray-50">
      <div className="px-6 pt-8 pb-4 bg-white border-b border-gray-200">
        <div className="flex items-center gap-3">
          <button onClick={onBack} className="p-2 -ml-2 hover:bg-gray-100 rounded-full transition-colors" disabled={submitting}>
            <ArrowLeft size={24} className="text-gray-700" />
          </button>
          <h2 className="text-2xl font-bold text-gray-900">Confirm completion</h2>
        </div>
      </div>

      <div className="flex-1 overflow-auto px-6 py-6 flex flex-col gap-4">
        {loadingData ? (
          <div className="flex-1 flex items-center justify-center">
            <Loader2 size={36} className="text-[#6D28D9] animate-spin" />
          </div>
        ) : step === 'done' ? (
          <div className="flex-1 flex flex-col items-center justify-center gap-4">
            <CheckCircle2 size={64} className="text-green-500" />
            <h3 className="text-xl font-bold text-gray-900">Task finalized!</h3>
            <p className="text-sm text-gray-500 text-center">Payment has been processed successfully.</p>
          </div>
        ) : step === 'hold_24h' ? (
          <Card>
            <div className="flex items-start gap-3">
              <Clock size={24} className="text-amber-500 flex-shrink-0 mt-1" />
              <div>
                <h3 className="font-bold text-gray-900 mb-1">Payment on hold — 24h window</h3>
                <p className="text-sm text-gray-600 mb-3">
                  Both codes have been validated. The payment ({escrowAmount}) is on hold for 24 hours.
                  If no dispute is raised, it will be released automatically to the tasker.
                </p>
                <p className="text-xs text-gray-400">You can raise a dispute within this window if you're unsatisfied with the work.</p>
              </div>
            </div>
            <div className="mt-4 flex gap-3">
              <Button fullWidth onClick={onSuccess}>Go back to tasks</Button>
              <button onClick={onReportIssue} className="flex-1 px-4 py-3 border-2 border-red-200 rounded-xl text-red-600 font-semibold hover:bg-red-50 transition-all text-sm">
                Raise dispute
              </button>
            </div>
          </Card>
        ) : step === 'code_sent' || step === 'code_entry' ? (
          <>
            <Card>
              <div className="flex items-start gap-3 mb-4">
                <Mail size={20} className="text-[#6D28D9] flex-shrink-0 mt-0.5" />
                <div>
                  <h3 className="font-semibold text-gray-900">Check your email</h3>
                  <p className="text-sm text-gray-500">
                    A 6-character completion code was sent to both parties. Enter your code below to confirm.
                  </p>
                </div>
              </div>
              <div className="flex gap-2 justify-center mb-4">
                {code.map((ch, i) => (
                  <input
                    key={i}
                    id={`fc-${i}`}
                    type="text"
                    maxLength={1}
                    value={ch}
                    onChange={(e) => handleCodeChange(i, e.target.value)}
                    className="w-11 h-12 text-center text-lg font-bold border-2 border-gray-200 rounded-xl focus:border-[#6D28D9] focus:outline-none uppercase"
                  />
                ))}
              </div>
              {error && (
                <div className="bg-amber-50 border border-amber-100 rounded-xl px-3 py-2 text-sm text-amber-700 mb-3">
                  {error}
                </div>
              )}
              <Button fullWidth onClick={handleSubmitCode} disabled={!codeComplete || submitting}>
                {submitting ? <Loader2 size={16} className="animate-spin" /> : 'Validate my code'}
              </Button>
            </Card>
            <button onClick={onReportIssue} className="w-full px-6 py-3 border-2 border-red-200 rounded-xl font-semibold text-red-600 hover:bg-red-50 transition-all text-sm flex items-center justify-center gap-2">
              <AlertCircle size={16} />
              Report an issue
            </button>
          </>
        ) : (
          <>
            {/* Task summary */}
            <Card>
              <div className="flex items-center gap-3 mb-4">
                <div className="w-12 h-12 rounded-xl bg-green-50 flex items-center justify-center flex-shrink-0">
                  <CheckCircle2 size={24} className="text-green-600" strokeWidth={2.5} />
                </div>
                <div className="flex-1 min-w-0">
                  <h3 className="font-semibold text-gray-900">Mark as completed</h3>
                  {task?.assignedTo && (
                    <p className="text-sm text-gray-500 truncate">Tasker: {task.assignedTo.slice(0, 16)}</p>
                  )}
                </div>
              </div>
              <div className="bg-gray-50 rounded-xl p-4">
                {task && <p className="text-sm font-medium text-gray-700 mb-3 line-clamp-2">{task.title || task.description.slice(0, 80)}</p>}
                <div className="flex items-baseline justify-between">
                  <span className="text-sm text-gray-500">Amount in escrow</span>
                  <span className="text-2xl font-bold text-gray-900">{escrowAmount}</span>
                </div>
              </div>
            </Card>

            {/* Completion % selector */}
            <Card>
              <h4 className="font-semibold text-gray-900 mb-2">Completion percentage</h4>
              <p className="text-xs text-gray-500 mb-3">Select how much of the work was done. Partial completion = partial payment.</p>
              <div className="flex gap-2 flex-wrap">
                {[25, 50, 75, 100].map(pct => (
                  <button
                    key={pct}
                    onClick={() => setCompletionPct(pct)}
                    className={`px-4 py-2 rounded-xl text-sm font-semibold border-2 transition-all ${
                      completionPct === pct
                        ? 'border-[#6D28D9] bg-[#6D28D9] text-white'
                        : 'border-gray-200 text-gray-700 hover:border-[#6D28D9]'
                    }`}
                  >
                    {pct}%
                  </button>
                ))}
              </div>
              {completionPct < 100 && (
                <p className="text-xs text-amber-600 mt-2">
                  Partial completion: tasker gets ~10% ({task ? `${(task.price * 0.1).toFixed(0)} ${task.currency}` : ''}), client refunded the rest.
                </p>
              )}
            </Card>

            {/* Escrow protection */}
            <Card>
              <div className="flex items-start gap-3 mb-3">
                <div className="w-10 h-10 rounded-xl bg-blue-50 flex items-center justify-center flex-shrink-0">
                  <Shield size={20} className="text-blue-600" />
                </div>
                <div>
                  <h4 className="font-semibold text-gray-900 mb-1">Dual-code validation</h4>
                  <p className="text-sm text-gray-600">
                    Both you and the tasker will receive a code by email. Both codes must be validated to release payment. Full work enters a 24h dispute window.
                  </p>
                </div>
              </div>
              <EscrowBadge amount={escrowAmount} status="held" />
            </Card>

            {error && (
              <div className="bg-red-50 border border-red-100 rounded-xl p-3 flex items-start gap-2">
                <AlertCircle size={16} className="text-red-500 flex-shrink-0 mt-0.5" />
                <p className="text-sm text-red-600">{error}</p>
              </div>
            )}

            <div className="space-y-3 pt-2">
              <Button fullWidth onClick={handleMarkComplete} disabled={submitting}>
                {submitting ? (
                  <span className="flex items-center justify-center gap-2">
                    <Loader2 size={16} className="animate-spin" />
                    Sending codes…
                  </span>
                ) : (
                  `Declare ${completionPct}% complete & send codes`
                )}
              </Button>
              <button onClick={onReportIssue} disabled={submitting} className="w-full px-6 py-3.5 border-2 border-red-200 rounded-xl font-semibold text-red-600 hover:bg-red-50 transition-all flex items-center justify-center gap-2 disabled:opacity-50">
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
