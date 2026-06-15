import { useEffect, useMemo, useState } from 'react';
import { Download, RefreshCw } from 'lucide-react';
import { adminApi, type AdminAccountingOverview } from '../adminApi';

function exportCsv(filename: string, rows: Array<Record<string, unknown>>) {
  if (!rows.length) return;
  const headers = Object.keys(rows[0]);
  const csv = [
    headers.join(','),
    ...rows.map((row) =>
      headers.map((header) => `"${String(row[header] ?? '').split('"').join('""')}"`).join(',')
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

function formatPercentBadgeColor(drift: string) {
  return Number.parseFloat(drift) === 0 ? 'text-emerald-700 bg-emerald-50' : 'text-amber-700 bg-amber-50';
}

export function AccountingPage() {
  const [data, setData] = useState<AdminAccountingOverview | null>(null);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      setData(await adminApi.getAccountingOverview());
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const reconciliationRows = useMemo(() => {
    if (!data) return [];
    return data.currencies.flatMap((item) =>
      Object.entries(item.fund_balances).map(([fundCode, snapshot]) => ({
        currency: item.currency,
        fund_code: fundCode,
        wallet_balance: snapshot.wallet_balance,
        ledger_balance: snapshot.ledger_balance,
        drift: snapshot.drift,
      }))
    );
  }, [data]);

  const badgeRows = useMemo(() => {
    if (!data) return [];
    return data.tasker_badges.taskers.map((row) => ({
      tasker_id: row.tasker_id,
      tasker_name: row.tasker_name,
      country_code: row.country_code ?? '',
      rating_avg: row.rating_avg ?? '',
      rating_count: row.rating_count,
      completed_tasks: row.completed_tasks,
      active_months: row.active_months,
      security_verified: row.tasker_security_verified,
      criminal_record_status: row.criminal_record_status,
      social_badge: row.social_badge?.label ?? '',
      public_badges: row.public_badges.map((badge) => badge.label).join(' | '),
    }));
  }, [data]);

  return (
    <div className="p-4 sm:p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Comptabilité</h2>
          <p className="text-sm text-gray-600">Suivi des splits, réconciliation interne et registre des badges Tasker.</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => void load()} className="flex items-center gap-2 rounded-xl border border-gray-200 px-4 py-2 text-sm font-medium hover:bg-gray-50">
            <RefreshCw size={15} />
            Actualiser
          </button>
          <button onClick={() => exportCsv('zaska_accounting_reconciliation.csv', reconciliationRows)} className="flex items-center gap-2 rounded-xl border border-gray-200 px-4 py-2 text-sm font-medium hover:bg-gray-50">
            <Download size={15} />
            Export réconciliation
          </button>
          <button onClick={() => exportCsv('zaska_tasker_badges.csv', badgeRows)} className="flex items-center gap-2 rounded-xl border border-gray-200 px-4 py-2 text-sm font-medium hover:bg-gray-50">
            <Download size={15} />
            Export badges
          </button>
        </div>
      </div>

      {loading ? (
        <div className="rounded-xl border bg-white p-8 text-sm text-gray-500">Chargement comptable…</div>
      ) : !data ? (
        <div className="rounded-xl border bg-white p-8 text-sm text-red-600">Impossible de charger les données comptables.</div>
      ) : (
        <>
          <div className="grid gap-4 md:grid-cols-3">
            <div className="rounded-xl border bg-white p-5">
              <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Tâches libérées</p>
              <p className="mt-2 text-2xl font-bold text-gray-900">{data.summary.released_tasks_count}</p>
            </div>
            <div className="rounded-xl border bg-white p-5">
              <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Devises suivies</p>
              <p className="mt-2 text-2xl font-bold text-gray-900">{data.summary.currencies_count}</p>
            </div>
            <div className="rounded-xl border bg-white p-5">
              <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Badges publics actifs</p>
              <p className="mt-2 text-2xl font-bold text-gray-900">
                {data.tasker_badges.counts.reduce((sum, item) => sum + item.count, 0)}
              </p>
            </div>
          </div>

          <div className="grid gap-4 xl:grid-cols-2">
            {data.currencies.map((item) => (
              <div key={item.currency} className="rounded-xl border bg-white p-5 space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-lg font-bold text-gray-900">{item.currency}</h3>
                  <span className="text-xs text-gray-400">Mis à jour {new Date(data.generated_at).toLocaleString('fr-FR')}</span>
                </div>

                <div className="grid gap-3 md:grid-cols-2">
                  <div className="rounded-lg bg-gray-50 p-4">
                    <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Split du mois</p>
                    <div className="mt-3 space-y-2 text-sm">
                      <p className="flex justify-between"><span>Taskers</span><span>{formatAmount(item.month.tasker_net, item.currency)}</span></p>
                      <p className="flex justify-between"><span>Zaska 8%</span><span>{formatAmount(item.month.zaska_operations, item.currency)}</span></p>
                      <p className="flex justify-between"><span>Pension</span><span>{formatAmount(item.month.pension_fund, item.currency)}</span></p>
                      <p className="flex justify-between"><span>Santé</span><span>{formatAmount(item.month.health_fund, item.currency)}</span></p>
                      <p className="flex justify-between"><span>Lissage</span><span>{formatAmount(item.month.smoothing_fund, item.currency)}</span></p>
                    </div>
                  </div>
                  <div className="rounded-lg bg-gray-50 p-4">
                    <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Split annuel</p>
                    <div className="mt-3 space-y-2 text-sm">
                      <p className="flex justify-between"><span>Taskers</span><span>{formatAmount(item.year.tasker_net, item.currency)}</span></p>
                      <p className="flex justify-between"><span>Zaska 8%</span><span>{formatAmount(item.year.zaska_operations, item.currency)}</span></p>
                      <p className="flex justify-between"><span>Pension</span><span>{formatAmount(item.year.pension_fund, item.currency)}</span></p>
                      <p className="flex justify-between"><span>Santé</span><span>{formatAmount(item.year.health_fund, item.currency)}</span></p>
                      <p className="flex justify-between"><span>Lissage</span><span>{formatAmount(item.year.smoothing_fund, item.currency)}</span></p>
                    </div>
                  </div>
                </div>

                <div className="rounded-lg border p-4">
                  <p className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-3">Réconciliation interne</p>
                  <div className="space-y-3 text-sm">
                    {Object.entries(item.fund_balances).map(([fundCode, snapshot]) => (
                      <div key={`${item.currency}-${fundCode}`} className="rounded-lg bg-gray-50 p-3">
                        <div className="flex items-center justify-between gap-3">
                          <span className="font-medium text-gray-900">{fundCode}</span>
                          <span className={`rounded-full px-2 py-1 text-xs font-semibold ${formatPercentBadgeColor(snapshot.drift)}`}>
                            drift {formatAmount(snapshot.drift, item.currency)}
                          </span>
                        </div>
                        <div className="mt-2 grid gap-2 md:grid-cols-2">
                          <p className="flex justify-between"><span className="text-gray-500">Wallet</span><span>{formatAmount(snapshot.wallet_balance, item.currency)}</span></p>
                          <p className="flex justify-between"><span className="text-gray-500">Ledger</span><span>{formatAmount(snapshot.ledger_balance, item.currency)}</span></p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="grid gap-3 md:grid-cols-2">
                  <div className="rounded-lg bg-amber-50 p-4">
                    <p className="text-xs font-semibold uppercase tracking-wide text-amber-700">Lissage</p>
                    <div className="mt-3 space-y-2 text-sm">
                      <p className="flex justify-between"><span>Interventions total</span><span>{formatAmount(item.event_totals.smoothing_interventions_total, item.currency)}</span></p>
                      <p className="flex justify-between"><span>Remboursements total</span><span>{formatAmount(item.event_totals.smoothing_reimbursements_total, item.currency)}</span></p>
                      <p className="flex justify-between"><span>Interventions mois</span><span>{item.event_totals.smoothing_interventions_month}</span></p>
                      <p className="flex justify-between"><span>Remboursements mois</span><span>{item.event_totals.smoothing_reimbursements_month}</span></p>
                    </div>
                  </div>
                  <div className="rounded-lg bg-indigo-50 p-4">
                    <p className="text-xs font-semibold uppercase tracking-wide text-indigo-700">Intérêts simulés</p>
                    <div className="mt-3 space-y-2 text-sm">
                      <p className="flex justify-between"><span>Pension / mois</span><span>{formatAmount(item.simulated_interest.pension_month, item.currency)}</span></p>
                      <p className="flex justify-between"><span>Lissage / mois</span><span>{formatAmount(item.simulated_interest.smoothing_month, item.currency)}</span></p>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>

          <div className="grid gap-6 xl:grid-cols-[320px_1fr]">
            <div className="rounded-xl border bg-white p-5">
              <h3 className="text-lg font-bold text-gray-900 mb-4">Répartition des badges</h3>
              <div className="space-y-3">
                {data.tasker_badges.counts.map((badge) => (
                  <div key={badge.code} className="rounded-lg border p-3">
                    <div className="flex items-center justify-between gap-3">
                      <span className="font-medium text-gray-900">{badge.label}</span>
                      <span className="rounded-full bg-gray-100 px-2 py-1 text-xs font-semibold text-gray-700">{badge.count}</span>
                    </div>
                    <p className="mt-1 text-xs text-gray-500">{badge.description}</p>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-xl border bg-white p-5">
              <h3 className="text-lg font-bold text-gray-900 mb-4">Registre badges Taskers</h3>
              <div className="space-y-3 max-h-[680px] overflow-auto">
                {data.tasker_badges.taskers.map((row) => (
                  <div key={row.tasker_id} className="rounded-lg border p-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold text-gray-900">{row.tasker_name}</p>
                        <p className="text-xs text-gray-500">
                          {row.country_code ?? '—'} · {row.completed_tasks} tâches · {row.active_months} mois · {row.rating_avg ?? '—'}/5
                        </p>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {row.public_badges.length === 0 ? (
                          <span className="rounded-full bg-gray-100 px-3 py-1 text-xs font-medium text-gray-600">Aucun badge public</span>
                        ) : (
                          row.public_badges.map((badge) => (
                            <span key={`${row.tasker_id}-${badge.code}`} className="rounded-full bg-black px-3 py-1 text-xs font-medium text-white">
                              {badge.label}
                            </span>
                          ))
                        )}
                      </div>
                    </div>
                    <div className="mt-3 grid gap-2 text-xs text-gray-600 md:grid-cols-3">
                      <p>Sécurité tasker: <span className="font-semibold">{row.tasker_security_verified ? 'OK' : 'À compléter'}</span></p>
                      <p>Casier: <span className="font-semibold">{row.criminal_record_status}</span></p>
                      <p>Badge social: <span className="font-semibold">{row.social_badge?.label ?? '—'}</span></p>
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
