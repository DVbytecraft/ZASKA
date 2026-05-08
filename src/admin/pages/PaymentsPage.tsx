import { useEffect, useState, useMemo } from 'react';
import {
  Search, RefreshCw, AlertCircle, RotateCcw,
  TrendingUp, TrendingDown, CheckCircle, XCircle, Clock, Zap
} from 'lucide-react';
import { DataTable } from '../components/DataTable';
import { TxStatusBadge, ProviderStatusBadge } from '../components/StatusBadge';
import { adminApi, type AdminTransaction, type AdminPaymentProvider } from '../adminApi';

const TX_TYPE_LABELS: Record<string, { label: string; icon: string; color: string }> = {
  deposit:    { label: 'Dépôt',          icon: '↓', color: 'text-green-600' },
  withdrawal: { label: 'Retrait',        icon: '↑', color: 'text-red-600' },
  transfer:   { label: 'Transfert',      icon: '⇄', color: 'text-blue-600' },
  escrow:     { label: 'Escrow',         icon: '🔒', color: 'text-purple-600' },
  release:    { label: 'Libération',     icon: '✓',  color: 'text-green-600' },
  refund:     { label: 'Remboursement',  icon: '↩', color: 'text-amber-600' },
  adjustment: { label: 'Ajustement',    icon: '⚙',  color: 'text-gray-600' },
};

const MOCK_PROVIDERS: AdminPaymentProvider[] = [
  { id: 'stripe',    name: 'Stripe',    type: 'card',         countries: ['US', 'EU'], status: 'operational', success_rate: 99.2 },
  { id: 'mtn',       name: 'MTN MoMo',  type: 'mobile_money', countries: ['GH', 'CI', 'CM'], status: 'operational', success_rate: 97.8 },
  { id: 'orange',    name: 'Orange Money', type: 'mobile_money', countries: ['SN', 'CI', 'ML'], status: 'degraded', success_rate: 91.4 },
  { id: 'fedapay',   name: 'FedaPay',   type: 'mobile_money', countries: ['TG', 'BJ'], status: 'operational', success_rate: 98.1 },
  { id: 'flutterwave', name: 'Flutterwave', type: 'card',     countries: ['NG', 'GH', 'KE'], status: 'operational', success_rate: 96.5 },
];

