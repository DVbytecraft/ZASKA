import { useEffect, useState } from 'react';
import { Button } from '../components/Button';
import { Card } from '../components/Card';
import { Avatar } from '../components/Avatar';
import { taskService } from '@zaska/shared-services';
import type { Task, TaskApplication } from '@zaska/shared-services';
import { ArrowLeft, Star } from 'lucide-react';

interface ApplicantsScreenProps {
  taskId: string;
  onBack: () => void;
  onSelectTasker: () => void;
  onNegotiate?: (taskerName: string, originalPrice: number, proposedPrice: number) => void;
}

export function ApplicantsScreen({ taskId, onBack, onSelectTasker, onNegotiate }: ApplicantsScreenProps) {
  const [task, setTask] = useState<Task | null>(null);
  const [applicants, setApplicants] = useState<TaskApplication[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [accepting, setAccepting] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    Promise.all([
      taskService.getTask(taskId),
      taskService.listApplications(taskId).catch(() => [] as TaskApplication[]),
    ])
      .then(([t, apps]) => {
        if (cancelled) return;
        setTask(t);
        setApplicants(apps);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : 'Impossible de charger les candidatures');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [taskId]);

  const handleAccept = async (applicant: TaskApplication) => {
    setAccepting(applicant.id);
    try {
      await taskService.acceptApplicant(taskId, applicant.taskerId);
      onSelectTasker();
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Impossible d\'accepter le prestataire');
    } finally {
      setAccepting(null);
    }
  };

  return (
    <div className="h-full flex flex-col bg-gray-50">
      <div className="px-6 pt-8 pb-4 bg-white border-b border-gray-200">
        <div className="flex items-center gap-3 mb-3">
          <button onClick={onBack} className="p-2 -ml-2 hover:bg-gray-100 rounded-full transition-colors">
            <ArrowLeft size={24} className="text-gray-700" />
          </button>
          <div>
            <h2 className="text-2xl font-bold text-gray-900">Candidatures</h2>
            <p className="text-sm text-gray-500">
              {loading ? 'Chargement…' : `${applicants.length} prestataire${applicants.length !== 1 ? 's' : ''} a postulé`}
            </p>
          </div>
        </div>
        {task && (
          <p className="text-sm text-gray-600 font-medium truncate">
            {task.title || task.description.slice(0, 60)}
          </p>
        )}
      </div>

      <div className="flex-1 overflow-auto px-6 py-4 space-y-3">
        {loading && (
          <div className="space-y-3">
            {[1, 2].map((i) => (
              <div key={i} className="h-40 bg-gray-200 rounded-2xl animate-pulse" />
            ))}
          </div>
        )}

        {error && !loading && (
          <div className="bg-red-50 border border-red-100 rounded-2xl p-4 text-center">
            <p className="text-sm text-red-600">{error}</p>
          </div>
        )}

        {!loading && !error && applicants.length === 0 && (
          <div className="bg-gray-100 rounded-2xl p-8 text-center">
            <p className="text-sm text-gray-500 mb-1">Aucune candidature pour l'instant.</p>
            <p className="text-xs text-gray-400">Les prestataires qui postulent apparaîtront ici.</p>
          </div>
        )}

        {!loading && !error && applicants.map((applicant) => (
          <Card key={applicant.id} className="hover:shadow-xl transition-all">
            <div className="flex items-start gap-3 mb-4">
              <Avatar name={applicant.taskerName ?? applicant.taskerId.slice(0, 8)} size="lg" />
              <div className="flex-1 min-w-0">
                <h4 className="font-semibold text-gray-900 mb-1">
                  {applicant.taskerName ?? `Prestataire ${applicant.taskerId.slice(0, 8)}`}
                </h4>
                {applicant.taskerRating != null && (
                  <div className="flex items-center gap-2 text-sm mb-2">
                    <div className="flex items-center gap-1">
                      <Star size={14} className="fill-amber-400 text-amber-400" />
                      <span className="font-semibold text-gray-900">{applicant.taskerRating.toFixed(1)}</span>
                      {applicant.taskerReviews != null && (
                        <span className="text-gray-500">({applicant.taskerReviews})</span>
                      )}
                    </div>
                  </div>
                )}
                <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
                  applicant.status === 'pending' ? 'bg-yellow-50 text-yellow-700' :
                  applicant.status === 'accepted' ? 'bg-green-50 text-green-700' :
                  'bg-gray-100 text-gray-600'
                }`}>
                  {applicant.status === 'pending' ? 'En attente' : applicant.status === 'accepted' ? 'Accepté' : 'Refusé'}
                </span>
              </div>
            </div>

            {applicant.proposedPrice != null && (
              <div className="bg-gray-50 rounded-xl p-3 mb-3">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-sm text-gray-600">Prix proposé</span>
                </div>
                <span className="text-2xl font-bold text-gray-900">
                  {applicant.currency} {applicant.proposedPrice.toFixed(2)}
                </span>
              </div>
            )}

            {applicant.status === 'pending' && (
              <div className="flex gap-2">
                <Button
                  fullWidth
                  onClick={() => handleAccept(applicant)}
                  disabled={accepting === applicant.id}
                >
                  {accepting === applicant.id ? 'Acceptation…' : 'Sélectionner le prestataire'}
                </Button>
                {applicant.proposedPrice != null && onNegotiate && (
                  <button
                    onClick={() => onNegotiate(
                      applicant.taskerName ?? applicant.taskerId.slice(0, 8),
                      task?.price ? Number(task.price) : 0,
                      applicant.proposedPrice ?? 0,
                    )}
                    className="px-4 py-2 rounded-xl border-2 border-[#6D28D9] text-[#6D28D9] font-semibold text-sm whitespace-nowrap hover:bg-purple-50 transition-colors"
                  >
                    Négocier
                  </button>
                )}
              </div>
            )}
          </Card>
        ))}
      </div>
    </div>
  );
}
