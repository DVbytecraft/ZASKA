import { useState, useEffect } from 'react';
import { Button } from '../components/Button';
import { Card } from '../components/Card';
import { taskService } from '@zaska/shared-services';
import type { TaskApplication } from '@zaska/shared-services';
import { ArrowLeft, CheckCircle2, Clock, XCircle, Loader2 } from 'lucide-react';

interface TaskerApplyScreenProps {
  taskId: string;
  taskBudget?: number;
  taskCurrency?: string;
  onBack: () => void;
  onSubmit: () => void;
}

// ── Application status card ───────────────────────────────────────────────────
function ApplicationStatusCard({
  app,
  onBack,
}: {
  app: TaskApplication;
  onBack: () => void;
}) {
  const isPending = app.status === 'pending';
  const isAccepted = app.status === 'accepted';

  return (
    <div className="h-full flex flex-col bg-gray-50">
      <div className="px-6 pt-8 pb-4 bg-white border-b border-gray-200">
        <div className="flex items-center gap-3">
          <button onClick={onBack} className="p-2 -ml-2 hover:bg-gray-100 rounded-full transition-colors">
            <ArrowLeft size={24} className="text-gray-700" />
          </button>
          <h2 className="text-2xl font-bold text-gray-900">Ma candidature</h2>
        </div>
      </div>

      <div className="flex-1 flex flex-col items-center justify-center px-6 gap-6">
        {/* Status icon */}
        <div className={`w-24 h-24 rounded-full flex items-center justify-center ${
          isAccepted ? 'bg-green-100' : isPending ? 'bg-amber-100' : 'bg-red-100'
        }`}>
          {isAccepted ? (
            <CheckCircle2 size={48} className="text-green-600" />
          ) : isPending ? (
            <Clock size={48} className="text-amber-500" />
          ) : (
            <XCircle size={48} className="text-red-500" />
          )}
        </div>

        {/* Status message */}
        <div className="text-center">
          <h3 className={`text-xl font-bold mb-2 ${
            isAccepted ? 'text-green-700' : isPending ? 'text-amber-700' : 'text-red-700'
          }`}>
            {isAccepted ? 'Candidature acceptée !' : isPending ? 'Candidature envoyée' : 'Candidature refusée'}
          </h3>
          <p className="text-sm text-gray-500 max-w-xs">
            {isAccepted
              ? 'Le client vous a sélectionné. Accédez à la tâche pour commencer et communiquer.'
              : isPending
              ? 'Votre candidature est en cours d\'examen. Le client vous répondra prochainement.'
              : 'Le client n\'a pas retenu votre candidature cette fois-ci. Continuez à explorer d\'autres tâches.'}
          </p>
        </div>

        {/* Application details */}
        <Card className="w-full">
          {app.proposedPrice != null && (
            <div className="flex items-center justify-between py-2 border-b border-gray-100">
              <span className="text-sm text-gray-500">Prix proposé</span>
              <span className="text-sm font-semibold text-gray-900">
                {Number(app.proposedPrice).toLocaleString()} {app.currency}
              </span>
            </div>
          )}
          {app.message && (
            <div className="py-2 border-b border-gray-100">
              <p className="text-xs text-gray-400 mb-1">Votre message</p>
              <p className="text-sm text-gray-700">{app.message}</p>
            </div>
          )}
          <div className="flex items-center justify-between py-2">
            <span className="text-sm text-gray-500">Statut</span>
            <span className={`text-xs font-semibold px-2.5 py-1 rounded-lg ${
              isAccepted ? 'bg-green-50 text-green-700' :
              isPending ? 'bg-amber-50 text-amber-700' :
              'bg-red-50 text-red-700'
            }`}>
              {isAccepted ? 'Acceptée' : isPending ? 'En attente' : 'Refusée'}
            </span>
          </div>
          <div className="flex items-center justify-between pt-2">
            <span className="text-sm text-gray-500">Soumise le</span>
            <span className="text-xs text-gray-400">
              {new Date(app.createdAt).toLocaleDateString('fr-FR')}
            </span>
          </div>
        </Card>

        <button onClick={onBack} className="text-sm font-medium text-[#6D28D9] hover:underline">
          Retour aux tâches
        </button>
      </div>
    </div>
  );
}

