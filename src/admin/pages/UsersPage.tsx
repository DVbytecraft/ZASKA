import { useEffect, useState, useMemo } from 'react';
import {
  Search, UserCheck, UserX, ShieldOff, Lock, Unlock,
  RefreshCw, AlertCircle, Eye, Filter
} from 'lucide-react';
import { DataTable } from '../components/DataTable';
import { ConfirmModal } from '../components/ConfirmModal';
import { UserDetailPanel } from '../components/UserDetailPanel';
import { adminApi, type AdminUser } from '../adminApi';

type ActionType = 'suspend' | 'unsuspend' | 'ban' | 'verify' | 'lock' | 'unlock';

interface Action {
  type: ActionType;
  userId: string;
  userName: string;
}

const ACTION_CONFIG: Record<ActionType, {
  title: string; variant: 'danger' | 'warning' | 'info'; label: string; requireReason: boolean;
}> = {
  suspend:   { title: 'Suspendre l\'utilisateur', variant: 'warning', label: 'Suspendre', requireReason: true },
  unsuspend: { title: 'Réactiver l\'utilisateur', variant: 'info',    label: 'Réactiver',  requireReason: false },
  ban:       { title: 'Bannir l\'utilisateur',    variant: 'danger',  label: 'Bannir',     requireReason: true },
  verify:    { title: 'Vérifier le compte',       variant: 'info',    label: 'Vérifier',   requireReason: false },
  lock:      { title: 'Verrouiller le compte',    variant: 'warning', label: 'Verrouiller', requireReason: true },
  unlock:    { title: 'Déverrouiller le compte',  variant: 'info',    label: 'Déverrouiller', requireReason: false },
};

function userName(u: AdminUser) {
  return (u.full_name ?? `${u.first_name ?? ''} ${u.last_name ?? ''}`.trim()) || (u.email ?? u.phone ?? '—');
}

