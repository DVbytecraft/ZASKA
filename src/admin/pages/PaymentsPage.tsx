import { useEffect, useState } from 'react';
import { adminApi, type AdminStats } from '../adminApi';

export function PaymentsPage() {
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    adminApi.getStats()
      .then(setStats)
      .catch((e) => setError(e instanceof Error ? e.message : 'Erreur'))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="p-6 space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">Paiements</h2>
        <p className="text-sm text-gray-600">Suivi des transactions de la plateforme</p>
      </div>

      {loading ? (
        <p className="text-gray-500 text-sm">Chargement...</p>
      ) : error ? (
        <p className="text-red-600 text-sm bg-red-50 rounded-lg p-4">{error}</p>
      ) : (
        <div className="grid grid-cols-2 gap-6">
          <div className="bg-white rounded-lg border border-gray-200 p-5">
            <span className="text-sm font-medium text-gray-600">Tâches avec paiement potentiel</span>
            <p className="text-3xl font-bold text-gray-900 mt-2">{stats?.total_tasks ?? 0}</p>
            <p className="text-xs text-gray-400 mt-1">Total des tâches créées</p>
          </div>
          <div className="bg-white rounded-lg border border-gray-200 p-5">
            <span className="text-sm font-medium text-gray-600">Tâches terminées</span>
            <p className="text-3xl font-bold text-green-600 mt-2">{stats?.completed_tasks ?? 0}</p>
            <p className="text-xs text-gray-400 mt-1">Paiements libérés</p>
          </div>
        </div>
      )}

      <div className="bg-blue-50 border border-blue-200 rounded-xl p-5">
        <p className="text-sm text-blue-900 font-medium">Transactions individuelles</p>
        <p className="text-sm text-blue-700 mt-1">
          Les transactions par utilisateur sont accessibles via <code className="bg-blue-100 px-1 rounded">GET /wallet/transactions/&#123;currency&#125;</code>.
          Un tableau de bord financier global sera disponible dans une prochaine version.
        </p>
      </div>
    </div>
  );
}
