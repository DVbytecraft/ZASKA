import { useEffect, useState } from 'react';
import { Headphones } from 'lucide-react';
import { adminApi, type AdminUser, type AdminTask } from '../adminApi';
import { DataTable } from '../components/DataTable';

export function CallCenterPage() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [tasks, setTasks] = useState<AdminTask[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([adminApi.getUsers(), adminApi.getTasks()])
      .then(([u, t]) => {
        setUsers(u.filter((user) => !user.is_verified));
        setTasks(t.filter((task) => task.status === 'OPEN'));
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="p-6 space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">Call Center</h2>
        <p className="text-sm text-gray-600">Utilisateurs et tâches nécessitant une attention</p>
      </div>

      {loading ? (
        <p className="text-sm text-gray-400">Chargement...</p>
      ) : (
        <>
          <div>
            <h3 className="text-base font-semibold text-gray-800 mb-3 flex items-center gap-2">
              <Headphones size={16} className="text-[#6D28D9]" />
              Comptes non vérifiés ({users.length})
            </h3>
            {users.length === 0 ? (
              <p className="text-sm text-gray-400">Aucun compte en attente.</p>
            ) : (
              <DataTable
                columns={[
                  { key: 'full_name', label: 'Nom', render: (v, row) => { const n = (v as string | null) ?? `${(row as AdminUser).first_name ?? ''} ${(row as AdminUser).last_name ?? ''}`.trim(); return n || '—'; } },
                  { key: 'email', label: 'Email', render: (v) => (v as string | null) ?? '—' },
                  { key: 'phone', label: 'Téléphone', render: (v) => (v as string | null) ?? '—' },
                  { key: 'country_code', label: 'Pays', render: (v) => (v as string | null) ?? '—' },
                ]}
                data={users}
              />
            )}
          </div>

          <div>
            <h3 className="text-base font-semibold text-gray-800 mb-3">
              Tâches ouvertes sans assignation ({tasks.length})
            </h3>
            {tasks.length === 0 ? (
              <p className="text-sm text-gray-400">Aucune tâche en attente.</p>
            ) : (
              <DataTable
                columns={[
                  { key: 'id', label: 'ID', render: (v) => (v as string).slice(0, 8) + '…' },
                  { key: 'title', label: 'Titre' },
                  { key: 'price', label: 'Prix', render: (v, row) => `${v} ${(row as AdminTask).currency}` },
                  { key: 'created_at', label: 'Créé le', render: (v) => new Date(v as string).toLocaleDateString('fr-FR') },
                ]}
                data={tasks}
              />
            )}
          </div>
        </>
      )}
    </div>
  );
}
