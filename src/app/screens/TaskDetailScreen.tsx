import { useEffect, useState, useCallback } from 'react';
import { Button } from '../components/Button';
import { Card } from '../components/Card';
import { TaskProgressBar } from '../components/TaskProgressBar';
import { TaskStatusBadge } from '../components/TaskStatusBadge';
import { EscrowBadge } from '../components/EscrowBadge';
import { taskService, walletService, apiClient } from '@zaska/shared-services';
import type { Task, Escrow, NegotiationEvent } from '@zaska/shared-services';
import {
  ArrowLeft, MapPin, MessageCircle, Users, RefreshCw,
  CheckCircle2, Clock, AlertTriangle, Loader2, TrendingUp,
  Trash2, History, ChevronDown, ChevronUp,
} from 'lucide-react';

// ── Negotiation Panel ─────────────────────────────────────────────────────────
interface NegotiationPanelProps {
  task: Task;
  currentUserId: string;
  onReload: () => void;
}

function NegotiationPanel({ task, currentUserId, onReload }: NegotiationPanelProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isInitiator = task.negotiatedBy === currentUserId;
  const isResponder = !isInitiator && (task.createdBy === currentUserId || task.assignedTo === currentUserId);
  const status = task.negotiationStatus;
  const proposed = task.negotiatedPrice ? Number(task.negotiatedPrice) : null;

  const respond = async (accept: boolean) => {
    setLoading(true);
    setError(null);
    try {
      await taskService.respondToNegotiation(task.id, accept);
      onReload();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erreur');
    } finally {
      setLoading(false);
    }
  };

  const abandon = async () => {
    setLoading(true);
    setError(null);
    try {
      await taskService.abandonNegotiation(task.id);
      onReload();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erreur');
    } finally {
      setLoading(false);
    }
  };

  if (!proposed) return null;

  return (
    <Card className={`border-2 ${
      status === 'accepted' ? 'border-green-200 bg-green-50/40' :
      status === 'rejected' ? 'border-red-200 bg-red-50/40' :
      'border-amber-200 bg-amber-50/40'
    }`}>
      <div className="flex items-center gap-2 mb-3">
        <TrendingUp size={16} className={
          status === 'accepted' ? 'text-green-600' :
          status === 'rejected' ? 'text-red-500' : 'text-amber-600'
        } />
        <h4 className="font-semibold text-sm text-gray-900">
          {status === 'accepted' ? 'Modification de prix acceptée' :
           status === 'rejected' ? 'Modification de prix refusée' :
           'Modification de prix en attente'}
        </h4>
      </div>

      <div className="flex gap-3 mb-3">
        <div className="flex-1 bg-white rounded-xl p-3 border border-gray-100">
          <p className="text-xs text-gray-400 mb-1">Prix initial</p>
          <p className="font-bold text-gray-900 text-sm">
            {task.currency} {Number(task.originalPrice ?? task.price).toFixed(2)}
          </p>
        </div>
        <div className={`flex-1 rounded-xl p-3 border ${
          status === 'accepted' ? 'bg-green-50 border-green-200' :
          status === 'rejected' ? 'bg-red-50 border-red-200' :
          'bg-amber-50 border-amber-200'
        }`}>
          <p className="text-xs text-gray-400 mb-1">
            {status === 'accepted' ? 'Accepté' : 'Proposé'}
          </p>
          <p className={`font-bold text-sm ${
            status === 'accepted' ? 'text-green-700' :
            status === 'rejected' ? 'text-red-600' : 'text-amber-800'
          }`}>{task.currency} {proposed.toFixed(2)}</p>
        </div>
      </div>

      {/* Pending — responder can accept or reject */}
      {status === 'pending' && isResponder && (
        <div className="flex gap-2">
          <button
            onClick={() => respond(true)}
            disabled={loading}
            className="flex-1 py-2.5 bg-green-600 text-white rounded-xl text-sm font-semibold hover:bg-green-700 disabled:opacity-50 flex items-center justify-center gap-1"
          >
            {loading ? <Loader2 size={14} className="animate-spin" /> : <CheckCircle2 size={14} />}
            Accepter
          </button>
          <button
            onClick={() => respond(false)}
            disabled={loading}
            className="flex-1 py-2.5 border-2 border-red-200 text-red-600 rounded-xl text-sm font-semibold hover:bg-red-50 disabled:opacity-50 flex items-center justify-center gap-1"
          >
            <AlertTriangle size={14} />
            Refuser
          </button>
        </div>
      )}

      {/* Pending — initiator is waiting */}
      {status === 'pending' && isInitiator && (
        <p className="text-xs text-amber-700 bg-amber-100 rounded-xl px-3 py-2">
          <Clock size={12} className="inline mr-1" />
          En attente de réponse du client…
        </p>
      )}

      {/* Rejected — initiator can abandon */}
      {status === 'rejected' && isInitiator && (
        <button
          onClick={abandon}
          disabled={loading}
          className="w-full py-2.5 border-2 border-gray-200 text-gray-600 rounded-xl text-sm font-semibold hover:bg-gray-50 disabled:opacity-50"
        >
          {loading ? <Loader2 size={14} className="animate-spin inline" /> : 'Abandonner la tâche'}
        </button>
      )}

      {/* Rejected — show message to responder */}
      {status === 'rejected' && !isInitiator && (
        <p className="text-xs text-red-700 bg-red-100 rounded-xl px-3 py-2">
          Vous avez refusé cette proposition. Le prestataire en a été notifié.
        </p>
      )}

      {/* Accepted */}
      {status === 'accepted' && (
        <p className="text-xs text-green-700 bg-green-100 rounded-xl px-3 py-2">
          <CheckCircle2 size={12} className="inline mr-1" />
          Prix accepté — le paiement sera basé sur ce montant.
        </p>
      )}

      {error && <p className="text-xs text-red-600 mt-2">{error}</p>}
    </Card>
  );
}

