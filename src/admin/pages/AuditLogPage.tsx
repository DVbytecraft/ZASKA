import { useEffect, useState } from 'react';
import { ClipboardList, RefreshCw, Loader2, Search, Filter } from 'lucide-react';
import { adminApi, type AdminAuditLog } from '../adminApi';

const ACTION_COLORS: Record<string, string> = {
  deposit: 'text-green-700 bg-green-50 border-green-100',
  withdrawal: 'text-blue-700 bg-blue-50 border-blue-100',
  escrow_fund: 'text-purple-700 bg-purple-50 border-purple-100',
  escrow_release: 'text-indigo-700 bg-indigo-50 border-indigo-100',
  refund: 'text-amber-700 bg-amber-50 border-amber-100',
  adjustment: 'text-gray-700 bg-gray-50 border-gray-200',
  reversal: 'text-red-700 bg-red-50 border-red-100',
};

function ActionBadge({ action }: { action: string }) {
  const cls = ACTION_COLORS[action] ?? 'text-gray-700 bg-gray-50 border-gray-200';
  return (
    <span className={`inline-block px-2 py-0.5 rounded-md text-xs font-semibold border ${cls}`}>
      {action}
    </span>
  );
}

function StatusDot({ status }: { status: string }) {
  const colors: Record<string, string> = {
    completed: 'bg-green-500',
    success: 'bg-green-500',
    pending: 'bg-amber-400',
    failed: 'bg-red-500',
    cancelled: 'bg-gray-400',
  };
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-gray-600 font-medium">
      <span className={`w-2 h-2 rounded-full ${colors[status] ?? 'bg-gray-400'}`} />
      {status}
    </span>
  );
}

export function AuditLogPage() {
  const [logs, setLogs] = useState<AdminAuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [userFilter, setUserFilter] = useState('');
  const [actionFilter, setActionFilter] = useState('');
  const [appliedUser, setAppliedUser] = useState('');
  const [appliedAction, setAppliedAction] = useState('');

  const load = async (uid?: string, action?: string) => {
    setLoading(true);
    try {
      const data = await adminApi.getAuditLogs({
        user_id: uid || undefined,
        action: action || undefined,
        limit: 200,
      });
      setLogs(data);
    } catch {
      setLogs([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void load(); }, []);

  const handleSearch = () => {
    setAppliedUser(userFilter);
    setAppliedAction(actionFilter);
    void load(userFilter, actionFilter);
  };

  const handleReset = () => {
    setUserFilter('');
    setActionFilter('');
    setAppliedUser('');
    setAppliedAction('');
    void load();
  };

  const formatAmount = (amount: string, currency: string) => {
    const n = parseFloat(amount);
    if (isNaN(n)) return `${amount} ${currency}`;
    return `${n.toLocaleString('fr-FR')} ${currency}`;
  };

  return (
    <div className="p-4 sm:p-6 space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Journal d'audit</h2>
          <p className="text-sm text-gray-600">Traçabilité immuable des opérations financières</p>
        </div>
        <button
          onClick={() => void load(appliedUser, appliedAction)}
          className="flex items-center gap-2 px-4 py-2 border border-gray-200 rounded-xl text-sm font-medium hover:bg-gray-50 transition-colors"
        >
          <RefreshCw size={15} />
          Actualiser
        </button>
      </div>

      {/* Filters */}
      <div className="bg-white border border-gray-200 rounded-xl p-4 flex flex-wrap gap-3 items-end">
        <div className="flex-1 min-w-[180px]">
          <label className="text-xs text-gray-500 font-medium block mb-1">ID utilisateur</label>
          <div className="relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              value={userFilter}
              onChange={(e) => setUserFilter(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              placeholder="uuid…"
              className="w-full pl-8 pr-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
            />
          </div>
        </div>
        <div className="flex-1 min-w-[160px]">
          <label className="text-xs text-gray-500 font-medium block mb-1">Action</label>
          <div className="relative">
            <Filter size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <select
              value={actionFilter}
              onChange={(e) => setActionFilter(e.target.value)}
              className="w-full pl-8 pr-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent bg-white appearance-none"
            >
              <option value="">Toutes les actions</option>
              {['deposit', 'withdrawal', 'escrow_fund', 'escrow_release', 'refund', 'adjustment', 'reversal'].map(a => (
                <option key={a} value={a}>{a}</option>
              ))}
            </select>
          </div>
        </div>
        <div className="flex gap-2">
          <button
            onClick={handleSearch}
            className="px-4 py-2 bg-[#6D28D9] text-white rounded-lg text-sm font-semibold hover:bg-purple-700 transition-colors"
          >
            Filtrer
          </button>
          {(appliedUser || appliedAction) && (
            <button
              onClick={handleReset}
              className="px-4 py-2 border border-gray-200 rounded-lg text-sm font-medium hover:bg-gray-50 transition-colors"
            >
              Réinitialiser
            </button>
          )}
        </div>
      </div>

      {/* Counter */}
      {!loading && (
        <p className="text-xs text-gray-500">
          {logs.length} entrée{logs.length !== 1 ? 's' : ''}
          {appliedUser ? ` · user ${appliedUser.slice(0, 8)}` : ''}
          {appliedAction ? ` · action: ${appliedAction}` : ''}
        </p>
      )}

      {loading ? (
        <div className="flex items-center justify-center h-48">
          <Loader2 size={32} className="animate-spin text-[#6D28D9]" />
        </div>
      ) : logs.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-48 gap-3 text-gray-400">
          <ClipboardList size={36} className="text-gray-300" />
          <p className="text-sm font-medium">Aucune entrée dans le journal</p>
        </div>
      ) : (
        <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
          <table className="w-full">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                {['Date', 'Action', 'Utilisateur', 'Montant', 'Statut', 'Provider', 'Pays'].map(h => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {logs.map((log) => (
                <tr key={log.id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3 text-xs text-gray-500 whitespace-nowrap">
                    {new Date(log.created_at).toLocaleString('fr-FR', { dateStyle: 'short', timeStyle: 'short' })}
                  </td>
                  <td className="px-4 py-3">
                    <ActionBadge action={log.action} />
                  </td>
                  <td className="px-4 py-3">
                    <span className="font-mono text-xs text-gray-600">{log.user_id.slice(0, 10)}…</span>
                  </td>
                  <td className="px-4 py-3 text-sm font-semibold text-gray-900 whitespace-nowrap">
                    {formatAmount(log.amount, log.currency)}
                  </td>
                  <td className="px-4 py-3">
                    <StatusDot status={log.status} />
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-500">{log.provider ?? '—'}</td>
                  <td className="px-4 py-3 text-xs text-gray-500">{log.country_code ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
