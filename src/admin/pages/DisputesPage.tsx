import { useEffect, useState, useMemo } from 'react';
import { AlertTriangle, RefreshCw, Eye, Loader2, MessageSquare, ChevronDown } from 'lucide-react';
import { DataTable } from '../components/DataTable';
import { SlidePanel } from '../components/SlidePanel';
import { DisputeStatusBadge } from '../components/StatusBadge';
import { adminApi, type AdminDispute } from '../adminApi';

const RESOLUTION_OPTIONS = [
  { value: 'in_favor_reporter', label: '✅ En faveur du plaignant', desc: 'Le plaignant a raison, remboursement effectué' },
  { value: 'in_favor_respondent', label: '✅ En faveur du défendeur', desc: 'Le défendeur a raison, escrow libéré' },
  { value: 'partial_refund', label: '⚖️ Remboursement partiel', desc: 'Partage équitable du montant' },
  { value: 'dismissed', label: '🚫 Rejeté', desc: 'Litige non fondé ou insuffisant' },
];

function DisputeDetailPanel({ dispute, onClose, onResolved }: {
  dispute: AdminDispute | null;
  onClose: () => void;
  onResolved: () => void;
}) {
  const [resolution, setResolution] = useState('');
  const [note, setNote] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleResolve = async () => {
    if (!dispute || !resolution || !note.trim()) return;
    setLoading(true);
    setError('');
    try {
      await adminApi.resolveDispute(dispute.id, resolution, note);
      onResolved();
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Échec de la résolution');
    } finally {
      setLoading(false);
    }
  };

  const canResolve = dispute?.status !== 'resolved' && dispute?.status !== 'closed';
  const selected = RESOLUTION_OPTIONS.find(o => o.value === resolution);

  return (
    <SlidePanel
      open={!!dispute}
      title="Détail du litige"
      subtitle={dispute ? `#${dispute.id.slice(0, 8)} · ${dispute.status}` : undefined}
      onClose={onClose}
    >
      {dispute && (
        <div className="divide-y divide-gray-100">
          {/* Case overview */}
          <div className="px-6 py-5">
            <DisputeStatusBadge status={dispute.status} size="md" />
            <h3 className="text-base font-bold text-gray-900 mt-3 mb-4">{dispute.reason}</h3>

            {dispute.description && (
              <div className="bg-gray-50 rounded-xl p-4 mb-4">
                <p className="text-sm text-gray-700">{dispute.description}</p>
              </div>
            )}

            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-1">Plaignant</p>
                <p className="font-medium text-gray-900">{dispute.reporter_name ?? dispute.reporter_id.slice(0, 12)}</p>
              </div>
              {dispute.respondent_id && (
                <div>
                  <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-1">Défendeur</p>
                  <p className="font-medium text-gray-900">{dispute.respondent_name ?? dispute.respondent_id.slice(0, 12)}</p>
                </div>
              )}
              <div>
                <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-1">Tâche</p>
                <p className="font-medium text-gray-900">{dispute.task_title ?? dispute.task_id.slice(0, 12) + '…'}</p>
              </div>
              <div>
                <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-1">Date</p>
                <p className="font-medium text-gray-900">{new Date(dispute.created_at).toLocaleDateString('fr-FR')}</p>
              </div>
            </div>
          </div>

          {/* Already resolved */}
          {!canResolve && (
            <div className="px-6 py-5">
              <div className="bg-green-50 border border-green-200 rounded-xl p-4">
                <p className="text-sm font-semibold text-green-800">Litige résolu</p>
                <p className="text-sm text-green-700 mt-1">Décision : {dispute.resolution?.replace(/_/g, ' ')}</p>
                {dispute.resolution_note && (
                  <p className="text-sm text-green-700 mt-1 italic">{dispute.resolution_note}</p>
                )}
              </div>
            </div>
          )}

          {/* Resolution form */}
          {canResolve && (
            <div className="px-6 py-5 space-y-4">
              <h3 className="text-sm font-bold text-gray-900 flex items-center gap-2">
                <MessageSquare size={15} className="text-[#6D28D9]" />
                Résoudre le litige
              </h3>

              <div className="space-y-2">
                {RESOLUTION_OPTIONS.map((opt) => (
                  <label
                    key={opt.value}
                    className={`flex items-start gap-3 p-3 rounded-xl border-2 cursor-pointer transition-all ${
                      resolution === opt.value ? 'border-[#6D28D9] bg-purple-50' : 'border-gray-200 hover:border-gray-300'
                    }`}
                  >
                    <input
                      type="radio"
                      name="resolution"
                      value={opt.value}
                      checked={resolution === opt.value}
                      onChange={() => setResolution(opt.value)}
                      className="mt-0.5 accent-[#6D28D9]"
                    />
                    <div>
                      <p className="text-sm font-semibold text-gray-900">{opt.label}</p>
                      <p className="text-xs text-gray-500">{opt.desc}</p>
                    </div>
                  </label>
                ))}
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1.5">
                  Note de décision <span className="text-red-500">*</span>
                </label>
                <textarea
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  placeholder="Expliquez votre décision en détail..."
                  rows={4}
                  className="w-full px-3 py-2.5 border-2 border-gray-200 rounded-xl text-sm resize-none focus:border-[#6D28D9] focus:outline-none"
                />
              </div>

              {error && <p className="text-xs text-red-600 bg-red-50 px-3 py-2 rounded-xl">{error}</p>}

              <button
                onClick={handleResolve}
                disabled={!resolution || !note.trim() || loading}
                className="w-full py-3 rounded-xl bg-[#6D28D9] text-white text-sm font-bold hover:bg-[#5B21B6] disabled:opacity-50 transition-colors flex items-center justify-center gap-2"
              >
                {loading ? <Loader2 size={14} className="animate-spin" /> : null}
                Résoudre le litige
              </button>
            </div>
          )}
        </div>
      )}
    </SlidePanel>
  );
}

