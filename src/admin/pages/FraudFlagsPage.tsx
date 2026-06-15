import { useEffect, useState } from 'react';
import { ShieldAlert, RefreshCw, Loader2, AlertTriangle, Zap, Trash2, CheckCircle2 } from 'lucide-react';
import { adminApi, type AdminFraudFlags } from '../adminApi';

function ConfirmClearModal({ userId, onConfirm, onCancel, loading }: {
  userId: string;
  onConfirm: () => void;
  onCancel: () => void;
  loading: boolean;
}) {
  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl p-6 w-full max-w-sm shadow-2xl">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-xl bg-amber-50 flex items-center justify-center flex-shrink-0">
            <AlertTriangle size={20} className="text-amber-500" />
          </div>
          <div>
            <h3 className="font-bold text-gray-900">Lever les flags ?</h3>
            <p className="text-xs text-gray-500">Utilisateur {userId.slice(0, 12)}…</p>
          </div>
        </div>
        <p className="text-sm text-gray-600 mb-5">
          Cela supprimera tous les flags fraude (blocage payout + cycle rapide) pour cet utilisateur.
          Cette action ne peut pas être annulée.
        </p>
        <div className="flex gap-3">
          <button
            onClick={onCancel}
            disabled={loading}
            className="flex-1 py-2.5 rounded-xl border-2 border-gray-200 text-sm font-semibold text-gray-700 hover:bg-gray-50 disabled:opacity-50 transition-colors"
          >
            Annuler
          </button>
          <button
            onClick={onConfirm}
            disabled={loading}
            className="flex-1 py-2.5 rounded-xl bg-amber-500 text-white text-sm font-semibold hover:bg-amber-600 disabled:opacity-50 transition-colors flex items-center justify-center gap-1.5"
          >
            {loading ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />}
            Lever les flags
          </button>
        </div>
      </div>
    </div>
  );
}

