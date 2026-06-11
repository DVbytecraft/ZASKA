import { useEffect, useState } from "react";
import { marketplaceApi, type VtcRideResponse } from "../services/marketplaceApi";

const rideActions: Array<{
  value: "en-route" | "arrived" | "start" | "complete" | "cancel";
  label: string;
}> = [
  { value: "en-route", label: "En route" },
  { value: "arrived", label: "Arrivé" },
  { value: "start", label: "Démarrer" },
  { value: "complete", label: "Terminer" },
  { value: "cancel", label: "Annuler" },
];

export function DriverPortalPage() {
  const [dashboard, setDashboard] = useState<Record<string, unknown> | null>(null);
  const [offers, setOffers] = useState<Record<string, unknown>[]>([]);
  const [rides, setRides] = useState<VtcRideResponse[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [latitude, setLatitude] = useState("");
  const [longitude, setLongitude] = useState("");
  const [isOnline, setIsOnline] = useState(false);

  const load = async () => {
    const [dashboardRes, offersRes, ridesRes] = await Promise.all([
      marketplaceApi.getDriverDashboard(),
      marketplaceApi.listDriverOffers(),
      marketplaceApi.listDriverRides(),
    ]);
    if (dashboardRes.success) setDashboard(dashboardRes.data);
    if (offersRes.success) setOffers(offersRes.data);
    if (ridesRes.success) setRides(ridesRes.data);
  };

  useEffect(() => {
    void load();
  }, []);

  const updatePresence = async () => {
    const res = await marketplaceApi.updateDriverPresence({
      is_online: isOnline,
      latitude: latitude ? Number(latitude) : null,
      longitude: longitude ? Number(longitude) : null,
    });
    if (!res.success) {
      setError(res.error ?? "Impossible de mettre à jour la présence");
      return;
    }
    await load();
  };

  const respondOffer = async (offerId: string, accept: boolean) => {
    const res = await marketplaceApi.respondDriverOffer(offerId, accept);
    if (!res.success) {
      setError(res.error ?? "Impossible de répondre à l’offre");
      return;
    }
    await load();
  };

  const actOnRide = async (
    rideId: string,
    action: "en-route" | "arrived" | "start" | "complete" | "cancel",
  ) => {
    const mapping = {
      "en-route": () => marketplaceApi.driverRideEnRoute(rideId),
      arrived: () => marketplaceApi.driverRideArrived(rideId),
      start: () => marketplaceApi.driverRideStart(rideId),
      complete: () => marketplaceApi.driverRideComplete(rideId),
      cancel: () => marketplaceApi.driverRideCancel(rideId),
    } as const;
    const res = await mapping[action]();
    if (!res.success) {
      setError(res.error ?? "Impossible de mettre à jour la course");
      return;
    }
    await load();
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">Espace chauffeur</h2>
        <p className="mt-1 text-sm text-gray-500">
          Activez votre présence, traitez les offres et faites avancer vos courses.
        </p>
      </div>

      {error ? (
        <div className="rounded-xl border border-red-100 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>
      ) : null}

      <section className="space-y-4 rounded-2xl border border-gray-200 bg-white p-5">
        <h3 className="text-lg font-semibold text-gray-900">Présence chauffeur</h3>
        <div className="grid gap-3 md:grid-cols-3">
          <label className="flex items-center gap-2 rounded-xl border border-gray-200 px-3 py-2 text-sm">
            <input type="checkbox" checked={isOnline} onChange={(event) => setIsOnline(event.target.checked)} />
            En ligne
          </label>
          <input
            type="number"
            step="0.000001"
            placeholder="Latitude"
            value={latitude}
            onChange={(event) => setLatitude(event.target.value)}
            className="rounded-xl border border-gray-200 px-3 py-2 text-sm"
          />
          <input
            type="number"
            step="0.000001"
            placeholder="Longitude"
            value={longitude}
            onChange={(event) => setLongitude(event.target.value)}
            className="rounded-xl border border-gray-200 px-3 py-2 text-sm"
          />
        </div>
        <button
          type="button"
          onClick={() => void updatePresence()}
          className="rounded-xl bg-black px-4 py-2 text-sm font-medium text-white"
        >
          Mettre à jour ma présence
        </button>
        <pre className="overflow-auto rounded-xl bg-gray-50 p-4 text-xs text-gray-700">
          {JSON.stringify(dashboard, null, 2)}
        </pre>
      </section>

      <section className="rounded-2xl border border-gray-200 bg-white p-5">
        <h3 className="text-lg font-semibold text-gray-900">Offres de courses</h3>
        <div className="mt-4 space-y-3">
          {offers.map((offer, index) => (
            <div key={String(offer.id ?? index)} className="rounded-xl border border-gray-100 p-4">
              <pre className="overflow-auto text-xs text-gray-700">{JSON.stringify(offer, null, 2)}</pre>
              {offer.id ? (
                <div className="mt-3 flex gap-2">
                  <button
                    type="button"
                    onClick={() => void respondOffer(String(offer.id), true)}
                    className="rounded-xl bg-black px-3 py-2 text-xs font-medium text-white"
                  >
                    Accepter
                  </button>
                  <button
                    type="button"
                    onClick={() => void respondOffer(String(offer.id), false)}
                    className="rounded-xl border border-gray-200 px-3 py-2 text-xs font-medium hover:bg-gray-50"
                  >
                    Refuser
                  </button>
                </div>
              ) : null}
            </div>
          ))}
          {offers.length === 0 ? <p className="text-sm text-gray-500">Aucune offre pour le moment.</p> : null}
        </div>
      </section>

      <section className="rounded-2xl border border-gray-200 bg-white p-5">
        <h3 className="text-lg font-semibold text-gray-900">Mes courses chauffeur</h3>
        <div className="mt-4 space-y-3">
          {rides.map((ride) => (
            <div key={ride.id} className="space-y-3 rounded-xl border border-gray-100 p-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="font-medium text-gray-900">{ride.pickupAddress}</p>
                  <p className="mt-1 text-sm text-gray-500">{ride.destinationAddress}</p>
                </div>
                <span className="rounded-full bg-gray-100 px-3 py-1 text-xs font-semibold">{ride.status}</span>
              </div>
              <div className="flex flex-wrap gap-2">
                {rideActions.map((action) => (
                  <button
                    key={action.value}
                    type="button"
                    onClick={() => void actOnRide(ride.id, action.value)}
                    className="rounded-full border border-gray-200 px-3 py-1 text-xs hover:bg-gray-50"
                  >
                    {action.label}
                  </button>
                ))}
              </div>
            </div>
          ))}
          {rides.length === 0 ? (
            <p className="text-sm text-gray-500">Aucune course chauffeur pour le moment.</p>
          ) : null}
        </div>
      </section>
    </div>
  );
}
