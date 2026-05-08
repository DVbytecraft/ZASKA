import { useEffect, useState, useCallback } from 'react';
import { Button } from '../components/Button';
import { Card } from '../components/Card';
import { TaskProgressBar } from '../components/TaskProgressBar';
import { TaskStatusBadge } from '../components/TaskStatusBadge';
import { EscrowBadge } from '../components/EscrowBadge';
import { taskService, walletService, apiClient } from '@zaska/shared-services';
import type { Task, Escrow } from '@zaska/shared-services';
import {
  ArrowLeft, MapPin, MessageCircle, Users, RefreshCw,
  CheckCircle2, Clock, AlertTriangle, Loader2,
} from 'lucide-react';

interface TaskDetailScreenProps {
  taskId: string;
  onBack: () => void;
  onComplete: () => void;   // called after client confirms payment released
  onChat: (taskerName?: string) => void;
  onViewApplicants?: () => void;
}

type ProgressStatus = 'posted' | 'applications' | 'in_progress' | 'validation' | 'paid';

function statusToProgressStatus(status: Task['status']): ProgressStatus {
  if (status === 'ASSIGNED') return 'in_progress';
  if (status === 'PENDING_VALIDATION') return 'validation';
  if (status === 'COMPLETED') return 'paid';
  return 'posted';
}

