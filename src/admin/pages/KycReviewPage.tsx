import { useEffect, useState } from 'react';
import { ShieldCheck, RefreshCw, Loader2, CheckCircle2, XCircle, Clock, Eye } from 'lucide-react';
import { DataTable } from '../components/DataTable';
import { SlidePanel } from '../components/SlidePanel';
import { adminApi, type AdminKycSubmission } from '../adminApi';

const STATUS_TABS = [
  { value: 'pending', label: 'En attente' },
  { value: 'approved', label: 'Approuvées' },
  { value: 'rejected', label: 'Rejetées' },
];

function StatusBadge({ status }: { status: string }) {
  if (status === 'approved') {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold bg-green-50 text-green-700 border border-green-100">
        <CheckCircle2 size={12} /> Approuvée
      </span>
    );
  }
  if (status === 'rejected') {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold bg-red-50 text-red-700 border border-red-100">
        <XCircle size={12} /> Rejetée
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-100">
      <Clock size={12} /> En attente
    </span>
  );
}

function KycDetailPanel({ submission, onClose, onDecision }: {
  submission: AdminKycSubmission | null;
  onClose: () => void;
  onDecision: () => void;
}) {
  const [rejectReason, setRejectReason] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => { setRejectReason(''); setError(''); }, [submission]);

  const handleApprove = async () => {
    if (!submission) return;
    setLoading(true);
    setError('');
    try {
      await adminApi.approveKyc(submission.id);
      onDecision();
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Échec');
    } finally {
      setLoading(false);
    }
  };

  const handleReject = async () => {
    if (!submission || !rejectReason.trim()) return;
    setLoading(true);
    setError('');
    try {
      await adminApi.rejectKyc(submission.id, rejectReason);
      onDecision();
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Échec');
    } finally {
      setLoading(false);
    }
  };

  const canDecide = submission?.status === 'pending';

  return (
    <SlidePanel
      open={!!submission}
      title="Détail KYC"
      subtitle={submission ? `Utilisateur ${submission.user_id.slice(0, 8)}` : undefined}
      onClose={onClose}
    >
      {submission && (
        <div className="divide-y divide-gray-100">
          <div className="px-6 py-5 space-y-3">
            <StatusBadge status={submission.status} />
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div>
                <p className="text-xs text-gray-500 mb-0.5">Soumis le</p>
                <p className="font-medium text-gray-900">{new Date(submission.created_at).toLocaleDateString('fr-FR')}</p>
              </div>
              {submission.reviewed_by && (
                <div>
                  <p className="text-xs text-gray-500 mb-0.5">Révisé par</p>
                  <p className="font-medium text-gray-900 truncate">{submission.reviewed_by.slice(0, 12)}</p>
                </div>
              )}
            </div>
            {submission.reviewer_note && (
              <div className="bg-red-50 rounded-xl p-3">
                <p className="text-xs text-red-600 font-medium">Motif de rejet</p>
                <p className="text-sm text-red-700 mt-1">{submission.reviewer_note}</p>
              </div>
            )}
          </div>

          {/* Document previews */}
          <div className="px-6 py-5 space-y-4">
            <h4 className="text-sm font-bold text-gray-900">Documents fournis</h4>
            {submission.id_document_url ? (
              <div>
                <p className="text-xs text-gray-500 mb-1">Pièce d'identité</p>
                <a
                  href={submission.id_document_url}
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center gap-2 text-sm text-[#6D28D9] font-medium hover:underline"
                >
                  <Eye size={14} /> Voir le document
                </a>
              </div>
            ) : (
              <p className="text-sm text-gray-400 italic">Aucun document uploadé</p>
            )}
            {submission.selfie_url && (
              <div>
                <p className="text-xs text-gray-500 mb-1">Selfie</p>
                <a
                  href={submission.selfie_url}
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center gap-2 text-sm text-[#6D28D9] font-medium hover:underline"
                >
                  <Eye size={14} /> Voir le selfie
                </a>
              </div>
            )}
          </div>

          {/* Actions */}
          {canDecide && (
            <div className="px-6 py-5 space-y-3">
              <h4 className="text-sm font-bold text-gray-900">Décision</h4>

              <div>
                <label className="text-xs text-gray-500 font-medium block mb-1">
                  Motif (obligatoire pour rejet)
                </label>
                <textarea
                  rows={3}
                  value={rejectReason}
                  onChange={(e) => setRejectReason(e.target.value)}
                  placeholder="Documents flous, visage non visible..."
                  className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                />
              </div>

              {error && <p className="text-sm text-red-500">{error}</p>}

              <div className="flex gap-3">
                <button
                  onClick={handleApprove}
                  disabled={loading}
                  className="flex-1 py-2.5 rounded-xl bg-green-600 text-white text-sm font-semibold hover:bg-green-700 disabled:opacity-50 transition-colors flex items-center justify-center gap-1.5"
                >
                  {loading ? <Loader2 size={14} className="animate-spin" /> : <CheckCircle2 size={14} />}
                  Approuver
                </button>
                <button
                  onClick={handleReject}
                  disabled={loading || !rejectReason.trim()}
                  className="flex-1 py-2.5 rounded-xl bg-red-600 text-white text-sm font-semibold hover:bg-red-700 disabled:opacity-50 transition-colors flex items-center justify-center gap-1.5"
                >
                  {loading ? <Loader2 size={14} className="animate-spin" /> : <XCircle size={14} />}
                  Rejeter
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </SlidePanel>
  );
}

export function KycReviewPage() {
  const [statusFilter, setStatusFilter] = useState('pending');
  const [submissions, setSubmissions] = useState<AdminKycSubmission[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<AdminKycSubmission | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const data = await adminApi.getKycSubmissions(statusFilter);
      setSubmissions(data);
    } catch {
      setSubmissions([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void load(); }, [statusFilter]);

  const columns = [
    {
      key: 'user_id',
      label: 'Utilisateur',
      render: (_: unknown, row: AdminKycSubmission) => (
        <span className="font-mono text-xs text-gray-600">{row.user_id.slice(0, 12)}…</span>
      ),
    },
    {
      key: 'status',
      label: 'Statut',
      render: (_: unknown, row: AdminKycSubmission) => <StatusBadge status={row.status} />,
    },
    {
      key: 'created_at',
      label: 'Soumis le',
      render: (_: unknown, row: AdminKycSubmission) => (
        <span className="text-sm text-gray-600">{new Date(row.created_at).toLocaleDateString('fr-FR')}</span>
      ),
    },
    {
      key: 'reviewer_note',
      label: 'Note',
      render: (_: unknown, row: AdminKycSubmission) => (
        <span className="text-xs text-gray-500 truncate max-w-[140px] block">
          {row.reviewer_note ?? '—'}
        </span>
      ),
    },
    {
      key: 'actions',
      label: '',
      render: (_: unknown, row: AdminKycSubmission) => (
        <button
          onClick={() => setSelected(row)}
          className="px-3 py-1.5 rounded-lg text-xs font-medium text-[#6D28D9] bg-purple-50 hover:bg-purple-100 transition-colors flex items-center gap-1"
        >
          <Eye size={12} /> Réviser
        </button>
      ),
    },
  ];

  return (
    <div className="p-6 space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Vérification KYC</h2>
          <p className="text-sm text-gray-600">Examinez et validez les documents d'identité</p>
        </div>
        <button
          onClick={load}
          className="flex items-center gap-2 px-4 py-2 border border-gray-200 rounded-xl text-sm font-medium hover:bg-gray-50 transition-colors"
        >
          <RefreshCw size={15} />
          Actualiser
        </button>
      </div>

      {/* Status tabs */}
      <div className="flex gap-2">
        {STATUS_TABS.map(tab => (
          <button
            key={tab.value}
            onClick={() => setStatusFilter(tab.value)}
            className={`px-4 py-2 rounded-xl text-sm font-semibold transition-all border-2 ${
              statusFilter === tab.value
                ? 'border-[#6D28D9] bg-[#6D28D9] text-white'
                : 'border-gray-200 text-gray-600 hover:border-[#6D28D9]'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* KPI strip */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-amber-50 border border-amber-100 rounded-xl p-4 text-center">
          <p className="text-2xl font-extrabold text-amber-700">
            {loading ? '—' : submissions.filter(s => s.status === 'pending').length}
          </p>
          <p className="text-xs text-amber-600 font-medium mt-1">En attente</p>
        </div>
        <div className="bg-green-50 border border-green-100 rounded-xl p-4 text-center">
          <p className="text-2xl font-extrabold text-green-700">
            {loading ? '—' : submissions.filter(s => s.status === 'approved').length}
          </p>
          <p className="text-xs text-green-600 font-medium mt-1">Approuvées</p>
        </div>
        <div className="bg-red-50 border border-red-100 rounded-xl p-4 text-center">
          <p className="text-2xl font-extrabold text-red-700">
            {loading ? '—' : submissions.filter(s => s.status === 'rejected').length}
          </p>
          <p className="text-xs text-red-600 font-medium mt-1">Rejetées</p>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-48">
          <Loader2 size={32} className="animate-spin text-[#6D28D9]" />
        </div>
      ) : submissions.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-48 gap-3 text-gray-400">
          <ShieldCheck size={36} className="text-gray-300" />
          <p className="text-sm font-medium">Aucune soumission {statusFilter === 'pending' ? 'en attente' : statusFilter === 'approved' ? 'approuvée' : 'rejetée'}</p>
        </div>
      ) : (
        <DataTable columns={columns} data={submissions} />
      )}

      <KycDetailPanel
        submission={selected}
        onClose={() => setSelected(null)}
        onDecision={load}
      />
    </div>
  );
}
