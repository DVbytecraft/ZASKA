import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, type SocialProtectionOverview, type SplitHistoryEntry } from "../api";
import { useAuthStore } from "../store";

function formatMoney(value: string, currency: string) {
  const amount = Number.parseFloat(value || "0");
  return new Intl.NumberFormat("fr-FR", {
    style: "currency",
    currency,
    maximumFractionDigits: currency === "XOF" ? 0 : 2,
  }).format(Number.isFinite(amount) ? amount : 0);
}

function formatDate(value: string | null) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleDateString("fr-FR", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

export function SocialProtectionPage() {
  const profile = useAuthStore((s) => s.profile);
  const [overview, setOverview] = useState<SocialProtectionOverview | null>(null);
  const [splits, setSplits] = useState<SplitHistoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      setLoading(true);
      const [overviewRes, splitsRes] = await Promise.all([
        api.getSocialProtection(),
        api.getWalletSplits(undefined, 12, 0),
      ]);

      if (!overviewRes.success) {
        setError(overviewRes.error ?? "Impossible de charger la protection sociale.");
        setLoading(false);
        return;
      }

      setOverview(overviewRes.data);
      setSplits(splitsRes.success ? splitsRes.data : []);
      setError(null);
      setLoading(false);
    }

    if (profile?.role === "tasker") {
      void load();
      return;
    }

    setLoading(false);
  }, [profile?.role]);

  const totalPension = useMemo(() => {
    if (!overview) return [];
    return overview.currencies.map((currencySummary) => ({
      currency: currencySummary.currency,
      value: formatMoney(currencySummary.pension.total_contributed, currencySummary.currency),
    }));
  }, [overview]);

  if (profile && profile.role !== "tasker") {
    return (
      <div className="space-y-4">
        <h2 className="text-xl font-semibold">Ma protection sociale</h2>
        <div className="rounded-2xl border bg-white p-6 text-sm text-gray-600">
          Cette page est réservée aux Taskers protégés par le split social Zaska.
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold">Ma protection sociale</h2>
          <p className="text-sm text-gray-500">
            Suivi de votre retraite, santé, lissage et historique de répartition.
          </p>
        </div>
        <Link
          to="/wallet"
          className="rounded-lg border border-gray-200 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
        >
          Retour au portefeuille
        </Link>
      </div>

      {loading ? (
        <div className="space-y-3">
          <div className="h-28 animate-pulse rounded-2xl bg-gray-100" />
          <div className="h-28 animate-pulse rounded-2xl bg-gray-100" />
          <div className="h-48 animate-pulse rounded-2xl bg-gray-100" />
        </div>
      ) : error ? (
        <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      ) : !overview ? (
        <div className="rounded-2xl border bg-white p-6 text-sm text-gray-500">
          Aucune donnée sociale disponible pour le moment.
        </div>
      ) : (
        <>
          <div className="grid gap-4 md:grid-cols-2">
            <div className="rounded-2xl border bg-white p-5">
              <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Statut</p>
              <div className="mt-3 flex items-center justify-between gap-3">
                <div>
                  <p className="text-lg font-semibold text-gray-900">{overview.badge.label}</p>
                  <p className="text-sm text-gray-500">{overview.badge.description}</p>
                </div>
                <span className="rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold text-emerald-700">
                  {overview.active_months} mois actifs
                </span>
              </div>
              <div className="mt-4 space-y-1 text-sm text-gray-600">
                <p>{overview.total_completed_tasks} tâches validées</p>
                <p>Première activité : {formatDate(overview.first_task_at)}</p>
              </div>
            </div>

            <div className="rounded-2xl border bg-white p-5">
              <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Capital retraite cumulé</p>
              <div className="mt-3 space-y-2">
                {totalPension.length === 0 ? (
                  <p className="text-sm text-gray-500">Aucune cotisation enregistrée.</p>
                ) : (
                  totalPension.map((item) => (
                    <div key={item.currency} className="flex items-center justify-between text-sm">
                      <span className="text-gray-500">{item.currency}</span>
                      <span className="font-semibold text-gray-900">{item.value}</span>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>

          {overview.currencies.map((currencySummary) => (
            <section key={currencySummary.currency} className="space-y-4 rounded-2xl border bg-white p-5">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-lg font-semibold text-gray-900">{currencySummary.currency}</h3>
                  <p className="text-sm text-gray-500">Synthèse sociale par devise</p>
                </div>
                <span className={`rounded-full px-3 py-1 text-xs font-semibold ${
                  currencySummary.health.status === "ACTIVE"
                    ? "bg-green-100 text-green-700"
                    : "bg-gray-100 text-gray-700"
                }`}>
                  Santé {currencySummary.health.status}
                </span>
              </div>

              <div className="grid gap-4 md:grid-cols-3">
                <div className="rounded-xl bg-gray-50 p-4">
                  <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Retraite</p>
                  <div className="mt-3 space-y-2 text-sm">
                    <p className="font-semibold text-gray-900">
                      {formatMoney(currencySummary.pension.total_contributed, currencySummary.currency)}
                    </p>
                    <p className="text-gray-500">
                      Intérêts simulés : {formatMoney(currencySummary.pension.simulated_interest, currencySummary.currency)}
                    </p>
                    <p className="text-gray-500">
                      Projection à 60 ans : {formatMoney(currencySummary.pension.projected_monthly_pension, currencySummary.currency)}/mois
                    </p>
                    <p className="text-gray-500">
                      Progression garantie : {currencySummary.pension.progress_percent_to_guarantee}%
                    </p>
                  </div>
                </div>

                <div className="rounded-xl bg-gray-50 p-4">
                  <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Santé</p>
                  <div className="mt-3 space-y-2 text-sm text-gray-500">
                    <p>Activation : {formatDate(currencySummary.health.activation_date)}</p>
                    <p>Jours couverts ce mois : {currencySummary.health.active_days_this_month}</p>
                    <p>
                      Total versé : {formatMoney(currencySummary.health.total_paid_to_authorities, currencySummary.currency)}
                    </p>
                  </div>
                </div>

                <div className="rounded-xl bg-gray-50 p-4">
                  <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Fonds de lissage</p>
                  <div className="mt-3 space-y-2 text-sm text-gray-500">
                    <p>
                      Solde disponible : {formatMoney(currencySummary.smoothing.available_balance, currencySummary.currency)}
                    </p>
                    <p>
                      Cotisé : {formatMoney(currencySummary.smoothing.total_contributed, currencySummary.currency)}
                    </p>
                    <p>
                      Intérêts reversés retraite : {formatMoney(currencySummary.smoothing.interest_redirected_to_pension, currencySummary.currency)}
                    </p>
                    <p>Interventions : {currencySummary.smoothing.interventions.length}</p>
                    {currencySummary.smoothing.interventions.length > 0 && (
                      <div className="space-y-1 pt-2 text-xs text-gray-600">
                        {currencySummary.smoothing.interventions.slice(0, 3).map((item, index) => (
                          <p key={`${item.period_key ?? item.created_at ?? index}-${index}`}>
                            {item.period_key ?? "Période"} · {formatMoney(item.amount ?? "0", currencySummary.currency)}
                          </p>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </section>
          ))}

          <section className="rounded-2xl border bg-white p-5">
            <div>
              <h3 className="text-lg font-semibold text-gray-900">Historique des splits</h3>
              <p className="text-sm text-gray-500">Détail des tâches déjà validées et réparties.</p>
            </div>

            {splits.length === 0 ? (
              <div className="mt-4 rounded-xl border border-dashed p-6 text-sm text-gray-500">
                Aucun split disponible pour le moment.
              </div>
            ) : (
              <div className="mt-4 space-y-3">
                {splits.map((entry) => (
                  <div key={entry.transaction_id} className="rounded-xl border p-4">
                    <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                      <div>
                        <p className="font-medium text-gray-900">{entry.task_title || "Tâche Zaska"}</p>
                        <p className="text-xs text-gray-500">
                          {formatDate(entry.released_at)} · Brut {formatMoney(entry.gross_amount, entry.currency)}
                        </p>
                      </div>
                      <span className="rounded-full bg-gray-100 px-3 py-1 text-xs font-semibold text-gray-700">
                        {entry.currency}
                      </span>
                    </div>
                    <div className="mt-3 grid gap-2 text-sm text-gray-600 md:grid-cols-2">
                      <p>Votre net : {formatMoney(entry.split.tasker_net, entry.currency)}</p>
                      <p>Zaska : {formatMoney(entry.split.zaska_operations, entry.currency)}</p>
                      <p>Retraite : {formatMoney(entry.split.pension_fund, entry.currency)}</p>
                      <p>Santé : {formatMoney(entry.split.health_fund, entry.currency)}</p>
                      <p>Lissage : {formatMoney(entry.split.smoothing_fund, entry.currency)}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}