export function FraudFlagsPage() {
  const [flags, setFlags] = useState<AdminFraudFlags | null>(null);
  const [loading, setLoading] = useState(true);
  const [confirmUserId, setConfirmUserId] = useState<string | null>(null);
  const [clearing, setClearing] = useState(false);
  const [cleared, setCleared] = useState<string[]>([]);

  const load = async () => {
    setLoading(true);
    try {
      const data = await adminApi.getFraudFlags();
      setFlags(data);
    } catch {
      setFlags({ payout_blocked: [], rapid_cycle_candidates: [] });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void load(); }, []);

  const handleClear = async () => {
    if (!confirmUserId) return;
    setClearing(true);
    try {
      await adminApi.clearFraudFlags(confirmUserId);
      setCleared(prev => [...prev, confirmUserId]);
      setConfirmUserId(null);
      await load();
    } catch (e) {
      console.error(e);
    } finally {
      setClearing(false);
    }
  };

  const totalFlags = (flags?.payout_blocked.length ?? 0) + (flags?.rapid_cycle_candidates.length ?? 0);

  return (
    <div className="p-4 sm:p-6 space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Flags fraude</h2>
          <p className="text-sm text-gray-600">Utilisateurs avec des comportements suspects détectés</p>
        </div>
        <button
          onClick={load}
          className="flex items-center gap-2 px-4 py-2 border border-gray-200 rounded-xl text-sm font-medium hover:bg-gray-50 transition-colors"
        >
          <RefreshCw size={15} />
          Actualiser
        </button>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-48">
          <Loader2 size={32} className="animate-spin text-[#6D28D9]" />
        </div>
      ) : totalFlags === 0 ? (
        <div className="flex flex-col items-center justify-center h-48 gap-3 text-gray-400">
          <CheckCircle2 size={36} className="text-green-400" />
          <p className="text-sm font-medium text-green-600">Aucun flag actif — plateforme saine</p>
        </div>
      ) : (
        <div className="space-y-6">
          {/* Payout blocked */}
          <div>
            <div className="flex items-center gap-2 mb-3">
              <div className="w-8 h-8 rounded-lg bg-red-50 flex items-center justify-center">
                <ShieldAlert size={16} className="text-red-600" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-gray-900">Payout bloqués</h3>
                <p className="text-xs text-gray-500">Trop d'échecs de payout consécutifs</p>
              </div>
              <span className="ml-auto bg-red-100 text-red-700 text-xs font-bold px-2.5 py-1 rounded-lg">
                {flags?.payout_blocked.length ?? 0}
              </span>
            </div>
            {(flags?.payout_blocked.length ?? 0) === 0 ? (
              <p className="text-sm text-gray-400 italic px-2">Aucun utilisateur bloqué</p>
            ) : (
              <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
                <table className="w-full">
                  <thead className="bg-red-50 border-b border-red-100">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-red-700 uppercase tracking-wider">Utilisateur</th>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-red-700 uppercase tracking-wider">Échecs consécutifs</th>
                      <th className="px-4 py-3 text-right text-xs font-semibold text-red-700 uppercase tracking-wider">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {flags!.payout_blocked.map((entry) => (
                      <tr key={entry.user_id} className={`hover:bg-gray-50 transition-colors ${cleared.includes(entry.user_id) ? 'opacity-40' : ''}`}>
                        <td className="px-4 py-3">
                          <span className="font-mono text-sm text-gray-700">{entry.user_id.slice(0, 16)}…</span>
                        </td>
                        <td className="px-4 py-3">
                          <span className="inline-flex items-center gap-1 text-sm font-bold text-red-600">
                            <AlertTriangle size={14} />
                            {entry.consecutive_failures}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-right">
                          <button
                            onClick={() => setConfirmUserId(entry.user_id)}
                            disabled={cleared.includes(entry.user_id)}
                            className="px-3 py-1.5 rounded-lg text-xs font-medium bg-red-50 text-red-700 hover:bg-red-100 disabled:opacity-40 transition-colors flex items-center gap-1 ml-auto"
                          >
                            <Trash2 size={12} /> Lever les flags
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Rapid cycle */}
          <div>
            <div className="flex items-center gap-2 mb-3">
              <div className="w-8 h-8 rounded-lg bg-amber-50 flex items-center justify-center">
                <Zap size={16} className="text-amber-600" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-gray-900">Cycle rapide suspect</h3>
                <p className="text-xs text-gray-500">Dépôt puis retrait immédiat (blanchiment potentiel)</p>
              </div>
              <span className="ml-auto bg-amber-100 text-amber-700 text-xs font-bold px-2.5 py-1 rounded-lg">
                {flags?.rapid_cycle_candidates.length ?? 0}
              </span>
            </div>
            {(flags?.rapid_cycle_candidates.length ?? 0) === 0 ? (
              <p className="text-sm text-gray-400 italic px-2">Aucun candidat détecté</p>
            ) : (
              <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
                <table className="w-full">
                  <thead className="bg-amber-50 border-b border-amber-100">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-amber-700 uppercase tracking-wider">Utilisateur</th>
                      <th className="px-4 py-3 text-right text-xs font-semibold text-amber-700 uppercase tracking-wider">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {flags!.rapid_cycle_candidates.map((entry) => (
                      <tr key={entry.user_id} className={`hover:bg-gray-50 transition-colors ${cleared.includes(entry.user_id) ? 'opacity-40' : ''}`}>
                        <td className="px-4 py-3">
                          <span className="font-mono text-sm text-gray-700">{entry.user_id.slice(0, 16)}…</span>
                        </td>
                        <td className="px-4 py-3 text-right">
                          <button
                            onClick={() => setConfirmUserId(entry.user_id)}
                            disabled={cleared.includes(entry.user_id)}
                            className="px-3 py-1.5 rounded-lg text-xs font-medium bg-amber-50 text-amber-700 hover:bg-amber-100 disabled:opacity-40 transition-colors flex items-center gap-1 ml-auto"
                          >
                            <Trash2 size={12} /> Lever les flags
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {confirmUserId && (
        <ConfirmClearModal
          userId={confirmUserId}
          onConfirm={handleClear}
          onCancel={() => setConfirmUserId(null)}
          loading={clearing}
        />
      )}
    </div>
  );
}
