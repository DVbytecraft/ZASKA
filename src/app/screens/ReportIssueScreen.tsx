import { useState } from 'react';
import { ArrowLeft, AlertCircle, Loader2, CheckCircle2 } from 'lucide-react';
import { Button } from '../components/Button';
import { ProofPhotoUpload } from '../components/ProofPhotoUpload';
import { apiClient } from '@zaska/shared-services';

interface ReportIssueScreenProps {
  onBack: () => void;
  onSubmit: () => void;
  taskId?: string;
}

const ISSUE_CATEGORIES = [
  'Tâche non effectuée',
  'Travail de mauvaise qualité',
  'Prestataire absent',
  'Problème de paiement',
  'Problème de sécurité',
  'Autre',
];

export function ReportIssueScreen({ onBack, onSubmit, taskId }: ReportIssueScreenProps) {
  const [category, setCategory] = useState('');
  const [description, setDescription] = useState('');
  const [disputePhoto, setDisputePhoto] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const canSubmit = Boolean(category && description.trim().length >= 10 && disputePhoto);

  const handleSubmit = async () => {
    if (!canSubmit || !disputePhoto) return;
    setSubmitting(true);
    setError(null);
    try {
      const token = apiClient.getAccessToken();
      const baseUrl: string =
        (import.meta as { env?: Record<string, string> }).env?.VITE_API_URL ??
        'http://localhost:6969/api';

      const form = new FormData();
      if (taskId) form.append('task_id', taskId);
      form.append('category', category);
      form.append('description', description.trim());
      form.append('photo', disputePhoto);

      const res = await fetch(`${baseUrl}/support/tickets`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: form,
      });
      const json = await res.json();
      if (!res.ok) throw new Error(json.error ?? 'Échec de l\'envoi du signalement');

      setDone(true);
      setTimeout(onSubmit, 1800);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erreur lors de l\'envoi');
    } finally {
      setSubmitting(false);
    }
  };

  if (done) {
    return (
      <div className="h-full flex flex-col items-center justify-center gap-4 px-6 bg-white">
        <CheckCircle2 size={64} className="text-green-500" />
        <h3 className="text-xl font-bold text-gray-900 text-center">Signalement envoyé</h3>
        <p className="text-sm text-gray-500 text-center">
          Notre équipe examine votre signalement dans les 24 heures. Nous vous notifierons de la
          décision.
        </p>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col bg-white">
      <div className="px-6 pt-8 pb-4 border-b border-gray-200">
        <div className="flex items-center justify-between">
          <button
            onClick={onBack}
            className="p-2 -ml-2 hover:bg-gray-100 rounded-full transition-colors"
            disabled={submitting}
          >
            <ArrowLeft size={24} className="text-gray-700" />
          </button>
          <h2 className="text-xl font-semibold text-gray-900">Signaler un problème</h2>
          <div className="w-10" />
        </div>
      </div>

      <div className="flex-1 overflow-auto p-6">
        {taskId && (
          <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 mb-6 flex items-start gap-3">
            <AlertCircle size={20} className="text-blue-600 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-medium text-blue-900">Tâche ID : {taskId}</p>
              <p className="text-sm text-blue-700">
                Notre équipe examinera votre signalement dans les 24 heures
              </p>
            </div>
          </div>
        )}

        <div className="space-y-5">
          {/* Category */}
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-2">
              Catégorie du problème <span className="text-red-500">*</span>
            </label>
            <div className="grid grid-cols-2 gap-2">
              {ISSUE_CATEGORIES.map((cat) => (
                <button
                  key={cat}
                  onClick={() => setCategory(cat)}
                  className={`py-3 px-4 border-2 rounded-xl text-sm font-medium transition-all text-left ${
                    category === cat
                      ? 'border-[#6D28D9] bg-purple-50 text-[#6D28D9]'
                      : 'border-gray-200 text-gray-700 hover:border-gray-300'
                  }`}
                >
                  {cat}
                </button>
              ))}
            </div>
          </div>

          {/* Description */}
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-2">
              Description <span className="text-red-500">*</span>
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={5}
              className="w-full px-4 py-3 border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-[#6D28D9] focus:border-transparent resize-none"
              placeholder="Décrivez le problème en détail… (min. 10 caractères)"
            />
            {description.length > 0 && description.trim().length < 10 && (
              <p className="text-xs text-red-500 mt-1">
                Décrivez le problème plus précisément (min. 10 caractères)
              </p>
            )}
          </div>

          {/* Mandatory dispute photo */}
          <ProofPhotoUpload
            label="Photo de preuve pour le litige"
            hint="Pour contester le paiement, une photo est obligatoire. Elle sera examinée par notre équipe de médiation."
            required
            onFileChange={setDisputePhoto}
          />

          {error && (
            <div className="bg-red-50 border border-red-200 rounded-xl p-3 flex items-start gap-2">
              <AlertCircle size={16} className="text-red-500 flex-shrink-0 mt-0.5" />
              <p className="text-sm text-red-700">{error}</p>
            </div>
          )}
        </div>
      </div>

      <div className="p-6 border-t border-gray-200">
        {!disputePhoto && (
          <p className="text-xs text-amber-600 text-center mb-3">
            ⚠️ Une photo de preuve est requise pour soumettre un litige
          </p>
        )}
        <Button fullWidth onClick={handleSubmit} disabled={!canSubmit || submitting}>
          {submitting ? (
            <span className="flex items-center justify-center gap-2">
              <Loader2 size={16} className="animate-spin" />
              Envoi en cours…
            </span>
          ) : (
            'Envoyer le signalement'
          )}
        </Button>
      </div>
    </div>
  );
}
