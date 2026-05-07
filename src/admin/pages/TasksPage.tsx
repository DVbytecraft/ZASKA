import { useEffect, useState } from 'react';
import { DataTable } from '../components/DataTable';
import { adminApi, type AdminTask } from '../adminApi';

export function TasksPage() {
  const [tasks, setTasks] = useState<AdminTask[]>([]);
  const [filter, setFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    adminApi.getTasks()
      .then(setTasks)
      .catch((e) => setError(e instanceof Error ? e.message : 'Erreur'))
      .finally(() => setLoading(false));
  }, []);

  const displayed = filter ? tasks.filter((t) => t.status === filter) : tasks;

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Tâches</h2>
          <p className="text-sm text-gray-600">Toutes les tâches de la plateforme</p>
        </div>
        <select
          className="px-4 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#6D28D9]"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        >
          <option value="">Tous les statuts</option>
          <option value="OPEN">Ouvertes</option>
          <option value="ASSIGNED">Assignées</option>
          <option value="COMPLETED">Terminées</option>
        </select>
      </div>

      {loading ? (
        <p className="text-gray-500 text-sm">Chargement...</p>
      ) : error ? (
        <p className="text-red-600 text-sm bg-red-50 rounded-lg p-4">{error}</p>
      ) : displayed.length === 0 ? (
        <p className="text-gray-500 text-sm">Aucune tâche{filter ? ` avec le statut "${filter}"` : ''}.</p>
      ) : (
        <DataTable
          columns={[
            { key: 'id', label: 'ID', render: (v) => (v as string).slice(0, 8) + '…' },
            { key: 'title', label: 'Titre' },
            { key: 'status', label: 'Statut', render: (value) => (
              <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                value === 'COMPLETED' ? 'bg-green-100 text-green-700' :
                value === 'ASSIGNED' ? 'bg-blue-100 text-blue-700' :
                'bg-gray-100 text-gray-700'
              }`}>{value}</span>
            )},
            { key: 'price', label: 'Prix', render: (v, row) => `${v} ${(row as AdminTask).currency}` },
            { key: 'created_at', label: 'Créé le', render: (v) => new Date(v as string).toLocaleDateString('fr-FR') },
          ]}
          data={displayed}
        />
      )}
    </div>
  );
}