// ── Main screen ───────────────────────────────────────────────────────────────
export function TaskerApplyScreen({
  taskId,
  taskBudget: budgetProp,
  taskCurrency: currencyProp,
  onBack,
  onSubmit,
}: TaskerApplyScreenProps) {
  const [applyType, setApplyType] = useState<'accept' | 'propose'>('accept');
  const [proposedPrice, setProposedPrice] = useState('');
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [taskBudget, setTaskBudget] = useState<number>(budgetProp ?? 0);
  const [taskCurrency, setTaskCurrency] = useState<string>(currencyProp ?? 'XOF');

  // Check for existing application
  const [existingApp, setExistingApp] = useState<TaskApplication | null>(null);
  const [checkingApp, setCheckingApp] = useState(true);

  useEffect(() => {
    taskService.getMyApplications()
      .then((apps) => {
        const found = apps.find((a) => a.taskId === taskId) ?? null;
        setExistingApp(found);
      })
      .catch(() => {})
      .finally(() => setCheckingApp(false));
  }, [taskId]);

  useEffect(() => {
    if (budgetProp !== undefined) return;
    taskService.getTask(taskId)
      .then((t) => {
        setTaskBudget(Number(t.price));
        setTaskCurrency(t.currency);
      })
      .catch(() => {});
  }, [taskId, budgetProp]);

  const handleSubmit = async () => {
    setLoading(true);
    setError(null);
    try {
      await taskService.applyTask(taskId, {
        proposed_price: applyType === 'propose' && proposedPrice ? Number(proposedPrice) : undefined,
        currency: taskCurrency,
        message: message || undefined,
      });
      onSubmit();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Impossible de soumettre la candidature');
    } finally {
      setLoading(false);
    }
  };

  const canSubmit = applyType === 'accept' || (proposedPrice.length > 0 && Number(proposedPrice) > 0);

  // Loading existing application check
  if (checkingApp) {
    return (
      <div className="h-full flex flex-col bg-gray-50">
        <div className="px-6 pt-8 pb-4 bg-white border-b border-gray-200">
          <div className="flex items-center gap-3">
            <button onClick={onBack} className="p-2 -ml-2 hover:bg-gray-100 rounded-full transition-colors">
              <ArrowLeft size={24} className="text-gray-700" />
            </button>
            <h2 className="text-2xl font-bold text-gray-900">Postuler</h2>
          </div>
        </div>
        <div className="flex-1 flex items-center justify-center">
          <Loader2 size={32} className="animate-spin text-[#6D28D9]" />
        </div>
      </div>
    );
  }

  // Already applied — show status card
  if (existingApp) {
    return <ApplicationStatusCard app={existingApp} onBack={onBack} />;
  }

  // Normal apply form
  return (
    <div className="h-full flex flex-col bg-gray-50">
      <div className="px-6 pt-8 pb-4 bg-white border-b border-gray-200">
        <div className="flex items-center gap-3">
          <button onClick={onBack} className="p-2 -ml-2 hover:bg-gray-100 rounded-full transition-colors">
            <ArrowLeft size={24} className="text-gray-700" />
          </button>
          <div>
            <h2 className="text-2xl font-bold text-gray-900">Postuler à la tâche</h2>
            <p className="text-sm text-gray-500">Choisissez votre option de tarif</p>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-auto px-6 py-6">
        <div className="space-y-3 mb-6">
          {/* Accept budget */}
          <div
            onClick={() => setApplyType('accept')}
            className={`p-4 rounded-xl border-2 cursor-pointer transition-all ${
              applyType === 'accept'
                ? 'border-[#6D28D9] bg-[#6D28D9]/5 shadow-md'
                : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
            }`}
          >
            <div className="flex items-center justify-between mb-2">
              <h4 className="font-semibold text-gray-900">Accepter le budget du client</h4>
              <div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center ${
                applyType === 'accept' ? 'border-[#6D28D9]' : 'border-gray-300'
              }`}>
                {applyType === 'accept' && <div className="w-3 h-3 bg-[#6D28D9] rounded-full" />}
              </div>
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-3xl font-bold text-gray-900">{taskCurrency} {Number(taskBudget).toLocaleString()}</span>
            </div>
            <p className="text-xs text-green-600 mt-2 font-medium">✓ Recommandé — augmente vos chances de sélection</p>
          </div>

          {/* Propose price */}
          <div
            onClick={() => setApplyType('propose')}
            className={`p-4 rounded-xl border-2 cursor-pointer transition-all ${
              applyType === 'propose'
                ? 'border-[#6D28D9] bg-[#6D28D9]/5 shadow-md'
                : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
            }`}
          >
            <div className="flex items-center justify-between mb-3">
              <h4 className="font-semibold text-gray-900">Proposer votre prix</h4>
              <div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center ${
                applyType === 'propose' ? 'border-[#6D28D9]' : 'border-gray-300'
              }`}>
                {applyType === 'propose' && <div className="w-3 h-3 bg-[#6D28D9] rounded-full" />}
              </div>
            </div>
            {applyType === 'propose' && (
              <div className="relative">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-xl text-gray-400 font-semibold">
                  {taskCurrency}
                </span>
                <input
                  type="number"
                  placeholder="0"
                  value={proposedPrice}
                  onChange={(e) => setProposedPrice(e.target.value)}
                  className="w-full pl-14 pr-4 py-3 text-xl font-semibold rounded-xl border-2 border-gray-200 focus:border-[#6D28D9] focus:outline-none transition-colors bg-white"
                />
              </div>
            )}
            <p className="text-xs text-amber-600 mt-2 font-medium">⚠ Le client peut refuser si le prix est trop différent</p>
          </div>
        </div>

        {/* Message */}
        <div className="mb-4">
          <label className="text-sm font-medium text-gray-700 mb-2 block">Message (optionnel)</label>
          <textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="Présentez-vous ou expliquez pourquoi vous êtes le meilleur candidat..."
            rows={3}
            maxLength={500}
            className="w-full px-4 py-3 rounded-xl border-2 border-gray-200 focus:border-[#6D28D9] focus:outline-none text-sm resize-none"
          />
        </div>

        {error && (
          <div className="bg-red-50 border border-red-100 rounded-xl p-3 mb-4">
            <p className="text-sm text-red-600">{error}</p>
          </div>
        )}

        <Card className="bg-blue-50 border-blue-100">
          <h4 className="font-semibold text-blue-900 mb-2">Conseils pour postuler</h4>
          <ul className="text-sm text-blue-900 space-y-1">
            <li>• Accepter le budget augmente vos chances de sélection</li>
            <li>• Vous ne pouvez postuler qu'une seule fois par tâche</li>
            <li>• Le client voit votre profil en examinant les candidatures</li>
          </ul>
        </Card>
      </div>

      <div className="px-6 py-4 bg-white border-t border-gray-200">
        <Button fullWidth onClick={handleSubmit} disabled={!canSubmit || loading}>
          {loading ? 'Envoi en cours...' : 'Soumettre ma candidature'}
        </Button>
      </div>
    </div>
  );
}
