import { useEffect, useMemo, useState } from "react";
import { TargetLocationPicker } from "../components/TargetLocationPicker";
import { marketplaceApi, type FoodOrderResponse, type FoodRestaurantDetail, type FoodRestaurantSummary, type TargetLocationValue } from "../services/marketplaceApi";
import { useAuthStore } from "../store";

function formatMoney(value: string | number | undefined, currency?: string) {
  if (value == null) return "—";
  const amount = typeof value === "number" ? value : Number(value);
  return `${currency ?? ""} ${Number.isFinite(amount) ? amount.toLocaleString("fr-FR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : value}`;
}

export function FoodPage() {
  const profile = useAuthStore((s) => s.profile);
  const [target, setTarget] = useState<TargetLocationValue | null>(null);
  const [restaurants, setRestaurants] = useState<FoodRestaurantSummary[]>([]);
  const [selectedRestaurant, setSelectedRestaurant] = useState<FoodRestaurantDetail | null>(null);
  const [quantities, setQuantities] = useState<Record<string, number>>({});
  const [selectedModifiers, setSelectedModifiers] = useState<Record<string, string[]>>({});
  const [deliveryQuote, setDeliveryQuote] = useState<Record<string, unknown> | null>(null);
  const [createdOrder, setCreatedOrder] = useState<FoodOrderResponse | null>(null);
  const [myOrders, setMyOrders] = useState<FoodOrderResponse[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedItems = useMemo(
    () => Object.entries(quantities).filter(([, quantity]) => quantity > 0),
    [quantities],
  );

  const loadOrders = async () => {
    const res = await marketplaceApi.listMyFoodOrders();
    if (res.success) setMyOrders(res.data);
  };

  useEffect(() => {
    void loadOrders();
  }, []);

  useEffect(() => {
    if (!target?.countryCode || !target.cityName) return;
    setLoading(true);
    setError(null);
    void marketplaceApi
      .listFoodRestaurants({
        country_code: target.countryCode,
        city_name: target.cityName,
        reference_latitude: target.latitude ?? undefined,
        reference_longitude: target.longitude ?? undefined,
        limit: 50,
      })
      .then((res) => {
        if (!res.success) {
          setError(res.error ?? "Impossible de charger les restaurants");
          return;
        }
        setRestaurants(res.data);
      })
      .finally(() => setLoading(false));
  }, [target?.countryCode, target?.cityName, target?.latitude, target?.longitude]);

  const openRestaurant = async (restaurantId: string) => {
    setError(null);
    const res = await marketplaceApi.getFoodRestaurant(restaurantId);
    if (!res.success) {
      setError(res.error ?? "Restaurant introuvable");
      return;
    }
    setSelectedRestaurant(res.data);
    setQuantities({});
    setSelectedModifiers({});
    setDeliveryQuote(null);
    setCreatedOrder(null);
  };

  const quoteDelivery = async () => {
    if (!selectedRestaurant || !target?.latitude || !target?.longitude) {
      setError("Choisissez une zone cible avec des coordonnées suggérées pour calculer la livraison.");
      return;
    }
    const res = await marketplaceApi.quoteFoodDelivery({
      restaurant_id: selectedRestaurant.id,
      delivery_latitude: target.latitude,
      delivery_longitude: target.longitude,
    });
    if (!res.success) {
      setError(res.error ?? "Impossible de calculer la livraison");
      return;
    }
    setDeliveryQuote(res.data);
  };

  const createOrder = async () => {
    if (!selectedRestaurant || !target) {
      setError("Choisissez un restaurant et une zone cible.");
      return;
    }
    const items = selectedItems.map(([menuItemId, quantity]) => ({
      menu_item_id: menuItemId,
      quantity,
      modifier_option_ids: selectedModifiers[menuItemId] ?? [],
    }));
    if (!items.length) {
      setError("Ajoutez au moins un article à la commande.");
      return;
    }
    const res = await marketplaceApi.createFoodOrder({
      restaurant_id: selectedRestaurant.id,
      items,
      delivery_address: target.address || `${target.cityName}, ${target.countryCode}`,
      delivery_latitude: target.latitude ?? null,
      delivery_longitude: target.longitude ?? null,
      ordered_for_other: target.mode === "remote",
      beneficiary_name: target.mode === "remote" ? "Bénéficiaire" : null,
      beneficiary_phone: null,
    });
    if (!res.success) {
      setError(res.error ?? "Impossible de créer la commande");
      return;
    }
    setCreatedOrder(res.data);
    await loadOrders();
  };

  const fundOrder = async () => {
    if (!createdOrder) return;
    const res = await marketplaceApi.fundFoodOrder(createdOrder.id);
    if (!res.success) {
      setError(res.error ?? "Impossible de financer la commande");
      return;
    }
    setCreatedOrder(res.data);
    await loadOrders();
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">Commander à manger</h2>
        <p className="text-sm text-gray-500 mt-1">
          Localement ou à distance, choisissez une zone cible puis commandez auprès des restaurants proches.
        </p>
      </div>

      <TargetLocationPicker
        storageKey="zaska-food-target"
        defaultCountryCode={profile?.country_code}
        onChange={setTarget}
      />

      {error && <div className="rounded-xl bg-red-50 border border-red-100 text-red-700 px-4 py-3 text-sm">{error}</div>}

      <div className="grid gap-6 lg:grid-cols-[1.1fr,1.4fr]">
        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold text-gray-900">Restaurants proches</h3>
            {loading && <span className="text-xs text-gray-400">Chargement...</span>}
          </div>
          <div className="space-y-3">
            {restaurants.map((restaurant) => (
              <button
                key={restaurant.id}
                type="button"
                className={`w-full rounded-2xl border p-4 text-left transition-shadow hover:shadow-sm ${selectedRestaurant?.id === restaurant.id ? "border-black bg-gray-50" : "border-gray-200 bg-white"}`}
                onClick={() => void openRestaurant(restaurant.id)}
              >
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <h4 className="font-semibold text-gray-900">{restaurant.publicName}</h4>
                    <p className="text-sm text-gray-500 mt-1">{restaurant.description || restaurant.address || restaurant.cityName}</p>
                    <p className="text-xs text-gray-400 mt-2">
                      {[restaurant.cityName, restaurant.countryCode].filter(Boolean).join(" · ")}
                    </p>
                  </div>
                  <div className="text-right">
                    {restaurant.distanceKm != null && (
                      <p className="text-xs font-medium text-gray-700">{restaurant.distanceKm.toFixed(1)} km</p>
                    )}
                    <p className={`mt-2 text-xs font-semibold ${restaurant.acceptingOrders ? "text-green-600" : "text-gray-400"}`}>
                      {restaurant.acceptingOrders ? "Prend des commandes" : "Indisponible"}
                    </p>
                  </div>
                </div>
              </button>
            ))}
            {!loading && restaurants.length === 0 && (
              <div className="rounded-2xl border border-dashed border-gray-300 bg-gray-50 p-6 text-sm text-gray-500">
                Aucun restaurant visible dans cette zone pour le moment.
              </div>
            )}
          </div>
        </section>

        <section className="space-y-4">
          {!selectedRestaurant ? (
            <div className="rounded-2xl border border-dashed border-gray-300 bg-gray-50 p-8 text-sm text-gray-500">
              Sélectionnez un restaurant pour voir son menu et préparer une commande.
            </div>
          ) : (
            <>
              <div className="rounded-2xl border border-gray-200 bg-white p-5">
                <h3 className="text-xl font-semibold text-gray-900">{selectedRestaurant.publicName}</h3>
                <p className="text-sm text-gray-500 mt-1">{selectedRestaurant.description || selectedRestaurant.address}</p>
                <div className="mt-3 flex flex-wrap gap-2 text-xs text-gray-500">
                  <span className="rounded-full bg-gray-100 px-3 py-1">{selectedRestaurant.cityName}</span>
                  <span className="rounded-full bg-gray-100 px-3 py-1">{selectedRestaurant.currency}</span>
                  <span className="rounded-full bg-gray-100 px-3 py-1">
                    {selectedRestaurant.isTemporarilyClosed ? "Temporairement fermé" : "Ouvert"}
                  </span>
                </div>
              </div>

              <div className="rounded-2xl border border-gray-200 bg-white p-5 space-y-4">
                <div className="flex items-center justify-between">
                  <h4 className="text-lg font-semibold text-gray-900">Menu</h4>
                  <button type="button" onClick={() => void quoteDelivery()} className="rounded-xl border border-gray-200 px-3 py-2 text-sm hover:bg-gray-50">
                    Calculer la livraison
                  </button>
                </div>

                <div className="space-y-3">
                  {selectedRestaurant.menuItems.map((item) => (
                    <div key={item.id} className="rounded-2xl border border-gray-100 bg-gray-50 p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <h5 className="font-medium text-gray-900">{item.name}</h5>
                          <p className="text-sm text-gray-500 mt-1">{item.description}</p>
                          <p className="text-sm font-semibold text-gray-900 mt-2">{formatMoney(item.price, item.currency)}</p>
                        </div>
                        <input
                          type="number"
                          min={0}
                          max={20}
                          value={quantities[item.id] ?? 0}
                          onChange={(e) => setQuantities((prev) => ({ ...prev, [item.id]: Number(e.target.value) }))}
                          className="w-20 rounded-xl border border-gray-200 px-3 py-2 text-sm"
                        />
                      </div>
                      {(selectedRestaurant.modifiersByItem[item.id] ?? []).length > 0 && (
                        <div className="mt-3 space-y-2">
                          {selectedRestaurant.modifiersByItem[item.id].map((group) => (
                            <div key={group.id}>
                              <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">{group.name}</p>
                              <div className="mt-1 flex flex-wrap gap-2">
                                {group.options.map((option) => {
                                  const active = (selectedModifiers[item.id] ?? []).includes(option.id);
                                  return (
                                    <button
                                      key={option.id}
                                      type="button"
                                      onClick={() =>
                                        setSelectedModifiers((prev) => {
                                          const current = prev[item.id] ?? [];
                                          const next = current.includes(option.id)
                                            ? current.filter((entry) => entry !== option.id)
                                            : [...current, option.id];
                                          return { ...prev, [item.id]: next };
                                        })}
                                      className={`rounded-full border px-3 py-1 text-xs ${active ? "border-black bg-black text-white" : "border-gray-200 bg-white text-gray-700"}`}
                                    >
                                      {option.name} (+{formatMoney(option.priceDelta, option.currency)})
                                    </button>
                                  );
                                })}
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>

                {deliveryQuote && (
                  <div className="rounded-xl bg-emerald-50 border border-emerald-100 p-4 text-sm text-emerald-800">
                    <p className="font-semibold">Devis livraison prêt</p>
                    <pre className="mt-2 text-xs whitespace-pre-wrap">{JSON.stringify(deliveryQuote, null, 2)}</pre>
                  </div>
                )}

                <div className="flex flex-wrap gap-3">
                  <button type="button" onClick={() => void createOrder()} className="rounded-xl bg-black px-4 py-2 text-sm font-medium text-white">
                    Créer la commande
                  </button>
                  {createdOrder && createdOrder.paymentStatus !== "FUNDED" && (
                    <button type="button" onClick={() => void fundOrder()} className="rounded-xl border border-gray-200 px-4 py-2 text-sm font-medium hover:bg-gray-50">
                      Financer la commande
                    </button>
                  )}
                </div>

                {createdOrder && (
                  <div className="rounded-xl bg-blue-50 border border-blue-100 p-4 text-sm text-blue-900">
                    <p className="font-semibold">Commande créée</p>
                    <p className="mt-1">Statut : {createdOrder.status} · Paiement : {createdOrder.paymentStatus}</p>
                    <p className="mt-1">Total : {formatMoney(createdOrder.totalAmount, createdOrder.currency)}</p>
                  </div>
                )}
              </div>
            </>
          )}
        </section>
      </div>

      <section className="rounded-2xl border border-gray-200 bg-white p-5">
        <h3 className="text-lg font-semibold text-gray-900">Mes commandes nourriture</h3>
        <div className="mt-4 space-y-3">
          {myOrders.map((order) => (
            <div key={order.id} className="rounded-xl border border-gray-100 p-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="font-medium text-gray-900">Commande #{order.id.slice(0, 8)}</p>
                  <p className="text-sm text-gray-500 mt-1">{order.deliveryAddress}</p>
                </div>
                <div className="text-right">
                  <p className="text-sm font-semibold text-gray-900">{formatMoney(order.totalAmount, order.currency)}</p>
                  <p className="text-xs text-gray-500 mt-1">{order.status} · {order.paymentStatus}</p>
                </div>
              </div>
            </div>
          ))}
          {myOrders.length === 0 && <p className="text-sm text-gray-500">Aucune commande nourriture pour le moment.</p>}
        </div>
      </section>
    </div>
  );
}
