import { useEffect, useState } from 'react';
import { DataTable } from '../components/DataTable';
import { adminApi } from '../adminApi';

interface Country {
  code: string;
  currency: string;
  mobile_money_enabled: boolean;
  payment_providers: string[];
}

export function CountriesPage() {
  const [countries, setCountries] = useState<Country[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    adminApi.getCountries()
      .then(setCountries)
      .catch((e) => setError(e instanceof Error ? e.message : 'Erreur'))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="p-6 space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">Pays configurés</h2>
        <p className="text-sm text-gray-600">Pays activés dans le moteur de paiement</p>
      </div>

      <div className="grid grid-cols-2 gap-6">
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <span className="text-sm font-medium text-gray-600">Pays actifs</span>
          <p className="text-3xl font-bold text-gray-900 mt-2">{loading ? '—' : countries.length}</p>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <span className="text-sm font-medium text-gray-600">Mobile Money actif</span>
          <p className="text-3xl font-bold text-green-600 mt-2">
            {loading ? '—' : countries.filter((c) => c.mobile_money_enabled).length}
          </p>
        </div>
      </div>

      {loading ? (
        <p className="text-sm text-gray-400">Chargement...</p>
      ) : error ? (
        <p className="text-red-600 text-sm bg-red-50 rounded-lg p-4">{error}</p>
      ) : (
        <DataTable
          columns={[
            { key: 'code', label: 'Code pays' },
            { key: 'currency', label: 'Devise' },
            { key: 'mobile_money_enabled', label: 'Mobile Money', render: (v) => (
              <span className={`px-2 py-1 rounded-full text-xs font-medium ${v ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                {v ? 'Activé' : 'Désactivé'}
              </span>
            )},
            { key: 'payment_providers', label: 'Providers', render: (v) => (v as string[]).join(', ') },
          ]}
          data={countries}
        />
      )}
    </div>
  );
}