export function PaymentsPage() {
  const [transactions, setTransactions] = useState<AdminTransaction[]>([]);
  const [providers, setProviders] = useState<AdminPaymentProvider[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [retrying, setRetrying] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const [txs, provs] = await Promise.allSettled([
        adminApi.getTransactions(),
        adminApi.getPaymentProviders(),
      ]);
      if (txs.status === 'fulfilled') setTransactions(txs.value);
      setProviders(txs.status === 'rejected' || provs.status === 'rejected' ? MOCK_PROVIDERS : (provs as PromiseFulfilledResult<AdminPaymentProvider[]>).value);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erreur');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    return transactions.filter((tx) => {
      const matchSearch = !q ||
        (tx.reference ?? '').toLowerCase().includes(q) ||
        tx.user_id.toLowerCase().includes(q) ||
        (tx.user_phone ?? '').includes(q) ||
        (tx.user_name ?? '').toLowerCase().includes(q);
      const matchType = !typeFilter || tx.type === typeFilter;
      const matchStatus = !statusFilter || tx.status === statusFilter;
      return matchSearch && matchType && matchStatus;
    });
  }, [transactions, search, typeFilter, statusFilter]);

  const stats = useMemo(() => {
    const failed = transactions.filter(t => t.status === 'failed');
    const pending = transactions.filter(t => t.status === 'pending');
    return { total: transactions.length, failed: failed.length, pending: pending.length };
  }, [transactions]);

  const handleRetry = async (txId: string) => {
    setRetrying(txId);
    try {
      await adminApi.retryTransaction(txId);
      setTransactions(prev => prev.map(tx => tx.id === txId ? { ...tx, status: 'pending' as const } : tx));
    } catch {}
    finally { setRetrying(null); }
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Paiements</h2>
          <p className="text-sm text-gray-600">Suivi des transactions et santé des fournisseurs</p>
        </div>
        <button onClick={load} className="flex items-center gap-2 px-4 py-2 border border-gray-200 rounded-xl text-sm font-medium hover:bg-gray-50 transition-colors">
          <RefreshCw size={15} />
          Actualiser
        </button>
      </div>

      {/* Provider health cards */}
      <div>
        <h3 className="text-sm font-bold text-gray-700 uppercase tracking-wide mb-3 flex items-center gap-2">
          <Zap size={14} className="text-amber-500" />
          État des fournisseurs
        </h3>
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
          {(providers.length ? providers : MOCK_PROVIDERS).map((p) => (
            <div key={p.id} className={`bg-white rounded-xl border p-4 ${
              p.status === 'down' ? 'border-red-200 bg-red-50' :
              p.status === 'degraded' ? 'border-amber-200 bg-amber-50' : 'border-gray-200'
            }`}>
              <div className="flex items-start justify-between mb-2">
                <p className="text-sm font-bold text-gray-900">{p.name}</p>
                <ProviderStatusBadge status={p.status} />
              </div>
              <div className="flex items-center gap-1 text-xs text-gray-500">
                {p.success_rate >= 95
                  ? <TrendingUp size={12} className="text-green-500" />
                  : <TrendingDown size={12} className="text-red-500" />
                }
                <span className={`font-semibold ${p.success_rate >= 95 ? 'text-green-600' : 'text-red-600'}`}>
                  {p.success_rate}%
                </span>
                <span>succès</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Transaction summary */}
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: 'Total transactions', value: stats.total, icon: CheckCircle, color: 'text-gray-900', bg: 'bg-gray-50' },
          { label: 'En attente', value: stats.pending, icon: Clock, color: 'text-amber-600', bg: 'bg-amber-50' },
          { label: 'Échouées', value: stats.failed, icon: XCircle, color: 'text-red-600', bg: 'bg-red-50' },
        ].map((s) => {
          const Icon = s.icon;
          return (
            <div key={s.label} className={`${s.bg} rounded-xl border border-gray-200 p-4 flex items-center gap-4`}>
              <div className="w-10 h-10 rounded-xl bg-white flex items-center justify-center shadow-sm">
                <Icon size={20} className={s.color} />
              </div>
              <div>
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">{s.label}</p>
                <p className={`text-2xl font-extrabold ${s.color}`}>{loading ? '—' : s.value}</p>
              </div>
            </div>
          );
        })}
      </div>

      {/* Failed transactions alert */}
      {stats.failed > 0 && !loading && (
        <div className="flex items-center gap-3 bg-red-50 border border-red-200 rounded-xl px-4 py-3">
          <AlertCircle size={18} className="text-red-600 flex-shrink-0" />
          <p className="text-sm text-red-800 font-medium">
            {stats.failed} transaction{stats.failed > 1 ? 's' : ''} échouée{stats.failed > 1 ? 's' : ''} — vérifiez les transactions ci-dessous.
          </p>
          <button
            onClick={() => setStatusFilter('failed')}
            className="ml-auto text-sm font-semibold text-red-700 underline whitespace-nowrap"
          >
            Voir les échecs
          </button>
        </div>
      )}

      {/* Filters */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[200px]">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            placeholder="Référence, téléphone, utilisateur..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2.5 border border-gray-200 rounded-xl text-sm bg-gray-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#6D28D9]/30 focus:border-[#6D28D9]"
          />
        </div>
        <select
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
          className="px-3 py-2.5 border border-gray-200 rounded-xl text-sm bg-white focus:outline-none"
        >
          <option value="">Tous les types</option>
          {Object.entries(TX_TYPE_LABELS).map(([k, v]) => (
            <option key={k} value={k}>{v.label}</option>
          ))}
        </select>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="px-3 py-2.5 border border-gray-200 rounded-xl text-sm bg-white focus:outline-none"
        >
          <option value="">Tous les statuts</option>
          <option value="completed">Complétées</option>
          <option value="pending">En attente</option>
          <option value="failed">Échouées</option>
          <option value="cancelled">Annulées</option>
        </select>
        {(search || typeFilter || statusFilter) && (
          <button onClick={() => { setSearch(''); setTypeFilter(''); setStatusFilter(''); }} className="text-sm text-[#6D28D9] hover:underline">
            Réinitialiser
          </button>
        )}
      </div>

      {loading ? (
        <div className="space-y-3">{[1,2,3,4,5].map(i => <div key={i} className="h-14 bg-gray-100 rounded-xl animate-pulse" />)}</div>
      ) : error ? (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
          <p className="text-sm text-amber-800">{error}</p>
          <p className="text-xs text-amber-600 mt-1">Les transactions ne sont pas disponibles en ce moment.</p>
        </div>
      ) : (
        <DataTable
          columns={[
            {
              key: 'type', label: 'Type',
              render: (v) => {
                const cfg = TX_TYPE_LABELS[v as string] ?? { label: v as string, icon: '', color: 'text-gray-700' };
                return (
                  <span className={`text-sm font-semibold ${cfg.color}`}>
                    {cfg.icon} {cfg.label}
                  </span>
                );
              }
            },
            {
              key: 'amount', label: 'Montant',
              render: (v, row) => {
                const tx = row as AdminTransaction;
                const cfg = TX_TYPE_LABELS[tx.type];
                const isOutflow = tx.type === 'withdrawal' || tx.type === 'escrow';
                return (
                  <span className={`font-bold text-sm ${isOutflow ? 'text-red-600' : 'text-gray-900'}`}>
                    {isOutflow ? '-' : '+'}{Number(v).toLocaleString()} {tx.currency}
                  </span>
                );
              }
            },
            { key: 'status', label: 'Statut', render: (v) => <TxStatusBadge status={v as string} /> },
            {
              key: 'user_name', label: 'Utilisateur',
              render: (v, row) => {
                const tx = row as AdminTransaction;
                return (
                  <div>
                    <p className="text-sm font-medium text-gray-900">{(v as string | undefined) ?? '—'}</p>
                    {tx.user_phone && <p className="text-xs text-gray-400">{tx.user_phone}</p>}
                  </div>
                );
              }
            },
            {
              key: 'provider', label: 'Fournisseur',
              render: (v) => (v as string | undefined) ? (
                <span className="text-xs font-medium text-gray-600 bg-gray-100 px-2 py-0.5 rounded-full">
                  {v as string}
                </span>
              ) : '—'
            },
            {
              key: 'reference', label: 'Référence',
              render: (v) => v ? (
                <code className="text-xs text-gray-500 bg-gray-50 px-2 py-0.5 rounded font-mono">
                  {(v as string).slice(0, 16)}…
                </code>
              ) : '—'
            },
            { key: 'created_at', label: 'Date', render: (v) => new Date(v as string).toLocaleDateString('fr-FR') },
            {
              key: 'id', label: 'Action',
              render: (v, row) => {
                const tx = row as AdminTransaction;
                if (tx.status !== 'failed') return null;
                return (
                  <button
                    onClick={(e) => { e.stopPropagation(); handleRetry(tx.id); }}
                    disabled={retrying === tx.id}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-100 text-amber-700 text-xs font-semibold hover:bg-amber-200 transition-colors"
                  >
                    <RotateCcw size={12} className={retrying === tx.id ? 'animate-spin' : ''} />
                    Réessayer
                  </button>
                );
              }
            },
          ]}
          data={filtered}
        />
      )}

      {filtered.length === 0 && !loading && !error && (
        <p className="text-center text-sm text-gray-400 py-8">Aucune transaction trouvée.</p>
      )}
    </div>
  );
}