export function UsersPage() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');

  const [pendingAction, setPendingAction] = useState<Action | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const [detailUserId, setDetailUserId] = useState<string | null>(null);

  const load = () => {
    setLoading(true);
    setError(null);
    adminApi.getUsers()
      .then(setUsers)
      .catch((e) => setError(e instanceof Error ? e.message : 'Erreur'))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    return users.filter((u) => {
      const matchSearch = !q ||
        userName(u).toLowerCase().includes(q) ||
        (u.phone ?? '').includes(q) ||
        (u.email ?? '').toLowerCase().includes(q);
      const matchRole = !roleFilter || u.role === roleFilter;
      const matchStatus = !statusFilter ||
        (statusFilter === 'verified' && u.is_verified) ||
        (statusFilter === 'unverified' && !u.is_verified) ||
        (statusFilter === 'suspended' && u.is_suspended) ||
        (statusFilter === 'locked' && u.is_locked);
      return matchSearch && matchRole && matchStatus;
    });
  }, [users, search, roleFilter, statusFilter]);

  const handleAction = async (reason: string) => {
    if (!pendingAction) return;
    setActionLoading(true);
    setActionError(null);
    try {
      const { type, userId } = pendingAction;
      if (type === 'suspend')   await adminApi.suspendUser(userId, reason);
      if (type === 'unsuspend') await adminApi.unsuspendUser(userId);
      if (type === 'ban')       await adminApi.banUser(userId, reason);
      if (type === 'verify')    await adminApi.verifyUser(userId);
      if (type === 'lock')      await adminApi.lockAccount(userId, reason);
      if (type === 'unlock')    await adminApi.unlockAccount(userId);

      // Optimistically update local state
      setUsers(prev => prev.map((u) => {
        if (u.id !== userId) return u;
        if (type === 'verify')    return { ...u, is_verified: true };
        if (type === 'suspend')   return { ...u, is_suspended: true };
        if (type === 'unsuspend') return { ...u, is_suspended: false };
        if (type === 'lock')      return { ...u, is_locked: true };
        if (type === 'unlock')    return { ...u, is_locked: false };
        return u;
      }));
      setPendingAction(null);
    } catch (e) {
      setActionError(e instanceof Error ? e.message : 'Action échouée');
    } finally {
      setActionLoading(false);
    }
  };

  const stats = useMemo(() => ({
    total: users.length,
    verified: users.filter(u => u.is_verified).length,
    unverified: users.filter(u => !u.is_verified).length,
    suspended: users.filter(u => u.is_suspended).length,
  }), [users]);

  const cfg = pendingAction ? ACTION_CONFIG[pendingAction.type] : null;

  return (
    <div className="p-4 sm:p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Utilisateurs</h2>
          <p className="text-sm text-gray-600">Gestion et supervision des comptes</p>
        </div>
        <button onClick={load} className="flex items-center gap-2 px-4 py-2 border border-gray-200 rounded-xl text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors">
          <RefreshCw size={15} />
          Actualiser
        </button>
      </div>

      {/* KPI strip */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {[
          { label: 'Total', value: stats.total, color: 'text-gray-900' },
          { label: 'Vérifiés', value: stats.verified, color: 'text-green-600' },
          { label: 'Non vérifiés', value: stats.unverified, color: 'text-amber-600' },
          { label: 'Suspendus', value: stats.suspended, color: 'text-red-600' },
        ].map((s) => (
          <div key={s.label} className="bg-white rounded-xl border border-gray-200 p-4">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">{s.label}</p>
            <p className={`text-3xl font-extrabold mt-1 ${s.color}`}>{loading ? '—' : s.value}</p>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[200px]">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            placeholder="Rechercher par nom, téléphone, email..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2.5 border border-gray-200 rounded-xl text-sm bg-gray-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#6D28D9]/30 focus:border-[#6D28D9]"
          />
        </div>
        <div className="flex items-center gap-2">
          <Filter size={15} className="text-gray-400" />
          <select
            value={roleFilter}
            onChange={(e) => setRoleFilter(e.target.value)}
            className="px-3 py-2.5 border border-gray-200 rounded-xl text-sm bg-white focus:outline-none focus:ring-2 focus:ring-[#6D28D9]/30"
          >
            <option value="">Tous les rôles</option>
            <option value="client">Clients</option>
            <option value="tasker">Taskers</option>
            <option value="admin">Admins</option>
          </select>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-3 py-2.5 border border-gray-200 rounded-xl text-sm bg-white focus:outline-none focus:ring-2 focus:ring-[#6D28D9]/30"
          >
            <option value="">Tous les statuts</option>
            <option value="verified">Vérifiés</option>
            <option value="unverified">Non vérifiés</option>
            <option value="suspended">Suspendus</option>
            <option value="locked">Verrouillés</option>
          </select>
        </div>
        {(search || roleFilter || statusFilter) && (
          <button
            onClick={() => { setSearch(''); setRoleFilter(''); setStatusFilter(''); }}
            className="text-sm text-[#6D28D9] hover:underline"
          >
            Réinitialiser
          </button>
        )}
      </div>

      {actionError && (
        <div className="flex items-center gap-2 bg-red-50 border border-red-100 rounded-xl px-4 py-3">
          <AlertCircle size={16} className="text-red-500 flex-shrink-0" />
          <p className="text-sm text-red-700">{actionError}</p>
        </div>
      )}

      {/* Table */}
      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3, 4, 5].map(i => <div key={i} className="h-14 bg-gray-100 rounded-xl animate-pulse" />)}
        </div>
      ) : error ? (
        <div className="bg-red-50 border border-red-100 rounded-xl p-4 flex items-center gap-3">
          <AlertCircle size={18} className="text-red-500" />
          <p className="text-sm text-red-700">{error}</p>
          <button onClick={load} className="ml-auto text-sm font-semibold text-red-600 underline">Réessayer</button>
        </div>
      ) : (
        <DataTable
          columns={[
            {
              key: 'full_name', label: 'Utilisateur',
              render: (_, row) => {
                const u = row as AdminUser;
                const name = userName(u);
                return (
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[#6D28D9] to-[#7C3AED] flex items-center justify-center text-white text-xs font-bold flex-shrink-0">
                      {name[0]?.toUpperCase() ?? '?'}
                    </div>
                    <div>
                      <p className="font-semibold text-gray-900 text-sm">{name}</p>
                      <p className="text-xs text-gray-400">{u.phone ?? u.email ?? '—'}</p>
                    </div>
                  </div>
                );
              }
            },
            {
              key: 'role', label: 'Rôle',
              render: (v) => (
                <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${
                  v === 'admin' ? 'bg-purple-100 text-purple-700' :
                  v === 'tasker' ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-700'
                }`}>{String(v)}</span>
              )
            },
            {
              key: 'is_verified', label: 'Statut',
              render: (_, row) => {
                const u = row as AdminUser;
                if (u.is_suspended) return <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-red-100 text-red-700">Suspendu</span>;
                if (u.is_locked)    return <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-orange-100 text-orange-700">Verrouillé</span>;
                if (u.is_verified)  return <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-green-100 text-green-700">✓ Vérifié</span>;
                return <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-700">Non vérifié</span>;
              }
            },
            { key: 'country_code', label: 'Pays', render: (v) => (v as string | null) ?? '—' },
            {
              key: 'created_at', label: 'Inscription',
              render: (v) => new Date(v as string).toLocaleDateString('fr-FR')
            },
            {
              key: 'id', label: 'Actions',
              render: (_, row) => {
                const u = row as AdminUser;
                const name = userName(u);
                return (
                  <div className="flex items-center gap-1.5">
                    <button
                      onClick={(e) => { e.stopPropagation(); setDetailUserId(u.id); }}
                      className="p-1.5 rounded-lg hover:bg-blue-50 text-blue-600 transition-colors"
                      title="Voir le profil"
                    >
                      <Eye size={15} />
                    </button>
                    {!u.is_verified && (
                      <button
                        onClick={(e) => { e.stopPropagation(); setPendingAction({ type: 'verify', userId: u.id, userName: name }); setActionError(null); }}
                        className="p-1.5 rounded-lg hover:bg-green-50 text-green-600 transition-colors"
                        title="Vérifier"
                      >
                        <UserCheck size={15} />
                      </button>
                    )}
                    {u.is_suspended ? (
                      <button
                        onClick={(e) => { e.stopPropagation(); setPendingAction({ type: 'unsuspend', userId: u.id, userName: name }); setActionError(null); }}
                        className="p-1.5 rounded-lg hover:bg-green-50 text-green-600 transition-colors"
                        title="Réactiver"
                      >
                        <UserCheck size={15} />
                      </button>
                    ) : (
                      <button
                        onClick={(e) => { e.stopPropagation(); setPendingAction({ type: 'suspend', userId: u.id, userName: name }); setActionError(null); }}
                        className="p-1.5 rounded-lg hover:bg-amber-50 text-amber-600 transition-colors"
                        title="Suspendre"
                      >
                        <UserX size={15} />
                      </button>
                    )}
                    {u.is_locked ? (
                      <button
                        onClick={(e) => { e.stopPropagation(); setPendingAction({ type: 'unlock', userId: u.id, userName: name }); setActionError(null); }}
                        className="p-1.5 rounded-lg hover:bg-green-50 text-green-600 transition-colors"
                        title="Déverrouiller"
                      >
                        <Unlock size={15} />
                      </button>
                    ) : (
                      <button
                        onClick={(e) => { e.stopPropagation(); setPendingAction({ type: 'lock', userId: u.id, userName: name }); setActionError(null); }}
                        className="p-1.5 rounded-lg hover:bg-orange-50 text-orange-600 transition-colors"
                        title="Verrouiller"
                      >
                        <Lock size={15} />
                      </button>
                    )}
                    <button
                      onClick={(e) => { e.stopPropagation(); setPendingAction({ type: 'ban', userId: u.id, userName: name }); setActionError(null); }}
                      className="p-1.5 rounded-lg hover:bg-red-50 text-red-500 transition-colors"
                      title="Bannir"
                    >
                      <ShieldOff size={15} />
                    </button>
                  </div>
                );
              }
            },
          ]}
          data={filtered}
          onRowClick={(row) => setDetailUserId((row as AdminUser).id)}
        />
      )}

      {filtered.length === 0 && !loading && !error && (
        <p className="text-center text-sm text-gray-400 py-8">Aucun utilisateur trouvé.</p>
      )}

      {/* Confirm modal */}
      {pendingAction && cfg && (
        <ConfirmModal
          open={!!pendingAction}
          title={cfg.title}
          description={
            <span>
              Vous êtes sur le point de <strong>{cfg.label.toLowerCase()}</strong>{' '}
              le compte de <strong>{pendingAction.userName}</strong>.
              Cette action sera enregistrée dans le journal d'audit.
            </span>
          }
          confirmLabel={cfg.label}
          variant={cfg.variant}
          requireReason={cfg.requireReason}
          reasonLabel="Raison de l'action"
          loading={actionLoading}
          onConfirm={handleAction}
          onCancel={() => { setPendingAction(null); setActionError(null); }}
        />
      )}

      {/* User detail panel */}
      <UserDetailPanel
        userId={detailUserId}
        onClose={() => setDetailUserId(null)}
      />
    </div>
  );
}
