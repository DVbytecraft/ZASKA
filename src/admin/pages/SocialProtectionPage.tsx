import { useEffect, useMemo, useState } from 'react';
import { Download, RefreshCw } from 'lucide-react';
import { adminApi, type AdminSocialProtectionOverview } from '../adminApi';

function exportCsv(filename: string, rows: Array<Record<string, unknown>>) {
  if (!rows.length) return;
  const headers = Object.keys(rows[0]);
  const csv = [
    headers.join(','),
    ...rows.map((row) =>
      headers
        .map((header) => `"${String(row[header] ?? '').split('"').join('""')}"`)
        .join(',')
    ),
  ].join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function formatAmount(value: string, currency: string) {
  const amount = Number.parseFloat(value || '0');
  return new Intl.NumberFormat('fr-FR', {
    style: 'currency',
    currency,
    maximumFractionDigits: currency === 'XOF' ? 0 : 2,
  }).format(Number.isFinite(amount) ? amount : 0);
}

export function SocialProtectionPage() {
  const [data, setData] = useState<AdminSocialProtectionOverview | null>(null);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      setData(await adminApi.getSocialProtectionOverview());
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const countryRows = useMemo(
    () =>
      (data?.countries ?? []).map((row) => ({
        country_code: row.country_code,
        users: row.users,
        taskers: row.taskers,
        protected_taskers: row.protected_taskers,
      })),
    [data],
  );

  const taskerRows = useMemo(
    () =>
      (data?.taskers ?? []).map((row) => ({
        tasker_id: row.tasker_id,
        tasker_name: row.tasker_name,
        country_code: row.country_code ?? '',
        badge: row.badge ?? '',
        active_months: row.active_months,
        completed_tasks: row.completed_tasks,
        currencies: row.currencies
          .map((item) => `${item.currency}: pension=${item.pension_total}, santé=${item.health_status}, lissage=${item.smoothing_outstanding}`)
          .join(' | '),
      })),
    [data],
  );

  return (
    <div className="p-4 sm:p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Fonds sociaux</h2>
          <p className="text-sm text-gray-600">Vision comptable et opérationnelle des fonds pension, santé et lissage.</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => void load()} className="flex items-center gap-2 rounded-xl border border-gray-200 px-4 py-2 text-sm font-medium hover:bg-gray-50">
            <RefreshCw size={15} />
            Actualiser
          </button>
          <button onClick={() => exportCsv('zaska_social_countries.csv', countryRows)} className="flex items-center gap-2 rounded-xl border border-gray-200 px-4 py-2 text-sm font-medium hover:bg-gray-50">
            <Download size={15} />
            Export pays
          </button>
          <button onClick={() => exportCsv('zaska_social_taskers.csv', taskerRows)} className="flex items-center gap-2 rounded-xl border border-gray-200 px-4 py-2 text-sm font-medium hover:bg-gray-50">
            <Download size={15} />
            Export taskers
          </button>
        </div>
      </div>

      {loading ? (
        <div className="rounded-xl border bg-white p-8 text-sm text-gray-500">Chargement des fonds sociaux…</div>
      ) : !data ? (
        <div className="rounded-xl border bg-white p-8 text-sm text-red-600">Impossible de charger les données sociales.</div>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
            <div className="rounded-xl border bg-white p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Utilisateurs</p>
              <p className="mt-2 text-2xl font-bold text-gray-900">{data.totals.registered_users}</p>
            </div>
            <div className="rounded-xl border bg-white p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Taskers</p>
              <p className="mt-2 text-2xl font-bold text-gray-900">{data.totals.taskers}</p>
            </div>
            <div className="rounded-xl border bg-white p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Taskers protégés</p>
              <p className="mt-2 text-2xl font-bold text-emerald-700">{data.totals.taskers_protected}</p>
            </div>
            <div className="rounded-xl border bg-white p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Pays actifs</p>
              <p className="mt-2 text-2xl font-bold text-gray-900">{data.totals.countries_active}</p>
            </div>
            <div className="rounded-xl border bg-white p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">KYC à renouveler</p>
              <p className="mt-2 text-2xl font-bold text-amber-700">{data.totals.kyc_due_soon}</p>
            </div>
          </div>

          <div className="grid gap-4 lg:grid-cols-3">
            {data.currencies.map((currency) => (
              <div key={currency.currency} className="rounded-xl border bg-white p-5 space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="text-lg font-bold text-gray-900">{currency.currency}</h3>
                  <span className="text-xs text-gray-400">Mis à jour {new Date(data.generated_at).toLocaleString('fr-FR')}</span>
                </div>
                <div className="space-y-2 text-sm">
                  <p className="flex items-center justify-between"><span className="text-gray-500">Solde pension</span><span className="font-semibold">{formatAmount(currency.pension_balance_total, currency.currency)}</span></p>
                  <p className="flex items-center justify-between"><span className="text-gray-500">Solde santé</span><span className="font-semibold">{formatAmount(currency.health_balance_total, currency.currency)}</span></p>
                  <p className="flex items-center justify-between"><span className="text-gray-500">Solde lissage</span><span className="font-semibold">{formatAmount(currency.smoothing_balance_total, currency.currency)}</span></p>
                  <p className="flex items-center justify-between"><span className="text-gray-500">Cotisations pension</span><span>{formatAmount(currency.pension_contributions_total, currency.currency)}</span></p>
                  <p className="flex items-center justify-between"><span className="text-gray-500">Cotisations santé</span><span>{formatAmount(currency.health_contributions_total, currency.currency)}</span></p>
                  <p className="flex items-center justify-between"><span className="text-gray-500">Cotisations lissage</span><span>{formatAmount(currency.smoothing_contributions_total, currency.currency)}</span></p>
                  <p className="flex items-center justify-between"><span className="text-gray-500">Intérêts simulés/mois</span><span>{formatAmount(currency.simulated_interest_month, currency.currency)}</span></p>
                  <p className="flex items-center justify-between"><span className="text-gray-500">Interventions ce mois</span><span>{currency.smoothing_interventions_month}</span></p>
                  <p className="flex items-center justify-between"><span className="text-gray-500">Reconstitution à récupérer</span><span>{formatAmount(currency.smoothing_outstanding_total, currency.currency)}</span></p>
                </div>
              </div>
            ))}
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <div className="rounded-xl border bg-white p-5">
              <h3 className="text-lg font-bold text-gray-900 mb-4">Inscrits par pays</h3>
              <div className="space-y-3">
                {data.countries.map((row) => (
                  <div key={row.country_code} className="grid grid-cols-4 gap-3 text-sm">
                    <span className="font-medium text-gray-900">{row.country_code}</span>
                    <span className="text-gray-600">{row.users} inscrits</span>
                    <span className="text-gray-600">{row.taskers} taskers</span>
                    <span className="text-emerald-700">{row.protected_taskers} protégés</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-xl border bg-white p-5">
              <h3 className="text-lg font-bold text-gray-900 mb-4">Taskers sociaux</h3>
              <div className="space-y-3 max-h-[420px] overflow-auto">
                {data.taskers.slice(0, 25).map((row) => (
                  <div key={row.tasker_id} className="rounded-lg border p-3">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <p className="font-semibold text-gray-900">{row.tasker_name}</p>
                        <p className="text-xs text-gray-500">{row.country_code ?? '—'} · {row.completed_tasks} tâches · {row.active_months} mois</p>
                      </div>
                      <span className="rounded-full bg-gray-100 px-3 py-1 text-xs font-medium text-gray-700">{row.badge ?? '—'}</span>
                    </div>
                    <div className="mt-2 space-y-1 text-xs text-gray-600">
                      {row.currencies.map((item) => (
                        <p key={`${row.tasker_id}-${item.currency}`}>
                          {item.currency} · pension {item.pension_total} · santé {item.health_status} · lissage {item.smoothing_outstanding}
                        </p>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
