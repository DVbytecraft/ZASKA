import { useEffect, useMemo, useState } from "react";
import { TargetLocationPicker } from "../components/TargetLocationPicker";
import { marketplaceApi, type MerchantSummary, type ShopCatalog, type ShopItem, type ShopOrderResponse, type TargetLocationValue } from "../services/marketplaceApi";
import { useAuthStore } from "../store";

function formatMoney(value: string | number | undefined, currency?: string) {
  if (value == null) return "—";
  const amount = typeof value === "number" ? value : Number(value);
  return `${currency ?? ""} ${Number.isFinite(amount) ? amount.toLocaleString("fr-FR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : value}`;
}

export function ShopPage() {
  const profile = useAuthStore((s) => s.profile);
  const [target, setTarget] = useState<TargetLocationValue | null>(null);
  const [merchants, setMerchants] = useState<MerchantSummary[]>([]);
  const [selectedMerchant, setSelectedMerchant] = useState<MerchantSummary | null>(null);
  const [catalogs, setCatalogs] = useState<ShopCatalog[]>([]);
  const [items, setItems] = useState<ShopItem[]>([]);
  const [cart, setCart] = useState<Record<string, number>>({});
  const [quote, setQuote] = useState<Record<string, unknown> | null>(null);
  const [createdOrder, setCreatedOrder] = useState<ShopOrderResponse | null>(null);
  const [myOrders, setMyOrders] = useState<ShopOrderResponse[]>([]);
  const [error, setError] = useState<string | null>(null);

  const selectedLines = useMemo(() => Object.entries(cart).filter(([, qty]) => qty > 0), [cart]);

  const loadOrders = async () => {
    const res = await marketplaceApi.listMyShopOrders();
    if (res.success) setMyOrders(res.data);
  };

  useEffect(() => {
    void loadOrders();
  }, []);

  useEffect(() => {
    if (!target?.countryCode || !target.cityName) return;
    void marketplaceApi
      .listShopMerchants({
        country_code: target.countryCode,
        city_name: target.cityName,
        reference_latitude: target.latitude ?? undefined,
        reference_longitude: target.longitude ?? undefined,
        active_only: true,
        limit: 50,
      })
      .then((res) => {
        if (res.success) setMerchants(res.data);
      });
  }, [target?.countryCode, target?.cityName, target?.latitude, target?.longitude]);

  const openMerchant = async (merchant: MerchantSummary) => {
    setSelectedMerchant(merchant);
    setError(null);
    setCart({});
    setQuote(null);
    setCreatedOrder(null);
    const [catalogRes, itemsRes] = await Promise.all([
      marketplaceApi.listShopCatalogs(merchant.id),
      marketplaceApi.listShopItems({ merchant_id: merchant.id, active_only: true }),
    ]);
    if (catalogRes.success) setCatalogs(catalogRes.data);
    if (itemsRes.success) setItems(itemsRes.data);
  };

  const quoteDelivery = async () => {
    if (!selectedMerchant || !target?.latitude || !target?.longitude) {
      setError("Choisissez une cible avec suggestion d’adresse pour calculer la livraison.");
      return;
    }
    const res = await marketplaceApi.quoteShopDelivery({
      merchant_id: selectedMerchant.id,
      delivery_latitude: target.latitude,
      delivery_longitude: target.longitude,
    });
    if (!res.success) {
      setError(res.error ?? "Impossible de calculer la livraison");
      return;
    }
    setQuote(res.data);
  };

  const createOrder = async () => {
    if (!selectedMerchant || !target) {
      setError("Choisissez un marchand et une zone cible.");
      return;
    }
    const lines = selectedLines.map(([catalogItemId, quantity]) => ({ catalog_item_id: catalogItemId, quantity }));
    if (!lines.length) {
      setError("Ajoutez au moins un article.");
      return;
    }
    const res = await marketplaceApi.createShopOrder({
      merchant_id: selectedMerchant.id,
      items: lines,
      ordered_for_other: target.mode === "remote",
      beneficiary_name: target.mode === "remote" ? "Bénéficiaire" : null,
      beneficiary_phone: null,
      delivery_address: target.address || `${target.cityName}, ${target.countryCode}`,
      delivery_latitude: target.latitude ?? null,
      delivery_longitude: target.longitude ?? null,
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
    const res = await marketplaceApi.fundShopOrder(createdOrder.id);
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
        <h2 className="text-2xl font-bold text-gray-900">Acheter des articles</h2>
        <p className="text-sm text-gray-500 mt-1">
          Explorez les marchands de la zone ciblée et achetez localement ou pour quelqu’un d’autre.
        </p>
      </div>

      <TargetLocationPicker storageKey="zaska-shop-target" defaultCountryCode={profile?.country_code} onChange={setTarget} />

      {error && <div className="rounded-xl bg-red-50 border border-red-100 text-red-700 px-4 py-3 text-sm">{error}</div>}

      <div className="grid gap-6 lg:grid-cols-[1.05fr,1.45fr]">
        <section className="space-y-3">
          <h3 className="text-lg font-semibold text-gray-900">Marchands proches</h3>
          <div className="space-y-3">
            {merchants.map((merchant) => (
              <button
                key={merchant.id}
                type="button"
                onClick={() => void openMerchant(merchant)}
                className={`w-full rounded-2xl border p-4 text-left transition-shadow hover:shadow-sm ${selectedMerchant?.id === merchant.id ? "border-black bg-gray-50" : "border-gray-200 bg-white"}`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h4 className="font-semibold text-gray-900">{merchant.publicName}</h4>
                    <p className="text-sm text-gray-500 mt-1">{merchant.description || merchant.address || merchant.cityName}</p>
                  </div>
                  {merchant.distanceKm != null && <span className="text-xs font-medium text-gray-700">{merchant.distanceKm.toFixed(1)} km</span>}
                </div>
              </button>
            ))}
            {merchants.length === 0 && (
              <div className="rounded-2xl border border-dashed border-gray-300 bg-gray-50 p-6 text-sm text-gray-500">
                Aucun marchand visible pour cette zone.
              </div>
            )}
          </div>
        </section>

        <section className="space-y-4">
          {!selectedMerchant ? (
            <div className="rounded-2xl border border-dashed border-gray-300 bg-gray-50 p-8 text-sm text-gray-500">
              Sélectionnez un marchand pour voir son catalogue et commander.
            </div>
          ) : (
            <>
              <div className="rounded-2xl border border-gray-200 bg-white p-5">
                <h3 className="text-xl font-semibold text-gray-900">{selectedMerchant.publicName}</h3>
                <p className="text-sm text-gray-500 mt-1">{selectedMerchant.description || selectedMerchant.address}</p>
                <div className="mt-3 flex flex-wrap gap-2 text-xs text-gray-500">
                  <span className="rounded-full bg-gray-100 px-3 py-1">{selectedMerchant.cityName}</span>
                  <span className="rounded-full bg-gray-100 px-3 py-1">{selectedMerchant.currency}</span>
                </div>
              </div>

              <div className="rounded-2xl border border-gray-200 bg-white p-5 space-y-4">
                <div className="flex items-center justify-between">
                  <h4 className="text-lg font-semibold text-gray-900">Catalogue</h4>
                  <button type="button" onClick={() => void quoteDelivery()} className="rounded-xl border border-gray-200 px-3 py-2 text-sm hover:bg-gray-50">
                    Calculer la livraison
                  </button>
                </div>

                {catalogs.length > 0 && (
                  <div className="flex flex-wrap gap-2 text-xs text-gray-500">
                    {catalogs.map((catalog) => (
                      <span key={catalog.id} className="rounded-full bg-gray-100 px-3 py-1">{catalog.name}</span>
                    ))}
                  </div>
                )}

                <div className="space-y-3">
                  {items.map((item) => (
                    <div key={item.id} className="rounded-2xl border border-gray-100 bg-gray-50 p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <h5 className="font-medium text-gray-900">{item.name}</h5>
                          <p className="text-sm text-gray-500 mt-1">{item.description}</p>
                          <p className="text-sm font-semibold text-gray-900 mt-2">{formatMoney(item.unitPrice, item.currency)}</p>
                        </div>
                        <input
                          type="number"
                          min={0}
                          max={20}
                          value={cart[item.id] ?? 0}
                          onChange={(e) => setCart((prev) => ({ ...prev, [item.id]: Number(e.target.value) }))}
                          className="w-20 rounded-xl border border-gray-200 px-3 py-2 text-sm"
                        />
                      </div>
                    </div>
                  ))}
                </div>

                {quote && (
                  <div className="rounded-xl bg-emerald-50 border border-emerald-100 p-4 text-sm text-emerald-800">
                    <p className="font-semibold">Devis livraison prêt</p>
                    <pre className="mt-2 text-xs whitespace-pre-wrap">{JSON.stringify(quote, null, 2)}</pre>
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
        <h3 className="text-lg font-semibold text-gray-900">Mes commandes articles</h3>
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
          {myOrders.length === 0 && <p className="text-sm text-gray-500">Aucune commande article pour le moment.</p>}
        </div>
      </section>
    </div>
  );
}
