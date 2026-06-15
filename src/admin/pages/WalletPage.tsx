import { useEffect, useState, useMemo } from 'react';
import {
  Wallet, RefreshCw, AlertCircle, Lock, Unlock, DollarSign,
  CheckCircle, Clock, Loader2, PlusCircle
} from 'lucide-react';
import { DataTable } from '../components/DataTable';
import { ConfirmModal } from '../components/ConfirmModal';
import { adminApi, type AdminEscrow } from '../adminApi';

type EscrowAction = { type: 'release' | 'refund'; escrow: AdminEscrow };

export function WalletPage() {
  const [escrows, setEscrows] = useState<AdminEscrow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState('');

  // Manual balance adjustment
  const [adjusting, setAdjusting] = useState(false);
  const [adjustUserId, setAdjustUserId] = useState('');
  const [adjustAmount, setAdjustAmount] = useState('');
  const [adjustCurrency, setAdjustCurrency] = useState('XOF');
  const [adjustReason, setAdjustReason] = useState('');
  const [adjustLoading, setAdjustLoading] = useState(false);
  const [adjustSuccess, setAdjustSuccess] = useState(false);
  const [adjustError, setAdjustError] = useState('');

  // Escrow action
  const [pendingAction, setPendingAction] = useState<EscrowAction | null>(null);
  const [actionLoading, setActionLoading] = useState(false);

  const load = () => {
    setLoading(true);
    setError(null);
    adminApi.getEscrows(statusFilter || undefined)
      .then(setEscrows)
      .catch((e) => setError(e instanceof Error ? e.message : 'Erreur'))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, [statusFilter]);

  const stats = useMemo(() => {
    const funded = escrows.filter(e => e.status === 'funded');
    const totalLocked = funded.reduce((sum, e) => sum + Number(e.amount), 0);
    return {
      total: escrows.length,
      funded: funded.length,
      released: escrows.filter(e => e.status === 'released').length,
      disputed: escrows.filter(e => e.status === 'disputed').length,
      totalLocked,
    };
  }, [escrows]);

  const handleEscrowAction = async (reason: string) => {
    if (!pendingAction) return;
    setActionLoading(true);
    try {
      if (pendingAction.type === 'release') await adminApi.releaseEscrow(pendingAction.escrow.escrow_id);
      if (pendingAction.type === 'refund') await adminApi.refundEscrow(pendingAction.escrow.escrow_id, reason);
      setEscrows(prev => prev.map(e =>
        e.escrow_id === pendingAction.escrow.escrow_id
          ? { ...e, status: pendingAction.type === 'release' ? 'released' : 'refunded' }
          : e
      ));
      setPendingAction(null);
    } catch {}
    finally { setActionLoading(false); }
  };

  const handleAdjust = async () => {
    if (!adjustUserId || !adjustAmount || !adjustReason) return;
    setAdjustLoading(true);
    setAdjustError('');
    setAdjustSuccess(false);
    try {
      await adminApi.adjustBalance(adjustUserId, adjustAmount, adjustCurrency, adjustReason);
      setAdjustSuccess(true);
      setAdjustUserId('');
      setAdjustAmount('');
      setAdjustReason('');
      setTimeout(() => setAdjustSuccess(false), 3000);
    } catch (e) {
      setAdjustError(e instanceof Error ? e.message : 'Échec de l\'ajustement');
    } finally {
      setAdjustLoading(false);
    }
  };

  const STATUS_COLORS: Record<string, string> = {
    funded:   'bg-blue-100 text-blue-700',
    released: 'bg-green-100 text-green-700',
    refunded: 'bg-amber-100 text-amber-700',
    disputed: 'bg-red-100 text-red-700',
  };

  return (
    <div className="p-4 sm:p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Portefeuille & Finance</h2>
          <p className="text-sm text-gray-600">Escrows, ajustements manuels et supervision financière</p>
        </div>
        <button onClick={load} className="flex items-center gap-2 px-4 py-2 border border-gray-200 rounded-xl text-sm font-medium hover:bg-gray-50 transition-colors">
          <RefreshCw size={15} />
          Actualiser
        </button>
      </div>

      {/* Financial summary */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: 'Total escrows', value: String(stats.total), icon: Lock, bg: 'bg-white', color: 'text-gray-900' },
          { label: 'Fonds bloqués', value: String(stats.funded), icon: Lock, bg: 'bg-blue-50', color: 'text-blue-700' },
          { label: 'Libérés', value: String(stats.released), icon: Unlock, bg: 'bg-green-50', color: 'text-green-700' },
          { label: 'Disputés', value: String(stats.disputed), icon: AlertCircle, bg: 'bg-red-50', color: 'text-red-700' },
        ].map((s) => {
          const Icon = s.icon;
          return (
            <div key={s.label} className={`${s.bg} rounded-xl border border-gray-200 p-4`}>
              <div className="flex items-center gap-2 mb-2">
                <Icon size={16} className={s.color} />
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">{s.label}</p>
              </div>
              <p className={`text-3xl font-extrabold ${s.color}`}>{loading ? '—' : s.value}</p>
            </div>
          );
        })}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Escrow table */}
        <div className="lg:col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-bold text-gray-900 flex items-center gap-2">
              <Lock size={16} className="text-[#6D28D9]" />
              Escrows
            </h3>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="px-3 py-2 border border-gray-200 rounded-xl text-sm bg-white focus:outline-none"
            >
              <option value="">Tous</option>
              <option value="funded">Bloqués</option>
              <option value="released">Libérés</option>
              <option value="refunded">Remboursés</option>
              <option value="disputed">Disputés</option>
            </select>
          </div>

          {loading ? (
            <div className="space-y-3">{[1,2,3].map(i => <div key={i} className="h-14 bg-gray-100 rounded-xl animate-pulse" />)}</div>
          ) : error ? (
            <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
              <p className="text-sm text-amber-800">{error}</p>
              <p className="text-xs text-amber-600 mt-1">Escrows non disponibles — le backend admin/escrows n'est peut-être pas encore implémenté.</p>
            </div>
          ) : (
            <DataTable
              columns={[
                {
                  key: 'task_title', label: 'Tâche',
                  render: (v, row) => {
                    const e = row as AdminEscrow;
                    return (
                      <div>
                        <p className="text-sm font-semibold text-gray-900">{(v as string | undefined) ?? e.task_id.slice(0, 10) + '…'}</p>
                        <p className="text-xs text-gray-400">{e.client_name ?? e.client_id.slice(0, 8)}</p>
                      </div>
                    );
                  }
                },
                {
                  key: 'amount', label: 'Montant',
                  render: (v, row) => {
                    const e = row as AdminEscrow;
                    return <span className="font-bold text-sm">{Number(v).toLocaleString()} {e.currency}</span>;
                  }
                },
                {
                  key: 'status', label: 'Statut',
                  render: (v) => (
                    <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${STATUS_COLORS[v as string] ?? 'bg-gray-100 text-gray-600'}`}>
                      {v as string}
                    </span>
                  )
                },
                {
                  key: 'escrow_id', label: 'Actions',
                  render: (_, row) => {
                    const e = row as AdminEscrow;
                    if (e.status !== 'funded' && e.status !== 'disputed') return null;
                    return (
                      <div className="flex gap-1.5">
                        <button
                          onClick={(ev) => { ev.stopPropagation(); setPendingAction({ type: 'release', escrow: e }); }}
                          className="px-2.5 py-1 rounded-lg bg-green-100 text-green-700 text-xs font-semibold hover:bg-green-200 transition-colors flex items-center gap-1"
                        >
                          <CheckCircle size={11} /> Libérer
                        </button>
                        <button
                          onClick={(ev) => { ev.stopPropagation(); setPendingAction({ type: 'refund', escrow: e }); }}
                          className="px-2.5 py-1 rounded-lg bg-amber-100 text-amber-700 text-xs font-semibold hover:bg-amber-200 transition-colors flex items-center gap-1"
                        >
                          <Clock size={11} /> Rembourser
                        </button>
                      </div>
                    );
                  }
                },
              ]}
              data={escrows}
            />
          )}
          {escrows.length === 0 && !loading && !error && (
            <p className="text-center text-sm text-gray-400 py-6">Aucun escrow trouvé.</p>
          )}
        </div>

        {/* Manual balance adjustment */}
        <div className="space-y-4">
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
              <h3 className="text-sm font-bold text-gray-900 flex items-center gap-2">
                <DollarSign size={16} className="text-[#6D28D9]" />
                Ajustement manuel
              </h3>
              <button
                onClick={() => setAdjusting(!adjusting)}
                className="p-1.5 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <PlusCircle size={16} className={`transition-transform ${adjusting ? 'text-[#6D28D9] rotate-45' : 'text-gray-400'}`} />
              </button>
            </div>

            {adjusting && (
              <div className="px-5 py-4 space-y-4">
                <div className="bg-amber-50 border border-amber-200 rounded-xl p-3 text-xs text-amber-800">
                  ⚠️ Action sensible. Tous les ajustements sont enregistrés dans le journal d'audit.
                </div>

                <div className="space-y-3">
                  <div>
                    <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">ID utilisateur</label>
                    <input
                      type="text"
                      value={adjustUserId}
                      onChange={(e) => setAdjustUserId(e.target.value)}
                      placeholder="UUID de l'utilisateur..."
                      className="w-full px-3 py-2.5 border-2 border-gray-200 rounded-xl text-sm focus:border-[#6D28D9] focus:outline-none"
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Montant</label>
                      <input
                        type="number"
                        value={adjustAmount}
                        onChange={(e) => setAdjustAmount(e.target.value)}
                        placeholder="ex: -500 ou 1000"
                        className="w-full px-3 py-2.5 border-2 border-gray-200 rounded-xl text-sm focus:border-[#6D28D9] focus:outline-none"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Devise</label>
                      <select
                        value={adjustCurrency}
                        onChange={(e) => setAdjustCurrency(e.target.value)}
                        className="w-full px-3 py-2.5 border-2 border-gray-200 rounded-xl text-sm focus:border-[#6D28D9] focus:outline-none"
                      >
                        <option value="XOF">XOF</option>
                        <option value="USD">USD</option>
                        <option value="EUR">EUR</option>
                        <option value="GHS">GHS</option>
                        <option value="NGN">NGN</option>
                      </select>
                    </div>
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Raison (obligatoire)</label>
                    <textarea
                      value={adjustReason}
                      onChange={(e) => setAdjustReason(e.target.value)}
                      placeholder="Justification de l'ajustement..."
                      rows={3}
                      className="w-full px-3 py-2.5 border-2 border-gray-200 rounded-xl text-sm resize-none focus:border-[#6D28D9] focus:outline-none"
                    />
                  </div>

                  {adjustError && <p className="text-xs text-red-600 bg-red-50 px-3 py-2 rounded-xl">{adjustError}</p>}
                  {adjustSuccess && <p className="text-xs text-green-700 bg-green-50 px-3 py-2 rounded-xl">✅ Ajustement appliqué avec succès</p>}

                  <button
                    onClick={handleAdjust}
                    disabled={!adjustUserId || !adjustAmount || !adjustReason || adjustLoading}
                    className="w-full py-2.5 rounded-xl bg-[#6D28D9] text-white text-sm font-bold hover:bg-[#5B21B6] disabled:opacity-50 transition-colors flex items-center justify-center gap-2"
                  >
                    {adjustLoading ? <Loader2 size={14} className="animate-spin" /> : <Wallet size={14} />}
                    Appliquer l'ajustement
                  </button>
                </div>
              </div>
            )}

            {!adjusting && (
              <div className="px-5 py-4 text-center">
                <p className="text-sm text-gray-400">Cliquez sur + pour créer un ajustement manuel de solde.</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Confirm escrow action */}
      <ConfirmModal
        open={!!pendingAction}
        title={pendingAction?.type === 'release' ? 'Libérer l\'escrow' : 'Rembourser l\'escrow'}
        description={
          pendingAction?.type === 'release'
            ? <span>Libérer <strong>{Number(pendingAction.escrow.amount).toLocaleString()} {pendingAction.escrow.currency}</strong> vers le tasker ?</span>
            : <span>Rembourser <strong>{Number(pendingAction?.escrow.amount).toLocaleString()} {pendingAction?.escrow.currency}</strong> vers le client ?</span>
        }
        confirmLabel={pendingAction?.type === 'release' ? 'Libérer' : 'Rembourser'}
        variant={pendingAction?.type === 'release' ? 'info' : 'warning'}
        requireReason={pendingAction?.type === 'refund'}
        reasonLabel="Raison du remboursement"
        loading={actionLoading}
        onConfirm={handleEscrowAction}
        onCancel={() => setPendingAction(null)}
      />
    </div>
  );
}