export function DisputesPage() {
  const [disputes, setDisputes] = useState<AdminDispute[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState('');
  const [selectedDispute, setSelectedDispute] = useState<AdminDispute | null>(null);

  const load = () => {
    setLoading(true);
    setError(null);
    adminApi.getDisputes(statusFilter || undefined)
      .then(setDisputes)
      .catch((e) => setError(e instanceof Error ? e.message : 'Erreur'))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, [statusFilter]);

  const stats = useMemo(() => ({
    total: disputes.length,
    open: disputes.filter(d => d.status === 'open').length,
    under_review: disputes.filter(d => d.status === 'under_review').length,
    resolved: disputes.filter(d => d.status === 'resolved').length,
  }), [disputes]);

  const STATUS_TABS = [
    { value: '', label: 'Tous', count: stats.total },
    { value: 'open', label: '🔴 Ouverts', count: stats.open },
    { value: 'under_review', label: '🟡 En examen', count: stats.under_review },
    { value: 'resolved', label: '✅ Résolus', count: stats.resolved },
  ];

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Litiges</h2>
          <p className="text-sm text-gray-600">Résolution des conflits et médiations</p>
        </div>
        <button onClick={load} className="flex items-center gap-2 px-4 py-2 border border-gray-200 rounded-xl text-sm font-medium hover:bg-gray-50 transition-colors">
          <RefreshCw size={15} />
          Actualiser
        </button>
      </div>

      {stats.open > 0 && !loading && (
        <div className="flex items-center gap-3 bg-red-50 border border-red-200 rounded-xl px-4 py-3">
          <AlertTriangle size={18} className="text-red-600 flex-shrink-0" />
          <p className="text-sm text-red-800 font-medium">
            {stats.open} litige{stats.open > 1 ? 's' : ''} ouvert{stats.open > 1 ? 's' : ''} en attente de traitement.
          </p>
        </div>
      )}

      {/* Status tabs */}
      <div className="flex items-center gap-1 bg-gray-100 rounded-xl p-1">
        {STATUS_TABS.map((tab) => (
          <button
            key={tab.value}
            onClick={() => setStatusFilter(tab.value)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              statusFilter === tab.value ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            {tab.label}
            <span className={`px-1.5 py-0.5 rounded-full text-xs font-bold ${
              statusFilter === tab.value ? 'bg-[#6D28D9] text-white' : 'bg-gray-200 text-gray-600'
            }`}>
              {loading ? '—' : tab.count}
            </span>
          </button>
        ))}
      </div>

      {loading ? (
        <div className="space-y-3">{[1,2,3].map(i => <div key={i} className="h-16 bg-gray-100 rounded-xl animate-pulse" />)}</div>
      ) : error ? (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-5 text-center">
          <AlertTriangle size={32} className="text-amber-400 mx-auto mb-2" />
          <p className="text-sm text-amber-800 font-medium">{error}</p>
          <p className="text-xs text-amber-600 mt-1">Le système de litiges sera disponible avec l'implémentation du backend.</p>
          <button onClick={load} className="mt-3 text-sm font-semibold text-amber-700 underline">Réessayer</button>
        </div>
      ) : disputes.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <div className="w-16 h-16 bg-green-100 rounded-2xl flex items-center justify-center mb-4">
            <AlertTriangle size={28} className="text-green-500" />
          </div>
          <p className="text-base font-semibold text-gray-700">Aucun litige{statusFilter ? ` avec le statut "${statusFilter}"` : ''}</p>
          <p className="text-sm text-gray-400 mt-1">La plateforme fonctionne bien.</p>
        </div>
      ) : (
        <DataTable
          columns={[
            {
              key: 'reason', label: 'Litige',
              render: (v, row) => {
                const d = row as AdminDispute;
                return (
                  <div>
                    <p className="font-semibold text-gray-900 text-sm">{v as string}</p>
                    <p className="text-xs text-gray-400">{d.task_title ?? `Tâche ${d.task_id.slice(0, 8)}`}</p>
                  </div>
                );
              }
            },
            {
              key: 'reporter_name', label: 'Plaignant',
              render: (v, row) => {
                const d = row as AdminDispute;
                return (v as string | undefined) ?? d.reporter_id.slice(0, 12) + '…';
              }
            },
            { key: 'status', label: 'Statut', render: (v) => <DisputeStatusBadge status={v as string} /> },
            { key: 'created_at', label: 'Ouvert le', render: (v) => new Date(v as string).toLocaleDateString('fr-FR') },
            {
              key: 'id', label: 'Action',
              render: (_, row) => (
                <button
                  onClick={(e) => { e.stopPropagation(); setSelectedDispute(row as AdminDispute); }}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#6D28D9]/10 text-[#6D28D9] text-xs font-semibold hover:bg-[#6D28D9]/20 transition-colors"
                >
                  <Eye size={12} /> Traiter
                </button>
              )
            },
          ]}
          data={disputes}
          onRowClick={(row) => setSelectedDispute(row as AdminDispute)}
        />
      )}

      <DisputeDetailPanel
        dispute={selectedDispute}
        onClose={() => setSelectedDispute(null)}
        onResolved={() => { load(); }}
      />
    </div>
  );
}
