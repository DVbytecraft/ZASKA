import { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api";

interface Balance {
  currency: string;
  balance: string;
}

interface Tx {
  id: string;
  type: string;
  amount: string;
  status: string;
  reference: string;
  provider: string;
  created_at: string;
}

interface DepositResult {
  mode: string;
  checkout_url?: string;
  tx_id?: string;
  amount: string;
  currency: string;
  status?: string;
}

const CURRENCIES = ["USD", "XOF"];

function StatusBanner({ type, msg, onClose }: { type: "success" | "cancel" | "error"; msg: string; onClose: () => void }) {
  const colors =
    type === "success"
      ? "bg-green-50 border-green-200 text-green-800"
      : type === "cancel"
      ? "bg-amber-50 border-amber-200 text-amber-800"
      : "bg-red-50 border-red-200 text-red-800";

  return (
    <div className={`border rounded-xl px-4 py-3 flex items-start justify-between gap-3 ${colors}`}>
      <div className="flex items-start gap-2">
        <span className="text-lg select-none">
          {type === "success" ? "✓" : type === "cancel" ? "✗" : "!"}
        </span>
        <p className="text-sm font-medium">{msg}</p>
      </div>
      <button onClick={onClose} className="text-current opacity-50 hover:opacity-100 font-bold text-lg leading-none">
        ×
      </button>
    </div>
  );
}

export function WalletPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  const [activeCurrency, setActiveCurrency] = useState("USD");
  const [balances, setBalances] = useState<Record<string, string>>({});
  const [txs, setTxs] = useState<Tx[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [banner, setBanner] = useState<{ type: "success" | "cancel" | "error"; msg: string } | null>(null);

  // Deposit form state
  const [depositAmount, setDepositAmount] = useState("");
  const [depositCurrency, setDepositCurrency] = useState("USD");
  const [depositing, setDepositing] = useState(false);

  const successRefetchDone = useRef(false);

  // ── Load all balances and transactions ──────────────────────────────────
  async function loadBalances() {
    const results = await Promise.all(CURRENCIES.map((c) => api.getWalletBalance(c)));
    const bMap: Record<string, string> = {};
    results.forEach((r, i) => {
      if (r.success) bMap[CURRENCIES[i]] = r.data.balance;
    });
    setBalances(bMap);
  }

  async function loadTxs(currency: string) {
    const res = await api.getWalletTransactions(currency);
    if (!res.success) {
      setError(res.error ?? "Impossible de charger les transactions");
      setTxs([]);
    } else {
      setTxs(res.data);
      setError(null);
    }
  }

  async function loadAll(currency?: string) {
    setLoading(true);
    await Promise.all([loadBalances(), loadTxs(currency ?? activeCurrency)]);
    setLoading(false);
  }

  // ── Initial load ─────────────────────────────────────────────────────────
  useEffect(() => {
    void loadAll();
  }, []);

  // ── Stripe return detection ───────────────────────────────────────────────
  useEffect(() => {
    const status = searchParams.get("status");
    if (!status) return;

    // Clean URL immediately — avoid duplicate handling on refresh
    navigate("/wallet", { replace: true });

    if (status === "success") {
      setBanner({ type: "success", msg: "Paiement confirmé — votre portefeuille va être crédité." });
      // Re-fetch after 2 s to give the webhook time to process
      if (!successRefetchDone.current) {
        successRefetchDone.current = true;
        setTimeout(() => void loadAll(), 2000);
      }
    } else if (status === "cancel") {
      setBanner({ type: "cancel", msg: "Paiement annulé. Aucun débit n'a été effectué." });
    }
  }, [searchParams]);

  // ── Currency switch ──────────────────────────────────────────────────────
  async function switchCurrency(currency: string) {
    setActiveCurrency(currency);
    setLoading(true);
    await loadTxs(currency);
    setLoading(false);
  }

  // ── Deposit (Stripe Checkout) ────────────────────────────────────────────
  async function handleDeposit() {
    const amt = parseFloat(depositAmount);
    if (!depositAmount || isNaN(amt) || amt <= 0) {
      setBanner({ type: "error", msg: "Veuillez entrer un montant valide." });
      return;
    }
    setDepositing(true);
    try {
      const res = await api.deposit(depositAmount, depositCurrency);
      if (!res.success) {
        setBanner({ type: "error", msg: res.error ?? "Erreur lors de l'initiation du paiement." });
        return;
      }
      const data = res.data as DepositResult;
      if (data.mode === "stripe_checkout" && data.checkout_url) {
        // Redirect to Stripe Checkout hosted page
        window.location.href = data.checkout_url;
      } else if (data.mode === "mock") {
        // Development direct credit
        setBanner({ type: "success", msg: `${data.amount} ${data.currency} ajouté (mode dev).` });
        setDepositAmount("");
        await loadAll();
      }
    } catch (err) {
      setBanner({ type: "error", msg: err instanceof Error ? err.message : "Erreur réseau." });
    } finally {
      setDepositing(false);
    }
  }

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold">Portefeuilles</h2>

      {banner && (
        <StatusBanner type={banner.type} msg={banner.msg} onClose={() => setBanner(null)} />
      )}

      {/* Balances */}
      <div className="grid grid-cols-2 gap-4">
        {CURRENCIES.map((c) => (
          <button
            key={c}
            onClick={() => void switchCurrency(c)}
            className={`rounded-xl p-4 text-left transition-colors border-2 ${
              activeCurrency === c
                ? "border-gray-900 bg-gray-900 text-white"
                : "border-gray-200 bg-white text-gray-900"
            }`}
          >
            <p className="text-xs font-medium opacity-70 mb-1">{c}</p>
            <p className="text-2xl font-bold">
              {balances[c] !== undefined ? parseFloat(balances[c]).toFixed(2) : loading ? "…" : "—"}
            </p>
          </button>
        ))}
      </div>

      {/* Deposit form */}
      <div className="bg-white border rounded-xl p-4 space-y-3">
        <h3 className="text-sm font-semibold">Recharger le portefeuille</h3>
        <div className="flex gap-2">
          <input
            type="number"
            min="1"
            step="1"
            className="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gray-900"
            placeholder="Montant"
            value={depositAmount}
            onChange={(e) => setDepositAmount(e.target.value)}
          />
          <select
            className="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gray-900"
            value={depositCurrency}
            onChange={(e) => setDepositCurrency(e.target.value)}
          >
            {CURRENCIES.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
          <button
            onClick={() => void handleDeposit()}
            disabled={depositing || !depositAmount}
            className="bg-gray-900 text-white rounded-lg px-4 py-2 text-sm font-medium disabled:opacity-40"
          >
            {depositing ? "…" : "Payer par carte"}
          </button>
        </div>
        <p className="text-xs text-gray-400">Paiement sécurisé via Stripe. Carte test : 4242 4242 4242 4242</p>
      </div>

      {/* Transactions */}
      <div>
        <h3 className="text-sm font-semibold mb-3">Transactions — {activeCurrency}</h3>

        {loading ? (
          <div className="space-y-2">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-14 bg-gray-100 rounded-xl animate-pulse" />
            ))}
          </div>
        ) : error ? (
          <p className="text-sm text-red-600">{error}</p>
        ) : txs.length === 0 ? (
          <div className="border rounded-xl p-6 text-center text-sm text-gray-400">
            Aucune transaction pour l'instant.
          </div>
        ) : (
          <div className="space-y-2">
            {txs.map((tx) => (
              <div key={tx.id} className="flex items-center justify-between border rounded-xl p-3 bg-white">
                <div className="min-w-0">
                  <p className="text-sm font-medium capitalize">
                    {tx.type === "credit" ? "Crédit" : "Débit"} · {tx.provider}
                  </p>
                  <p className="text-xs text-gray-500 truncate max-w-[200px]">{tx.reference}</p>
                  <p className="text-xs text-gray-400">
                    {new Date(tx.created_at).toLocaleDateString("fr-FR", {
                      day: "2-digit",
                      month: "short",
                      year: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </p>
                </div>
                <div className="text-right flex-shrink-0 ml-3">
                  <p className={`text-base font-bold ${tx.type === "credit" ? "text-green-600" : "text-red-500"}`}>
                    {tx.type === "credit" ? "+" : "-"}
                    {parseFloat(tx.amount).toFixed(2)} {activeCurrency}
                  </p>
                  <span
                    className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                      tx.status === "completed"
                        ? "bg-green-100 text-green-700"
                        : tx.status === "pending"
                        ? "bg-amber-100 text-amber-700"
                        : "bg-red-100 text-red-600"
                    }`}
                  >
                    {tx.status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