// ── Negotiation History Panel ─────────────────────────────────────────────────
function NegotiationHistoryPanel({ taskId, currency }: { taskId: string; currency: string }) {
  const [events, setEvents] = useState<NegotiationEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);

  const load = async () => {
    if (!open) { setOpen(true); }
    if (events.length > 0) { setOpen(!open); return; }
    setLoading(true);
    try {
      const evts = await taskService.getNegotiationHistory(taskId);
      setEvents(evts);
      setOpen(true);
    } catch { /* silent */ }
    finally { setLoading(false); }
  };

  const EVENT_LABELS: Record<string, { label: string; color: string }> = {
    proposed: { label: 'Prix proposé', color: 'text-amber-700 bg-amber-50 border-amber-200' },
    accepted: { label: 'Prix accepté', color: 'text-green-700 bg-green-50 border-green-200' },
    rejected: { label: 'Prix refusé', color: 'text-red-700 bg-red-50 border-red-200' },
    abandoned: { label: 'Tâche abandonnée', color: 'text-gray-600 bg-gray-50 border-gray-200' },
    counter: { label: 'Contre-offre', color: 'text-blue-700 bg-blue-50 border-blue-200' },
  };

  return (
    <Card>
      <button
        onClick={load}
        className="w-full flex items-center justify-between text-sm font-semibold text-gray-700"
      >
        <span className="flex items-center gap-2">
          <History size={16} className="text-[#6D28D9]" />
          Historique des négociations
        </span>
        {loading
          ? <Loader2 size={14} className="animate-spin text-gray-400" />
          : open ? <ChevronUp size={16} className="text-gray-400" /> : <ChevronDown size={16} className="text-gray-400" />}
      </button>
      {open && !loading && (
        <div className="mt-3 space-y-2">
          {events.length === 0 ? (
            <p className="text-xs text-gray-400 text-center py-2">Aucun historique disponible</p>
          ) : (
            events.map((ev) => {
              const meta = EVENT_LABELS[ev.eventType] ?? { label: ev.eventType, color: 'text-gray-600 bg-gray-50 border-gray-200' };
              return (
                <div key={ev.id} className={`flex items-center justify-between rounded-xl border px-3 py-2 ${meta.color}`}>
                  <div>
                    <p className="text-xs font-semibold">{meta.label}</p>
                    <p className="text-xs opacity-70">{ev.actorName} · {new Date(ev.createdAt).toLocaleString('fr-FR', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</p>
                  </div>
                  {ev.price != null && (
                    <p className="text-sm font-bold">{currency} {ev.price.toFixed(2)}</p>
                  )}
                </div>
              );
            })
          )}
        </div>
      )}
    </Card>
  );
}

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
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleting, setDeleting] = useState(false);
  // Cancel modal
  const [showCancelModal, setShowCancelModal] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  // Partial completion
  const [showCompleteModal, setShowCompleteModal] = useState(false);
  const [isPartial, setIsPartial] = useState(false);
  const [completionPct, setCompletionPct] = useState(80);

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

  const handleDelete = async () => {
    setDeleting(true);
    try {
      await taskService.deleteTask(taskId);
      onBack();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Impossible de supprimer la tâche');
      setShowDeleteConfirm(false);
    } finally {
      setDeleting(false);
    }
  };

  const handleCancel = async (republish: boolean) => {
    setCancelling(true);
    setActionError(null);
    try {
      await taskService.cancelTask(taskId, republish);
      setShowCancelModal(false);
      if (republish) load(); else onBack();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Impossible d\'annuler la tâche');
      setShowCancelModal(false);
    } finally {
      setCancelling(false);
    }
  };

  const handleExecutorDone = async () => {
    setShowCompleteModal(true);
  };

  const submitCompletion = async () => {
    setActionLoading(true);
    setActionError(null);
    setShowCompleteModal(false);
    try {
      await taskService.completeTask(taskId, isPartial, isPartial ? completionPct : 100);
      load();
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
  const locationCity = task.city
    ? [task.city, task.country].filter(Boolean).join(', ')
    : null;
  const locationDisplay = locationCity ?? task.address ?? `${task.latitude.toFixed(4)}, ${task.longitude.toFixed(4)}`;

  return (
    <div className="h-full flex flex-col bg-gray-50">
      {/* Cancel task modal */}
      {showCancelModal && task && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-6">
          <div className="bg-white rounded-3xl p-6 w-full max-w-sm">
            <h3 className="font-bold text-gray-900 text-lg mb-2">Annuler la tâche ?</h3>
            <p className="text-sm text-gray-500 mb-5">
              Le prestataire sera notifié et le paiement vous sera remboursé.
              Que souhaitez-vous faire ?
            </p>
            <div className="flex flex-col gap-3">
              <button
                onClick={() => handleCancel(true)}
                disabled={cancelling}
                className="w-full py-3 rounded-xl bg-[#6D28D9] font-semibold text-white flex items-center justify-center gap-2"
              >
                {cancelling ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
                Republier la tâche
              </button>
              <button
                onClick={() => handleCancel(false)}
                disabled={cancelling}
                className="w-full py-3 rounded-xl bg-red-500 font-semibold text-white flex items-center justify-center gap-2"
              >
                {cancelling ? <Loader2 size={16} className="animate-spin" /> : <Trash2 size={16} />}
                Annuler définitivement
              </button>
              <button
                onClick={() => setShowCancelModal(false)}
                disabled={cancelling}
                className="w-full py-2.5 rounded-xl border-2 border-gray-200 font-semibold text-gray-700"
              >
                Retour
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Partial/complete completion modal */}
      {showCompleteModal && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-6">
          <div className="bg-white rounded-3xl p-6 w-full max-w-sm">
            <h3 className="font-bold text-gray-900 text-lg mb-1">Déclarer la prestation</h3>
            <p className="text-sm text-gray-500 mb-4">Le client sera notifié et aura 6h pour confirmer.</p>
            <div className="flex gap-2 mb-4">
              <button
                onClick={() => setIsPartial(false)}
                className={`flex-1 py-2.5 rounded-xl text-sm font-semibold border-2 transition-colors ${
                  !isPartial ? 'bg-green-600 border-green-600 text-white' : 'border-gray-200 text-gray-600'
                }`}
              >
                ✓ Totalement terminée
              </button>
              <button
                onClick={() => setIsPartial(true)}
                className={`flex-1 py-2.5 rounded-xl text-sm font-semibold border-2 transition-colors ${
                  isPartial ? 'bg-amber-500 border-amber-500 text-white' : 'border-gray-200 text-gray-600'
                }`}
              >
                ~ Partiellement
              </button>
            </div>
            {isPartial && (
              <div className="mb-4">
                <div className="flex justify-between text-sm text-gray-600 mb-2">
                  <span>Avancement</span>
                  <span className="font-bold text-amber-600">{completionPct}%</span>
                </div>
                <input
                  type="range"
                  min={10} max={99} step={5}
                  value={completionPct}
                  onChange={(e) => setCompletionPct(Number(e.target.value))}
                  className="w-full accent-amber-500"
                />
                <p className="text-xs text-gray-400 mt-1">
                  Vous recevrez {completionPct}% du montant convenu. Le client sera remboursé du reste.
                </p>
              </div>
            )}
            <div className="flex gap-3">
              <button
                onClick={() => setShowCompleteModal(false)}
                className="flex-1 py-3 rounded-xl border-2 border-gray-200 font-semibold text-gray-700"
              >
                Annuler
              </button>
              <button
                onClick={submitCompletion}
                className={`flex-1 py-3 rounded-xl font-semibold text-white ${
                  isPartial ? 'bg-amber-500 hover:bg-amber-600' : 'bg-green-600 hover:bg-green-700'
                }`}
              >
                Confirmer
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete confirmation modal */}
      {showDeleteConfirm && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-6">
          <div className="bg-white rounded-3xl p-6 w-full max-w-sm">
            <h3 className="font-bold text-gray-900 text-lg mb-2">Supprimer la tâche ?</h3>
            <p className="text-sm text-gray-500 mb-5">Cette action est irréversible. La tâche sera définitivement supprimée.</p>
            <div className="flex gap-3">
              <button
                onClick={() => setShowDeleteConfirm(false)}
                className="flex-1 py-3 rounded-xl border-2 border-gray-200 font-semibold text-gray-700"
                disabled={deleting}
              >
                Annuler
              </button>
              <button
                onClick={handleDelete}
                disabled={deleting}
                className="flex-1 py-3 rounded-xl bg-red-500 font-semibold text-white flex items-center justify-center gap-2"
              >
                {deleting ? <Loader2 size={16} className="animate-spin" /> : <Trash2 size={16} />}
                Supprimer
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Header */}
      <div className="px-6 pt-8 pb-4 bg-white border-b border-gray-200">
        <div className="flex items-center gap-3">
          <button onClick={onBack} className="p-2 -ml-2 hover:bg-gray-100 rounded-full transition-colors">
            <ArrowLeft size={24} className="text-gray-700" />
          </button>
          <div className="flex-1">
            <h2 className="text-2xl font-bold text-gray-900 mb-1">
              {isClient ? 'Ma tâche' : isExecutor ? 'Ma mission' : 'Détail de la tâche'}
            </h2>
            <TaskStatusBadge
              status={
                progressStatus === 'paid' ? 'completed' :
                progressStatus === 'validation' ? 'awaiting_payment' :
                progressStatus === 'applications' ? 'accepted' :
                progressStatus === 'in_progress' ? 'in_progress' :
                'posted'
              }
              size="md"
            />
          </div>
          {/* Cancel ASSIGNED task — republish or cancel permanently */}
          {isClient && task.status === 'ASSIGNED' && (
            <button
              onClick={() => setShowCancelModal(true)}
              className="p-2 hover:bg-red-50 rounded-full transition-colors"
              title="Annuler la tâche"
            >
              <Trash2 size={20} className="text-red-500" />
            </button>
          )}
          {/* Delete button — only creator, only on deletable statuses */}
          {isClient && (task.status === 'OPEN' || task.status === 'PAUSED') && (
            <button
              onClick={() => setShowDeleteConfirm(true)}
              className="p-2 hover:bg-red-50 rounded-full transition-colors"
              title="Supprimer la tâche"
            >
              <Trash2 size={20} className="text-red-500" />
            </button>
          )}
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
          <div className="flex items-start gap-3 text-sm text-gray-500 mb-2">
            <MapPin size={16} className="mt-0.5 flex-shrink-0 text-[#6D28D9]" />
            <div>
              <span className="font-medium text-gray-800">{locationDisplay}</span>
              {locationCity && task.address && task.address !== locationDisplay && (
                <p className="text-xs text-gray-400 mt-0.5">{task.address}</p>
              )}
            </div>
          </div>
          {/* Scheduled time */}
          {task.anySchedule ? (
            <div className="flex items-center gap-2 text-sm text-gray-400 mt-1">
              <Clock size={14} className="text-gray-300" />
              <span>Horaire flexible — le prestataire s'organise</span>
            </div>
          ) : task.scheduledAt ? (
            <div className="flex items-center gap-2 text-sm text-[#6D28D9] mt-1">
              <Clock size={14} />
              <span className="font-medium">
                {new Date(task.scheduledAt).toLocaleString('fr-FR', {
                  weekday: 'short', day: 'numeric', month: 'short',
                  hour: '2-digit', minute: '2-digit',
                })}
              </span>
            </div>
          ) : null}
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
                <h4 className="font-semibold text-gray-900">
                  {task.completionPercent != null && task.completionPercent < 100
                    ? `Prestation déclarée à ${task.completionPercent}%`
                    : 'Prestation déclarée terminée'}
                </h4>
                <p className="text-xs text-gray-500 mt-0.5">
                  {task.completionPercent != null && task.completionPercent < 100
                    ? `Le prestataire déclare avoir réalisé ${task.completionPercent}% du travail. En confirmant, vous payez ${task.completionPercent}% et êtes remboursé du reste.`
                    : 'Confirmez si le travail est satisfaisant, ou contestez si ce n\'est pas le cas. Sans action de votre part, le paiement sera libéré dans 6h.'}
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
                <h4 className="font-semibold text-gray-900">
                  {task.completionPercent != null && task.completionPercent < 100
                    ? `Prestation déclarée à ${task.completionPercent}%`
                    : 'En attente de validation'}
                </h4>
                <p className="text-sm text-gray-600 mt-0.5">
                  {task.completionPercent != null && task.completionPercent < 100
                    ? `Vous avez déclaré avoir réalisé ${task.completionPercent}% de la tâche. Le client dispose de 6h pour confirmer. Vous recevrez ${task.completionPercent}% du montant.`
                    : 'Votre prestation a été déclarée terminée. Le client a été notifié et dispose de 6h pour confirmer. Sans action de sa part, le paiement vous sera libéré automatiquement.'}
                </p>
              </div>
            </div>
          </Card>
        )}

        {/* ── Negotiation panel ── */}
        {task.negotiationStatus && task.negotiationStatus !== 'none' && (
          <NegotiationPanel
            task={task}
            currentUserId={currentUserId ?? ''}
            onReload={load}
          />
        )}

        {/* ── Negotiation history (for parties involved) ── */}
        {(isClient || isExecutor) && task.negotiationStatus && task.negotiationStatus !== 'none' && (
          <NegotiationHistoryPanel taskId={taskId} currency={task.currency} />
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
            Le client sera notifié et aura 6h pour confirmer ou contester
          </p>
        </div>
      )}
    </div>
  );
}
