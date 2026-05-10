import { useEffect, useState } from 'react';
import { Button } from '../components/Button';
import { Card } from '../components/Card';
import { EscrowBadge } from '../components/EscrowBadge';
import { ProofPhotoUpload } from '../components/ProofPhotoUpload';
import { taskService, walletService, chatService } from '@zaska/shared-services';
import type { Task, Escrow } from '@zaska/shared-services';
import {
  ArrowLeft, CheckCircle2, AlertCircle, Shield, Loader2, Clock,
} from 'lucide-react';

interface ConfirmCompletionScreenProps {
  taskId: string;
  onBack: () => void;
  onSuccess: () => void;
  onReportIssue: () => void;
}

type Step = 'idle' | 'submitting' | 'submitted' | 'error';

export function ConfirmCompletionScreen({
  taskId,
  onBack,
  onSuccess,
  onReportIssue,
}: ConfirmCompletionScreenProps) {
  const [task, setTask] = useState<Task | null>(null);
  const [escrow, setEscrow] = useState<Escrow | null>(null);
  const [loadingData, setLoadingData] = useState(true);
  const [step, setStep] = useState<Step>('idle');
  const [error, setError] = useState<string | null>(null);
  const [completionPct, setCompletionPct] = useState(100);
  const [proofPhoto, setProofPhoto] = useState<File | null>(null);

  useEffect(() => {
    if (!taskId) { setLoadingData(false); return; }
    let cancelled = false;
    setLoadingData(true);
    Promise.all([
      taskService.getTask(taskId),
      walletService.getEscrowForTask(taskId).catch(() => null),
    ])
      .then(([t, esc]) => { if (!cancelled) { setTask(t); setEscrow(esc); } })
      .catch((err) => { if (!cancelled) setError(err instanceof Error ? err.message : 'Impossible de charger'); })
      .finally(() => { if (!cancelled) setLoadingData(false); });
    return () => { cancelled = true; };
  }, [taskId]);

  const handleMarkComplete = async () => {
    if (!task || !proofPhoto) return;
    setStep('submitting');
    setError(null);
    try {
      // 1. Upload proof photo via existing chat upload endpoint
      let proofPhotoUrl: string | undefined;
      try {
        const upload = await chatService.uploadMedia(proofPhoto, taskId);
        proofPhotoUrl = upload.secure_url;
      } catch {
        // Non-fatal: proceed without photo URL if upload fails
      }

      // 2. Declare task complete — real backend endpoint
      await taskService.completeTask(taskId, completionPct < 100, completionPct, proofPhotoUrl);
      setStep('submitted');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Impossible de déclarer la tâche terminée');
      setStep('error');
    }
  };

  const escrowAmount = escrow
    ? `${task?.currency ?? ''} ${parseFloat(escrow.amount).toFixed(2)}`
    : task
    ? `${task.currency} ${task.price.toFixed(2)}`
    : '—';

  if (loadingData) {
    return (
      <div className="h-full flex items-center justify-center bg-gray-50">
        <Loader2 size={36} className="text-[#6D28D9] animate-spin" />
      </div>
    );
  }

  // ── Success state ──────────────────────────────────────────────────────────
  if (step === 'submitted') {
    return (
      <div className="h-full flex flex-col bg-gray-50">
        <div className="px-6 pt-8 pb-4 bg-white border-b border-gray-200">
          <div className="flex items-center gap-3">
            <button onClick={onBack} className="p-2 -ml-2 hover:bg-gray-100 rounded-full transition-colors">
              <ArrowLeft size={24} className="text-gray-700" />
            </button>
            <h2 className="text-2xl font-bold text-gray-900">Prestation déclarée</h2>
          </div>
        </div>
        <div className="flex-1 flex flex-col items-center justify-center gap-5 px-6">
          <div className="w-20 h-20 rounded-full bg-green-50 flex items-center justify-center">
            <CheckCircle2 size={44} className="text-green-500" strokeWidth={2} />
          </div>
          <div className="text-center">
            <h3 className="text-xl font-bold text-gray-900 mb-2">Prestation déclarée terminée</h3>
            <p className="text-sm text-gray-500 leading-relaxed">
              Le client a été notifié. Il dispose de <strong>6 heures</strong> pour confirmer ou
              contester. Sans réponse, le paiement sera libéré automatiquement.
            </p>
          </div>
          <Card className="w-full">
            <div className="flex items-start gap-3">
              <Clock size={20} className="text-amber-500 flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold text-gray-900 text-sm">Paiement en attente</p>
                <p className="text-xs text-gray-500 mt-0.5">
                  {escrowAmount} · Libération automatique dans 6h
                </p>
              </div>
            </div>
          </Card>
          <div className="w-full space-y-3 pt-2">
            <Button fullWidth onClick={onSuccess}>
              Retour à mes tâches
            </Button>
            <button
              onClick={onReportIssue}
              className="w-full px-6 py-3 border-2 border-red-200 rounded-xl font-semibold text-red-600 hover:bg-red-50 transition-all text-sm flex items-center justify-center gap-2"
            >
              <AlertCircle size={16} />
              Signaler un problème
            </button>
          </div>
        </div>
      </div>
    );
  }

  // ── Main form ──────────────────────────────────────────────────────────────
  return (
    <div className="h-full flex flex-col bg-gray-50">
      <div className="px-6 pt-8 pb-4 bg-white border-b border-gray-200">
        <div className="flex items-center gap-3">
          <button
            onClick={onBack}
            className="p-2 -ml-2 hover:bg-gray-100 rounded-full transition-colors"
            disabled={step === 'submitting'}
          >
            <ArrowLeft size={24} className="text-gray-700" />
          </button>
          <h2 className="text-2xl font-bold text-gray-900">Déclarer terminé</h2>
        </div>
      </div>

      <div className="flex-1 overflow-auto px-6 py-6 flex flex-col gap-4">
        {/* Task summary */}
        <Card>
          <div className="flex items-center gap-3 mb-3">
            <div className="w-10 h-10 rounded-xl bg-green-50 flex items-center justify-center flex-shrink-0">
              <CheckCircle2 size={20} className="text-green-600" strokeWidth={2.5} />
            </div>
            <div className="flex-1 min-w-0">
              <p className="font-semibold text-gray-900 text-sm line-clamp-1">
                {task?.title || task?.description.slice(0, 60) || '—'}
              </p>
              <p className="text-xs text-gray-400 mt-0.5">Prestation en cours</p>
            </div>
          </div>
          <div className="flex items-baseline justify-between bg-gray-50 rounded-xl px-4 py-3">
            <span className="text-sm text-gray-500">Montant en séquestre</span>
            <span className="text-xl font-bold text-gray-900">{escrowAmount}</span>
          </div>
        </Card>

        {/* Completion % */}
        <Card>
          <h4 className="font-semibold text-gray-900 mb-1">Pourcentage de réalisation</h4>
          <p className="text-xs text-gray-400 mb-3">
            Choisissez honnêtement. Partiel = paiement proportionnel.
          </p>
          <div className="flex gap-2 flex-wrap">
            {[25, 50, 75, 100].map((pct) => (
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
              Partiel : vous recevrez ~10% de l'escrow, le reste est remboursé au client.
            </p>
          )}
        </Card>

        {/* Proof photo */}
        <Card>
          <ProofPhotoUpload
            label="Photo de preuve du travail effectué"
            hint="Une photo claire montrant le travail accompli. Obligatoire pour valider la complétion."
            required
            onFileChange={setProofPhoto}
          />
        </Card>

        {/* Security info */}
        <Card>
          <div className="flex items-start gap-3">
            <div className="w-9 h-9 rounded-xl bg-blue-50 flex items-center justify-center flex-shrink-0">
              <Shield size={18} className="text-blue-600" />
            </div>
            <div>
              <h4 className="font-semibold text-gray-900 text-sm mb-1">Fenêtre de 6h</h4>
              <p className="text-xs text-gray-500 leading-relaxed">
                Le client a 6h pour confirmer ou contester. Sans réponse, le paiement est
                automatiquement libéré sur votre portefeuille.
              </p>
            </div>
          </div>
          <div className="mt-3">
            <EscrowBadge amount={escrowAmount} status="held" />
          </div>
        </Card>

        {(step === 'error' && error) && (
          <div className="bg-red-50 border border-red-100 rounded-xl p-3 flex items-start gap-2">
            <AlertCircle size={16} className="text-red-500 flex-shrink-0 mt-0.5" />
            <p className="text-sm text-red-600">{error}</p>
          </div>
        )}

        <div className="space-y-3 pt-2 pb-4">
          <Button
            fullWidth
            onClick={handleMarkComplete}
            disabled={step === 'submitting' || !proofPhoto}
          >
            {step === 'submitting' ? (
              <span className="flex items-center justify-center gap-2">
                <Loader2 size={16} className="animate-spin" />
                Envoi en cours…
              </span>
            ) : !proofPhoto ? (
              'Ajoutez une photo pour continuer'
            ) : (
              `Déclarer ${completionPct}% terminé`
            )}
          </Button>
          <button
            onClick={onReportIssue}
            disabled={step === 'submitting'}
            className="w-full px-6 py-3.5 border-2 border-red-200 rounded-xl font-semibold text-red-600 hover:bg-red-50 transition-all flex items-center justify-center gap-2 disabled:opacity-50 text-sm"
          >
            <AlertCircle size={16} />
            Signaler un problème
          </button>
        </div>
      </div>
    </div>
  );
}
