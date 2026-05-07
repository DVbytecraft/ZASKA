import { useEffect, useState } from 'react';
import { DataTable } from '../components/DataTable';
import { adminApi, type AdminUser } from '../adminApi';

export function UsersPage() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    adminApi.getUsers()
      .then(setUsers)
      .catch((e) => setError(e instanceof Error ? e.message : 'Erreur'))
      .finally(() => setLoading(false));
  }, []);

  const verified = users.filter((u) => u.is_verified).length;
  const pending = users.filter((u) => !u.is_verified).length;

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Utilisateurs</h2>
          <p className="text-sm text-gray-600">Gestion des comptes utilisateurs</p>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-6">
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <span className="text-sm font-medium text-gray-600">Total</span>
          <p className="text-3xl font-bold text-gray-900 mt-2">{loading ? '—' : users.length}</p>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <span className="text-sm font-medium text-gray-600">Vérifiés</span>
          <p className="text-3xl font-bold text-green-600 mt-2">{loading ? '—' : verified}</p>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <span className="text-sm font-medium text-gray-600">Non vérifiés</span>
          <p className="text-3xl font-bold text-yellow-600 mt-2">{loading ? '—' : pending}</p>
        </div>
      </div>

      {loading ? (
        <p className="text-gray-500 text-sm">Chargement...</p>
      ) : error ? (
        <p className="text-red-600 text-sm bg-red-50 rounded-lg p-4">{error}</p>
      ) : users.length === 0 ? (
        <p className="text-gray-500 text-sm">Aucun utilisateur pour l'instant.</p>
      ) : (
        <DataTable
          columns={[
            { key: 'id', label: 'ID', render: (v) => (v as string).slice(0, 8) + '…' },
            { key: 'full_name', label: 'Nom', render: (v, row) => { const n = (v as string | null) ?? `${(row as AdminUser).first_name ?? ''} ${(row as AdminUser).last_name ?? ''}`.trim(); return n || '—'; } },
            { key: 'email', label: 'Email', render: (v) => (v as string | null) ?? '—' },
            { key: 'phone', label: 'Téléphone', render: (v) => (v as string | null) ?? '—' },
            { key: 'is_verified', label: 'Statut', render: (v) => (
              <span className={`px-2 py-1 rounded-full text-xs font-medium ${v ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700'}`}>
                {v ? 'Vérifié' : 'En attente'}
              </span>
            )},
            { key: 'country_code', label: 'Pays', render: (v) => (v as string | null) ?? '—' },
          ]}
          data={users}
        />
      )}
    </div>
  );
}
