import { useEffect, useState } from "react";
import { TargetLocationPicker } from "../components/TargetLocationPicker";
import { marketplaceApi, type TargetLocationValue, type VtcOperatorSummary, type VtcRideResponse } from "../services/marketplaceApi";
import { useAuthStore } from "../store";

function formatMoney(value: string | number | null | undefined, currency?: string) {
  if (value == null) return "—";
  const amount = typeof value === "number" ? value : Number(value);
  return `${currency ?? ""} ${Number.isFinite(amount) ? amount.toLocaleString("fr-FR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : value}`;
}

export function VtcPage() {
  const profile = useAuthStore((s) => s.profile);
  const [target, setTarget] = useState<TargetLocationValue | null>(null);
  const [operators, setOperators] = useState<VtcOperatorSummary[]>([]);
  const [selectedOperator, setSelectedOperator] = useState<VtcOperatorSummary | null>(null);
  const [destinationAddress, setDestinationAddress] = useState("");
  const [passengerName, setPassengerName] = useState("");
  const [passengerPhone, setPassengerPhone] = useState("");
  const [quote, setQuote] = useState<Record<string, unknown> | null>(null);
  const [rides, setRides] = useState<VtcRideResponse[]>([]);
  const [error, setError] = useState<string | null>(null);

  const loadRides = async () => {
    const res = await marketplaceApi.listMyVtcRides();
    if (res.success) setRides(res.data);
  };

  useEffect(() => {
    void loadRides();
  }, []);

  useEffect(() => {
    if (!target?.countryCode || !target.cityName) return;
    void marketplaceApi
      .listVtcOperators({
        country_code: target.countryCode,
        city_name: target.cityName,
        active_only: true,
        limit: 30,
      })
      .then((res) => {
        if (res.success) setOperators(res.data);
      });
  }, [target?.countryCode, target?.cityName]);

  const computeQuote = async () => {
    if (!selectedOperator || !target) {
      setError("Choisissez une zone cible et un opérateur VTC.");
      return;
    }
    const res = await marketplaceApi.quoteVtcRide({
      currency: selectedOperator.currency,
      operator_id: selectedOperator.id,
      pickup_latitude: target.latitude ?? null,
      pickup_longitude: target.longitude ?? null,
      destination_latitude: target.latitude ?? null,
      destination_longitude: target.longitude ?? null,
      ride_type: "standard",
    });
    if (!res.success) {
      setError(res.error ?? "Impossible de calculer le tarif");
      return;
    }
    setQuote(res.data);
  };

  const createRide = async () => {
    if (!selectedOperator || !target) {
      setError("Choisissez la zone de prise en charge et un opérateur.");
      return;
    }
    const isRemote = target.mode === "remote";
    const res = await marketplaceApi.createVtcRide({
      pickup_address: target.address || `${target.cityName}, ${target.countryCode}`,
      destination_address: destinationAddress || target.address || `${target.cityName}, ${target.countryCode}`,
      currency: selectedOperator.currency,
      operator_id: selectedOperator.id,
      pickup_latitude: target.latitude ?? null,
      pickup_longitude: target.longitude ?? null,
      destination_latitude: target.latitude ?? null,
      destination_longitude: target.longitude ?? null,
      passenger_name: isRemote ? passengerName || "Passager" : null,
      passenger_phone: isRemote ? passengerPhone || null : null,
      ride_type: "standard",
    });
    if (!res.success) {
      setError(res.error ?? "Impossible de créer la course");
      return;
    }
    setQuote(res.data.pricingBreakdown as Record<string, unknown> | null);
    await loadRides();
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">Réserver un VTC</h2>
        <p className="text-sm text-gray-500 mt-1">
          Réservez une course locale ou pour un proche dans une autre ville ou un autre pays couvert.
        </p>
      </div>

      <TargetLocationPicker storageKey="zaska-vtc-target" defaultCountryCode={profile?.country_code} onChange={setTarget} />

      {error && <div className="rounded-xl bg-red-50 border border-red-100 text-red-700 px-4 py-3 text-sm">{error}</div>}

      <div className="grid gap-6 lg:grid-cols-[1fr,1.3fr]">
        <section className="space-y-3">
          <h3 className="text-lg font-semibold text-gray-900">Opérateurs disponibles</h3>
          <div className="space-y-3">
            {operators.map((operator) => (
              <button
                key={operator.id}
                type="button"
                onClick={() => setSelectedOperator(operator)}
                className={`w-full rounded-2xl border p-4 text-left transition-shadow hover:shadow-sm ${selectedOperator?.id === operator.id ? "border-black bg-gray-50" : "border-gray-200 bg-white"}`}
              >
                <h4 className="font-semibold text-gray-900">{operator.publicName}</h4>
                <p className="text-sm text-gray-500 mt-1">{operator.description || `${operator.cityName}, ${operator.countryCode}`}</p>
                <p className="text-xs text-gray-400 mt-2">{operator.currency} · {operator.acceptingRides ? "Accepte les courses" : "Indisponible"}</p>
              </button>
            ))}
            {operators.length === 0 && (
              <div className="rounded-2xl border border-dashed border-gray-300 bg-gray-50 p-6 text-sm text-gray-500">
                Aucun opérateur VTC visible pour cette zone.
              </div>
            )}
          </div>
        </section>

        <section className="space-y-4">
          <div className="rounded-2xl border border-gray-200 bg-white p-5 space-y-4">
            <div>
              <h3 className="text-lg font-semibold text-gray-900">Préparer la course</h3>
              <p className="text-sm text-gray-500 mt-1">
                Définissez la destination et, si besoin, les informations du passager distant.
              </p>
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Adresse de destination</label>
              <input
                type="text"
                className="w-full rounded-xl border border-gray-200 px-3 py-2.5 text-sm"
                placeholder="Ex: Rue de Rivoli, Paris"
                value={destinationAddress}
                onChange={(e) => setDestinationAddress(e.target.value)}
              />
            </div>

            {target?.mode === "remote" && (
              <div className="grid gap-3 md:grid-cols-2">
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Nom du passager</label>
                  <input
                    type="text"
                    className="w-full rounded-xl border border-gray-200 px-3 py-2.5 text-sm"
                    value={passengerName}
                    onChange={(e) => setPassengerName(e.target.value)}
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Téléphone du passager</label>
                  <input
                    type="text"
                    className="w-full rounded-xl border border-gray-200 px-3 py-2.5 text-sm"
                    value={passengerPhone}
                    onChange={(e) => setPassengerPhone(e.target.value)}
                  />
                </div>
              </div>
            )}

            <div className="flex flex-wrap gap-3">
              <button type="button" onClick={() => void computeQuote()} className="rounded-xl border border-gray-200 px-4 py-2 text-sm font-medium hover:bg-gray-50">
                Calculer le tarif
              </button>
              <button type="button" onClick={() => void createRide()} className="rounded-xl bg-black px-4 py-2 text-sm font-medium text-white">
                Demander la course
              </button>
            </div>

            {quote && (
              <div className="rounded-xl bg-emerald-50 border border-emerald-100 p-4 text-sm text-emerald-800">
                <p className="font-semibold">Devis course prêt</p>
                <pre className="mt-2 text-xs whitespace-pre-wrap">{JSON.stringify(quote, null, 2)}</pre>
              </div>
            )}
          </div>

          <div className="rounded-2xl border border-gray-200 bg-white p-5">
            <h3 className="text-lg font-semibold text-gray-900">Mes courses</h3>
            <div className="mt-4 space-y-3">
              {rides.map((ride) => (
                <div key={ride.id} className="rounded-xl border border-gray-100 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="font-medium text-gray-900">{ride.pickupAddress}</p>
                      <p className="text-sm text-gray-500 mt-1">{ride.destinationAddress}</p>
                    </div>
                    <div className="text-right">
                      <p className="text-sm font-semibold text-gray-900">{formatMoney(ride.totalFare || ride.estimatedFare, ride.currency)}</p>
                      <p className="text-xs text-gray-500 mt-1">{ride.status}</p>
                    </div>
                  </div>
                </div>
              ))}
              {rides.length === 0 && <p className="text-sm text-gray-500">Aucune course pour le moment.</p>}
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