export function TaskDetailScreen({ taskId, onBack, onComplete, onChat, onViewApplicants }: TaskDetailScreenProps) {
  const [task, setTask] = useState<Task | null>(null);
  const [escrow, setEscrow] = useState<Escrow | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Inline action states
  const [actionLoading, setActionLoading] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [showContestForm, setShowContestForm] = useState(false);
  const [contestReason, setContestReason] = useState('');

  const currentUserId = apiClient.getUserId();

  const load = useCallback(() => {
    if (!taskId) { setError('Aucun ID de tâche fourni'); setLoading(false); return; }
    setLoading(true);
    setError(null);
    taskService.getTask(taskId)
      .then(async (t) => {
        setTask(t);
        try {
          const esc = await walletService.getEscrowForTask(taskId);
          setEscrow(esc);
        } catch { /* no escrow yet */ }
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Impossible de charger la tâche'))
      .finally(() => setLoading(false));
  }, [taskId]);

  useEffect(() => { load(); }, [load]);

  // ── Action handlers ──────────────────────────────────────────────────────────

  const handleExecutorDone = async () => {
    setActionLoading(true);
    setActionError(null);
    try {
      await taskService.completeTask(taskId);
      load(); // task status → PENDING_VALIDATION
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Erreur lors de la déclaration');
    } finally {
      setActionLoading(false);
    }
  };

  const handleClientConfirm = async () => {
    setActionLoading(true);
    setActionError(null);
    try {
      await taskService.confirmTask(taskId);
      onComplete(); // navigate to paymentSuccess
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Erreur lors de la confirmation');
      setActionLoading(false);
    }
  };

  const handleClientContest = async () => {
    if (contestReason.trim().length < 10) {
      setActionError('Veuillez décrire le problème (minimum 10 caractères).');
      return;
    }
    setActionLoading(true);
    setActionError(null);
    try {
      await taskService.contestTask(taskId, contestReason.trim());
      load(); // reload — escrow now frozen, admin will intervene
      setShowContestForm(false);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Erreur lors de la contestation');
    } finally {
      setActionLoading(false);
    }
  };

  // ── Loading / error states ───────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="h-full flex flex-col bg-gray-50">
        <div className="px-6 pt-8 pb-4 bg-white border-b border-gray-200">
          <div className="flex items-center gap-3">
            <button onClick={onBack} className="p-2 -ml-2 hover:bg-gray-100 rounded-full">
              <ArrowLeft size={24} className="text-gray-700" />
            </button>
            <h2 className="text-2xl font-bold text-gray-900">Détail de la tâche</h2>
          </div>
        </div>
        <div className="flex-1 flex items-center justify-center">
          <Loader2 size={32} className="animate-spin text-[#6D28D9]" />
        </div>
      </div>
    );
  }

  if (error || !task) {
    return (
      <div className="h-full flex flex-col bg-gray-50">
        <div className="px-6 pt-8 pb-4 bg-white border-b border-gray-200">
          <div className="flex items-center gap-3">
            <button onClick={onBack} className="p-2 -ml-2 hover:bg-gray-100 rounded-full">
              <ArrowLeft size={24} className="text-gray-700" />
            </button>
            <h2 className="text-2xl font-bold text-gray-900">Détail de la tâche</h2>
          </div>
        </div>
        <div className="flex-1 flex flex-col items-center justify-center px-6 gap-4">
          <p className="text-sm text-red-600 text-center">{error ?? 'Tâche introuvable'}</p>
          <button onClick={load} className="flex items-center gap-2 text-sm font-semibold text-[#6D28D9] hover:underline">
            <RefreshCw size={16} /> Réessayer
          </button>
          <button onClick={onBack} className="text-sm text-gray-500 hover:underline">Retour</button>
        </div>
      </div>
    );
  }

  const isClient = task.createdBy === currentUserId;
  const isExecutor = task.assignedTo === currentUserId;
  const progressStatus = statusToProgressStatus(task.status);
  const escrowStatus: 'held' | 'released' = escrow?.status === 'released' ? 'released' : 'held';
  const escrowAmount = escrow
    ? `${task.currency} ${parseFloat(escrow.amount).toFixed(2)}`
    : `${task.currency} ${Number(task.price).toFixed(2)}`;
  const locationDisplay = task.address || `${task.latitude.toFixed(4)}, ${task.longitude.toFixed(4)}`;

  return (
    <div className="h-full flex flex-col bg-gray-50">
      {/* Header */}
      <div className="px-6 pt-8 pb-4 bg-white border-b border-gray-200">
        <div className="flex items-center gap-3">
          <button onClick={onBack} className="p-2 -ml-2 hover:bg-gray-100 rounded-full transition-colors">
            <ArrowLeft size={24} className="text-gray-700" />
          </button>
          <div>
            <h2 className="text-2xl font-bold text-gray-900 mb-1">
              {isClient ? 'Ma tâche' : isExecutor ? 'Ma mission' : 'Détail de la tâche'}
            </h2>
            <TaskStatusBadge
              status={progressStatus === 'paid' ? 'completed' : progressStatus === 'posted' ? 'posted' : progressStatus}
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
          {task.title && <p className="text-sm text-gray-600 mb-3">{task.description}</p>}
          <div className="flex items-start gap-3 text-sm text-gray-500">
            <MapPin size={16} className="mt-0.5 flex-shrink-0 text-[#6D28D9]" />
            <span>{locationDisplay}</span>
          </div>
        </Card>

        {/* ── CLIENT: applicants CTA (OPEN) ── */}
        {isClient && task.status === 'OPEN' && onViewApplicants && (
          <Card className="border-2 border-[#6D28D9]/20 bg-purple-50/50">
            <div className="flex items-center gap-3 mb-3">
              <div className="w-10 h-10 rounded-xl bg-[#6D28D9]/10 flex items-center justify-center">
                <Users size={20} className="text-[#6D28D9]" />
              </div>
              <div>
                <h4 className="font-semibold text-gray-900">Examiner les candidats</h4>
                <p className="text-xs text-gray-500">Des prestataires ont postulé et attendent votre choix</p>
              </div>
            </div>
            <button
              onClick={onViewApplicants}
              className="w-full py-3 bg-[#6D28D9] text-white rounded-xl font-semibold text-sm hover:bg-[#5B21B6] transition-colors"
            >
              Voir les candidats
            </button>
          </Card>
        )}

        {/* ── CLIENT: tasker assigned + chat (ASSIGNED) ── */}
        {isClient && task.status === 'ASSIGNED' && task.assignedTo && (
          <Card>
            <h4 className="font-semibold text-gray-900 mb-3 text-sm uppercase tracking-wide">Prestataire assigné</h4>
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
              <MessageCircle size={18} /> Envoyer un message au prestataire
            </button>
          </Card>
        )}

        {/* ── CLIENT: validation panel (PENDING_VALIDATION) ── */}
        {isClient && task.status === 'PENDING_VALIDATION' && (
          <Card className="border-2 border-green-200 bg-green-50/40">
            <div className="flex items-start gap-3 mb-4">
              <div className="w-10 h-10 rounded-xl bg-green-100 flex items-center justify-center flex-shrink-0">
                <CheckCircle2 size={20} className="text-green-600" />
              </div>
              <div>
                <h4 className="font-semibold text-gray-900">Prestation déclarée terminée</h4>
                <p className="text-xs text-gray-500 mt-0.5">
                  Confirmez si le travail est satisfaisant, ou contestez si ce n'est pas le cas.
                  Sans action de votre part, le paiement sera libéré dans 24h.
                </p>
              </div>
            </div>

            {showContestForm ? (
              <div className="space-y-3">
                <textarea
                  value={contestReason}
                  onChange={(e) => setContestReason(e.target.value)}
                  placeholder="Décrivez le problème en détail (minimum 10 caractères)..."
                  rows={3}
                  maxLength={500}
                  className="w-full px-4 py-3 rounded-xl border-2 border-red-200 focus:border-red-400 focus:outline-none text-sm resize-none"
                />
                <div className="flex gap-2">
                  <button
                    onClick={() => { setShowContestForm(false); setActionError(null); }}
                    className="flex-1 py-2.5 border-2 border-gray-200 rounded-xl text-sm font-medium text-gray-600 hover:bg-gray-50"
                    disabled={actionLoading}
                  >
                    Annuler
                  </button>
                  <button
                    onClick={handleClientContest}
                    disabled={actionLoading || contestReason.trim().length < 10}
                    className="flex-1 py-2.5 bg-red-600 text-white rounded-xl text-sm font-semibold hover:bg-red-700 disabled:opacity-50 transition-colors"
                  >
                    {actionLoading ? <Loader2 size={16} className="animate-spin mx-auto" /> : 'Confirmer la contestation'}
                  </button>
                </div>
              </div>
            ) : (
              <div className="flex gap-2">
                <button
                  onClick={handleClientConfirm}
                  disabled={actionLoading}
                  className="flex-1 py-3 bg-green-600 text-white rounded-xl font-semibold text-sm hover:bg-green-700 disabled:opacity-50 transition-colors flex items-center justify-center gap-2"
                >
                  {actionLoading
                    ? <Loader2 size={16} className="animate-spin" />
                    : <><CheckCircle2 size={16} /> Confirmer et libérer</>}
                </button>
                <button
                  onClick={() => setShowContestForm(true)}
                  disabled={actionLoading}
                  className="flex-1 py-3 border-2 border-red-200 text-red-600 rounded-xl font-semibold text-sm hover:bg-red-50 disabled:opacity-50 transition-colors flex items-center justify-center gap-2"
                >
                  <AlertTriangle size={16} /> Contester
                </button>
              </div>
            )}
          </Card>
        )}

        {/* ── EXECUTOR: mission card + chat (ASSIGNED) ── */}
        {isExecutor && task.status === 'ASSIGNED' && (
          <Card className="border-2 border-blue-200 bg-blue-50/40">
            <div className="flex items-center gap-3 mb-3">
              <div className="w-10 h-10 rounded-xl bg-blue-100 flex items-center justify-center">
                <CheckCircle2 size={20} className="text-blue-600" />
              </div>
              <div>
                <h4 className="font-semibold text-gray-900">Mission acceptée</h4>
                <p className="text-xs text-gray-500">Vous êtes l'exécutant de cette tâche</p>
              </div>
            </div>
            <button
              onClick={() => onChat(task.createdBy)}
              className="w-full flex items-center justify-center gap-2 px-4 py-3 border-2 border-gray-200 rounded-xl hover:border-blue-500 hover:text-blue-600 transition-colors font-medium text-sm"
            >
              <MessageCircle size={18} /> Envoyer un message au client
            </button>
          </Card>
        )}

        {/* ── EXECUTOR: waiting status (PENDING_VALIDATION) ── */}
        {isExecutor && task.status === 'PENDING_VALIDATION' && (
          <Card className="border-2 border-amber-200 bg-amber-50/40">
            <div className="flex items-start gap-3">
              <div className="w-10 h-10 rounded-xl bg-amber-100 flex items-center justify-center flex-shrink-0">
                <Clock size={20} className="text-amber-600" />
              </div>
              <div>
                <h4 className="font-semibold text-gray-900">En attente de validation</h4>
                <p className="text-sm text-gray-600 mt-0.5">
                  Votre prestation a été déclarée terminée. Le client a été notifié et dispose de 24h pour confirmer.
                  Sans action de sa part, le paiement vous sera libéré automatiquement.
                </p>
              </div>
            </div>
          </Card>
        )}

        {/* Payment / Escrow */}
        <Card>
          <h4 className="font-semibold text-gray-900 mb-3 text-sm uppercase tracking-wide">Paiement</h4>
          <div className="flex items-baseline justify-between mb-4">
            <span className="text-gray-600 text-sm">Montant total</span>
            <span className="text-2xl font-bold text-gray-900">
              {task.currency} {Number(task.price).toFixed(2)}
            </span>
          </div>
          {task.negotiatedPrice && task.negotiationStatus === 'pending' && (
            <div className="mb-3 p-3 bg-amber-50 rounded-xl border border-amber-100">
              <p className="text-xs font-semibold text-amber-700">Modification de prix en attente</p>
              <p className="text-sm text-amber-900 mt-0.5">
                Prix proposé : {task.currency} {Number(task.negotiatedPrice).toFixed(2)}
              </p>
            </div>
          )}
          <EscrowBadge amount={escrowAmount} status={escrowStatus} />
          {task.status === 'COMPLETED' && (
            <p className="text-xs text-green-600 mt-3 font-medium">Paiement libéré au prestataire.</p>
          )}
        </Card>

        {/* Action error */}
        {actionError && (
          <div className="bg-red-50 border border-red-100 rounded-xl p-3 flex items-center gap-2">
            <AlertTriangle size={16} className="text-red-500 flex-shrink-0" />
            <p className="text-sm text-red-600">{actionError}</p>
          </div>
        )}
      </div>

      {/* ── Bottom CTA: executor ASSIGNED → declare done ── */}
      {isExecutor && task.status === 'ASSIGNED' && (
        <div className="px-6 py-4 bg-white border-t border-gray-200">
          <Button fullWidth onClick={handleExecutorDone} disabled={actionLoading}>
            {actionLoading
              ? <span className="flex items-center justify-center gap-2"><Loader2 size={16} className="animate-spin" /> Envoi…</span>
              : 'Terminer ma prestation'}
          </Button>
          <p className="text-xs text-gray-400 text-center mt-2">
            Le client sera notifié et aura 24h pour confirmer ou contester
          </p>
        </div>
      )}
    </div>
  );
}
