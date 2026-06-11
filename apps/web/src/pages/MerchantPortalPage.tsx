import { useEffect, useState } from "react";
import { marketplaceApi, type ShopOrderResponse } from "../services/marketplaceApi";

function formatMoney(value: string | number | undefined, currency?: string) {
  if (value == null) return "—";
  const amount = typeof value === "number" ? value : Number(value);
  return `${currency ?? ""} ${Number.isFinite(amount) ? amount.toLocaleString("fr-FR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : value}`;
}

export function MerchantPortalPage() {
  const [orders, setOrders] = useState<ShopOrderResponse[]>([]);
  const [payouts, setPayouts] = useState<Record<string, unknown>[]>([]);
  const [dashboard, setDashboard] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    const [dashboardRes, ordersRes, payoutsRes] = await Promise.all([
      marketplaceApi.getMerchantDashboard(),
      marketplaceApi.listMerchantOrders(),
      marketplaceApi.listMerchantPayouts(),
    ]);
    if (dashboardRes.success) setDashboard(dashboardRes.data);
    if (ordersRes.success) setOrders(ordersRes.data);
    if (payoutsRes.success) setPayouts(payoutsRes.data);
  };

  useEffect(() => {
    void load();
  }, []);

  const changeStatus = async (orderId: string, status: string) => {
    const res = await marketplaceApi.updateMerchantOrderStatus(orderId, status);
    if (!res.success) {
      setError(res.error ?? "Impossible de mettre à jour la commande");
      return;
    }
    await load();
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">Espace marchand</h2>
        <p className="text-sm text-gray-500 mt-1">Suivez vos commandes, votre fulfilment et vos paiements marchand.</p>
      </div>

      {error && <div className="rounded-xl bg-red-50 border border-red-100 text-red-700 px-4 py-3 text-sm">{error}</div>}

      <section className="rounded-2xl border border-gray-200 bg-white p-5">
        <h3 className="text-lg font-semibold text-gray-900">Dashboard marchand</h3>
        <pre className="mt-4 rounded-xl bg-gray-50 p-4 text-xs text-gray-700 overflow-auto">
          {JSON.stringify(dashboard, null, 2)}
        </pre>
      </section>

      <section className="rounded-2xl border border-gray-200 bg-white p-5">
        <h3 className="text-lg font-semibold text-gray-900">Commandes marchand</h3>
        <div className="mt-4 space-y-3">
          {orders.map((order) => (
            <div key={order.id} className="rounded-xl border border-gray-100 p-4 space-y-3">
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
              <div className="flex flex-wrap gap-2">
                {[
                  ["confirmed", "Confirmer"],
                  ["preparing", "Préparer"],
                  ["ready", "Prête à livrer"],
                  ["cancelled", "Annuler"],
                ].map(([value, label]) => (
                  <button
                    key={value}
                    type="button"
                    onClick={() => void changeStatus(order.id, value)}
                    className="rounded-full border border-gray-200 px-3 py-1 text-xs hover:bg-gray-50"
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>
          ))}
          {orders.length === 0 && <p className="text-sm text-gray-500">Aucune commande marchand pour le moment.</p>}
        </div>
      </section>

      <section className="rounded-2xl border border-gray-200 bg-white p-5">
        <h3 className="text-lg font-semibold text-gray-900">Payouts marchand</h3>
        <pre className="mt-4 rounded-xl bg-gray-50 p-4 text-xs text-gray-700 overflow-auto">
          {JSON.stringify(payouts, null, 2)}
        </pre>
      </section>
    </div>
  );
}
