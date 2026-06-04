import { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api, type PaymentMethod, type VirtualCard } from "../api";

interface Balance { currency: string; balance: string; }
interface Tx { id: string; type: string; amount: string; status: string; reference: string; provider: string; created_at: string; }
interface DepositResult { mode: string; checkout_url?: string; tx_id?: string; amount: string; currency: string; status?: string; }

const CURRENCIES = ["USD", "XOF"];
type WalletTab = "balances" | "transfer" | "withdraw" | "methods" | "cards";

function StatusBanner({ type, msg, onClose }: { type: "success" | "cancel" | "error"; msg: string; onClose: () => void }) {
  const colors = type === "success" ? "bg-green-50 border-green-200 text-green-800"
    : type === "cancel" ? "bg-amber-50 border-amber-200 text-amber-800"
    : "bg-red-50 border-red-200 text-red-800";
  return (
    <div className={`border rounded-xl px-4 py-3 flex items-start justify-between gap-3 ${colors}`}>
      <div className="flex items-start gap-2">
        <span className="text-lg select-none">{type === "success" ? "✓" : type === "cancel" ? "✗" : "!"}</span>
        <p className="text-sm font-medium">{msg}</p>
      </div>
      <button onClick={onClose} className="text-current opacity-50 hover:opacity-100 font-bold text-lg leading-none">×</button>
    </div>
  );
}

export function WalletPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<WalletTab>("balances");

  // Balance/tx state
  const [activeCurrency, setActiveCurrency] = useState("USD");
  const [balances, setBalances] = useState<Record<string, string>>({});
  const [txs, setTxs] = useState<Tx[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [banner, setBanner] = useState<{ type: "success" | "cancel" | "error"; msg: string } | null>(null);

  // Deposit
  const [depositAmount, setDepositAmount] = useState("");
  const [depositCurrency, setDepositCurrency] = useState("USD");
  const [depositing, setDepositing] = useState(false);
  const successRefetchDone = useRef(false);

  // Transfer
  const [toUserId, setToUserId] = useState("");
  const [transferAmount, setTransferAmount] = useState("");
  const [transferCurrency, setTransferCurrency] = useState("USD");
  const [transferNote, setTransferNote] = useState("");
  const [transferring, setTransferring] = useState(false);

  // Withdraw
  const [withdrawAmount, setWithdrawAmount] = useState("");
  const [withdrawCurrency, setWithdrawCurrency] = useState("XOF");
  const [withdrawPhone, setWithdrawPhone] = useState("");
  const [withdrawCountry, setWithdrawCountry] = useState("");
  const [withdrawName, setWithdrawName] = useState("");
  const [withdrawing, setWithdrawing] = useState(false);

  // Payment methods
  const [methods, setMethods] = useState<PaymentMethod[]>([]);
  const [loadingMethods, setLoadingMethods] = useState(false);
  const [deletingMethod, setDeletingMethod] = useState<string | null>(null);

  // Cards
  const [cards, setCards] = useState<VirtualCard[]>([]);
  const [loadingCards, setLoadingCards] = useState(false);
  const [cardType, setCardType] = useState<"visa" | "mastercard">("visa");
  const [cardCurrency, setCardCurrency] = useState("USD");
  const [creatingCard, setCreatingCard] = useState(false);

  async function loadBalances() {
    const results = await Promise.all(CURRENCIES.map((c) => api.getWalletBalance(c)));
    const bMap: Record<string, string> = {};
    results.forEach((r, i) => { if (r.success) bMap[CURRENCIES[i]] = r.data.balance; });
    setBalances(bMap);
  }

  async function loadTxs(currency: string) {
    const res = await api.getWalletTransactions(currency);
    if (res.success) { setTxs(res.data); setError(null); }
    else { setError(res.error ?? "Erreur transactions"); setTxs([]); }
  }

  async function loadAll(currency?: string) {
    setLoading(true);
    await Promise.all([loadBalances(), loadTxs(currency ?? activeCurrency)]);
    setLoading(false);
  }

  useEffect(() => { void loadAll(); }, []);

  useEffect(() => {
    const status = searchParams.get("status");
    if (!status) return;
    navigate("/wallet", { replace: true });
    if (status === "success") {
      setBanner({ type: "success", msg: "Paiement confirmé — votre portefeuille va être crédité." });
      if (!successRefetchDone.current) { successRefetchDone.current = true; setTimeout(() => void loadAll(), 2000); }
    } else if (status === "cancel") {
      setBanner({ type: "cancel", msg: "Paiement annulé. Aucun débit n'a été effectué." });
    }
  }, [searchParams]);

  useEffect(() => {
    if (activeTab === "methods" && methods.length === 0) {
      setLoadingMethods(true);
      api.listPaymentMethods().then((r) => { if (r.success) setMethods(r.data); setLoadingMethods(false); });
    }
    if (activeTab === "cards" && cards.length === 0) {
      setLoadingCards(true);
      api.listCards().then((r) => { if (r.success) setCards(r.data); setLoadingCards(false); });
    }
  }, [activeTab]);

  async function switchCurrency(currency: string) {
    setActiveCurrency(currency);
    setLoading(true);
    await loadTxs(currency);
    setLoading(false);
  }

  async function handleDeposit() {
    const amt = parseFloat(depositAmount);
    if (!depositAmount || isNaN(amt) || amt <= 0) { setBanner({ type: "error", msg: "Veuillez entrer un montant valide." }); return; }
    setDepositing(true);
    try {
      const res = await api.deposit(depositAmount, depositCurrency);
      if (!res.success) { setBanner({ type: "error", msg: res.error ?? "Erreur." }); return; }
      const data = res.data as DepositResult;
      if (data.mode === "stripe_checkout" && data.checkout_url) {
        window.location.href = data.checkout_url;
      } else if (data.mode === "mock") {
        setBanner({ type: "success", msg: `${data.amount} ${data.currency} ajouté (mode dev).` });
        setDepositAmount("");
        await loadAll();
      }
    } catch (err) {
      setBanner({ type: "error", msg: err instanceof Error ? err.message : "Erreur réseau." });
    } finally { setDepositing(false); }
  }

  async function handleTransfer() {
    if (!toUserId.trim() || !transferAmount) { setBanner({ type: "error", msg: "ID destinataire et montant requis." }); return; }
    const amt = parseFloat(transferAmount);
    if (isNaN(amt) || amt <= 0) { setBanner({ type: "error", msg: "Montant invalide." }); return; }
    setTransferring(true);
    const res = await api.transfer(toUserId.trim(), transferAmount, transferCurrency, transferNote || undefined);
    setTransferring(false);
    if (res.success) {
      setBanner({ type: "success", msg: `${transferAmount} ${transferCurrency} transféré avec succès.` });
      setToUserId(""); setTransferAmount(""); setTransferNote("");
      void loadAll();
    } else setBanner({ type: "error", msg: res.error ?? "Erreur lors du transfert." });
  }

  async function handleWithdraw() {
    if (!withdrawAmount || !withdrawPhone || !withdrawCountry) { setBanner({ type: "error", msg: "Montant, téléphone et pays requis." }); return; }
    const amt = parseFloat(withdrawAmount);
    if (isNaN(amt) || amt <= 0) { setBanner({ type: "error", msg: "Montant invalide." }); return; }
    setWithdrawing(true);
    const res = await api.withdraw(withdrawAmount, withdrawCurrency, withdrawPhone, withdrawCountry, withdrawName || undefined);
    setWithdrawing(false);
    if (res.success) {
      setBanner({ type: "success", msg: `Retrait initié. Référence : ${res.data.reference}` });
      setWithdrawAmount(""); setWithdrawPhone(""); setWithdrawCountry(""); setWithdrawName("");
      void loadAll();
    } else setBanner({ type: "error", msg: res.error ?? "Erreur lors du retrait." });
  }

  async function handleDeleteMethod(id: string) {
    if (!confirm("Supprimer ce moyen de paiement ?")) return;
    setDeletingMethod(id);
    const res = await api.deletePaymentMethod(id);
    setDeletingMethod(null);
    if (res.success) setMethods((prev) => prev.filter((m) => m.id !== id));
    else setBanner({ type: "error", msg: res.error ?? "Erreur." });
  }

  async function handleCreateCard() {
    setCreatingCard(true);
    const res = await api.createCard(cardType, cardCurrency);
    setCreatingCard(false);
    if (res.success) { setCards((prev) => [res.data, ...prev]); setBanner({ type: "success", msg: "Carte virtuelle créée !" }); }
    else setBanner({ type: "error", msg: res.error ?? "Erreur." });
  }

  const tabs: { key: WalletTab; label: string }[] = [
    { key: "balances", label: "Soldes" },
    { key: "transfer", label: "Transfert" },
    { key: "withdraw", label: "Retrait" },
    { key: "methods", label: "Méthodes" },
    { key: "cards", label: "Cartes" },
  ];

  return (
    <div className="space-y-5">
      <h2 className="text-xl font-semibold">Portefeuille</h2>

      {banner && <StatusBanner type={banner.type} msg={banner.msg} onClose={() => setBanner(null)} />}

      {/* Tabs */}
      <div className="flex gap-1 bg-gray-100 rounded-lg p-1 overflow-x-auto">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setActiveTab(t.key)}
            className={`flex-shrink-0 text-xs font-medium py-1.5 px-3 rounded-md transition-colors ${activeTab === t.key ? "bg-white text-gray-900 shadow-sm" : "text-gray-500 hover:text-gray-700"}`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* ── Balances + Deposit + Transactions ──────────────────────────────── */}
      {activeTab === "balances" && (
        <>
          <div className="grid grid-cols-2 gap-4">
            {CURRENCIES.map((c) => (
              <button key={c} onClick={() => void switchCurrency(c)}
                className={`rounded-xl p-4 text-left transition-colors border-2 ${activeCurrency === c ? "border-gray-900 bg-gray-900 text-white" : "border-gray-200 bg-white text-gray-900"}`}>
                <p className="text-xs font-medium opacity-70 mb-1">{c}</p>
                <p className="text-2xl font-bold">{balances[c] !== undefined ? parseFloat(balances[c]).toFixed(2) : loading ? "…" : "—"}</p>
              </button>
            ))}
          </div>

          <div className="bg-white border rounded-xl p-4 space-y-3">
            <h3 className="text-sm font-semibold">Recharger le portefeuille</h3>
            <div className="flex gap-2">
              <input type="number" min="1" step="1" className="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gray-900" placeholder="Montant" value={depositAmount} onChange={(e) => setDepositAmount(e.target.value)} />
              <select className="border border-gray-200 rounded-lg px-3 py-2 text-sm" value={depositCurrency} onChange={(e) => setDepositCurrency(e.target.value)}>
                {CURRENCIES.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
              <button onClick={() => void handleDeposit()} disabled={depositing || !depositAmount} className="bg-gray-900 text-white rounded-lg px-4 py-2 text-sm font-medium disabled:opacity-40">
                {depositing ? "…" : "Payer"}
              </button>
            </div>
            <p className="text-xs text-gray-400">Paiement sécurisé via Stripe. Carte test : 4242 4242 4242 4242</p>
          </div>

          <div>
            <h3 className="text-sm font-semibold mb-3">Transactions — {activeCurrency}</h3>
            {loading ? (
              <div className="space-y-2">{[1, 2, 3].map((i) => <div key={i} className="h-14 bg-gray-100 rounded-xl animate-pulse" />)}</div>
            ) : error ? (
              <p className="text-sm text-red-600">{error}</p>
            ) : txs.length === 0 ? (
              <div className="border rounded-xl p-6 text-center text-sm text-gray-400">Aucune transaction.</div>
            ) : (
              <div className="space-y-2">
                {txs.map((tx) => (
                  <div key={tx.id} className="flex items-center justify-between border rounded-xl p-3 bg-white">
                    <div className="min-w-0">
                      <p className="text-sm font-medium capitalize">{tx.type === "credit" ? "Crédit" : "Débit"} · {tx.provider}</p>
                      <p className="text-xs text-gray-500 truncate max-w-[200px]">{tx.reference}</p>
                      <p className="text-xs text-gray-400">{new Date(tx.created_at).toLocaleDateString("fr-FR", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" })}</p>
                    </div>
                    <div className="text-right flex-shrink-0 ml-3">
                      <p className={`text-base font-bold ${tx.type === "credit" ? "text-green-600" : "text-red-500"}`}>
                        {tx.type === "credit" ? "+" : "-"}{parseFloat(tx.amount).toFixed(2)} {activeCurrency}
                      </p>
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${tx.status === "completed" ? "bg-green-100 text-green-700" : tx.status === "pending" ? "bg-amber-100 text-amber-700" : "bg-red-100 text-red-600"}`}>
                        {tx.status}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}

      {/* ── Transfer ─────────────────────────────────────────────────────── */}
      {activeTab === "transfer" && (
        <div className="bg-white border rounded-xl p-5 space-y-4">
          <h3 className="font-semibold">Transférer des fonds</h3>
          <div className="space-y-3">
            <div>
              <label className="text-xs font-medium text-gray-500 block mb-1">ID du destinataire</label>
              <input className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gray-900" placeholder="User ID du destinataire" value={toUserId} onChange={(e) => setToUserId(e.target.value)} />
            </div>
            <div className="flex gap-3">
              <div className="flex-1">
                <label className="text-xs font-medium text-gray-500 block mb-1">Montant</label>
                <input type="number" min="1" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gray-900" placeholder="0.00" value={transferAmount} onChange={(e) => setTransferAmount(e.target.value)} />
              </div>
              <div>
                <label className="text-xs font-medium text-gray-500 block mb-1">Devise</label>
                <select className="border border-gray-200 rounded-lg px-3 py-2 text-sm" value={transferCurrency} onChange={(e) => setTransferCurrency(e.target.value)}>
                  {CURRENCIES.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>
            </div>
            <div>
              <label className="text-xs font-medium text-gray-500 block mb-1">Note (optionnel)</label>
              <input className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gray-900" placeholder="Objet du transfert" value={transferNote} onChange={(e) => setTransferNote(e.target.value)} />
            </div>
            <button onClick={() => void handleTransfer()} disabled={transferring || !toUserId || !transferAmount} className="w-full bg-gray-900 text-white rounded-lg py-2.5 text-sm font-medium disabled:opacity-40">
              {transferring ? "Transfert en cours…" : "Transférer"}
            </button>
          </div>
          <p className="text-xs text-gray-400">Les transferts entre utilisateurs ZASKA sont instantanés.</p>
        </div>
      )}

      {/* ── Withdraw ─────────────────────────────────────────────────────── */}
      {activeTab === "withdraw" && (
        <div className="bg-white border rounded-xl p-5 space-y-4">
          <h3 className="font-semibold">Retrait Mobile Money</h3>
          <div className="space-y-3">
            <div className="flex gap-3">
              <div className="flex-1">
                <label className="text-xs font-medium text-gray-500 block mb-1">Montant</label>
                <input type="number" min="1" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gray-900" placeholder="0.00" value={withdrawAmount} onChange={(e) => setWithdrawAmount(e.target.value)} />
              </div>
              <div>
                <label className="text-xs font-medium text-gray-500 block mb-1">Devise</label>
                <select className="border border-gray-200 rounded-lg px-3 py-2 text-sm" value={withdrawCurrency} onChange={(e) => setWithdrawCurrency(e.target.value)}>
                  {CURRENCIES.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>
            </div>
            <div>
              <label className="text-xs font-medium text-gray-500 block mb-1">Numéro de téléphone</label>
              <input className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gray-900" placeholder="+22890000000" value={withdrawPhone} onChange={(e) => setWithdrawPhone(e.target.value)} />
            </div>
            <div className="flex gap-3">
              <div className="flex-1">
                <label className="text-xs font-medium text-gray-500 block mb-1">Pays (code ISO)</label>
                <input className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gray-900" placeholder="TG, BJ, SN…" maxLength={2} value={withdrawCountry} onChange={(e) => setWithdrawCountry(e.target.value.toUpperCase())} />
              </div>
              <div className="flex-1">
                <label className="text-xs font-medium text-gray-500 block mb-1">Nom bénéficiaire (opt.)</label>
                <input className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gray-900" placeholder="Nom complet" value={withdrawName} onChange={(e) => setWithdrawName(e.target.value)} />
              </div>
            </div>
            <button onClick={() => void handleWithdraw()} disabled={withdrawing || !withdrawAmount || !withdrawPhone || !withdrawCountry} className="w-full bg-gray-900 text-white rounded-lg py-2.5 text-sm font-medium disabled:opacity-40">
              {withdrawing ? "Retrait en cours…" : "Initier le retrait"}
            </button>
          </div>
          <p className="text-xs text-gray-400">Délai de traitement : 1–24h selon l'opérateur.</p>
        </div>
      )}

      {/* ── Payment Methods ───────────────────────────────────────────────── */}
      {activeTab === "methods" && (
        <div className="space-y-3">
          <h3 className="font-semibold">Méthodes de paiement sauvegardées</h3>
          {loadingMethods ? (
            <div className="space-y-2">{[1, 2].map((i) => <div key={i} className="h-14 bg-gray-100 rounded-xl animate-pulse" />)}</div>
          ) : methods.length === 0 ? (
            <div className="border rounded-xl p-8 text-center text-gray-400">
              <p className="text-3xl mb-2">💳</p>
              <p>Aucune méthode sauvegardée.</p>
              <p className="text-xs mt-1">Effectuez un dépôt Stripe pour enregistrer une carte.</p>
            </div>
          ) : (
            methods.map((m) => (
              <div key={m.id} className="bg-white border rounded-xl p-4 flex items-center justify-between">
                <div>
                  <p className="font-medium text-sm capitalize">{m.type}</p>
                  {Object.entries(m.details).map(([k, v]) => (
                    <p key={k} className="text-xs text-gray-500">{k}: {v}</p>
                  ))}
                  {m.isDefault && <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full font-medium">Par défaut</span>}
                </div>
                <button
                  onClick={() => void handleDeleteMethod(m.id)}
                  disabled={deletingMethod === m.id}
                  className="text-red-500 text-sm hover:text-red-700 disabled:opacity-40"
                >
                  {deletingMethod === m.id ? "…" : "Supprimer"}
                </button>
              </div>
            ))
          )}
        </div>
      )}

      {/* ── Virtual Cards ─────────────────────────────────────────────────── */}
      {activeTab === "cards" && (
        <div className="space-y-4">
          <div className="bg-white border rounded-xl p-4 space-y-3">
            <h3 className="font-semibold">Créer une carte virtuelle</h3>
            <div className="flex gap-3">
              <div>
                <label className="text-xs font-medium text-gray-500 block mb-1">Type</label>
                <select className="border border-gray-200 rounded-lg px-3 py-2 text-sm" value={cardType} onChange={(e) => setCardType(e.target.value as "visa" | "mastercard")}>
                  <option value="visa">Visa</option>
                  <option value="mastercard">Mastercard</option>
                </select>
              </div>
              <div>
                <label className="text-xs font-medium text-gray-500 block mb-1">Devise wallet</label>
                <select className="border border-gray-200 rounded-lg px-3 py-2 text-sm" value={cardCurrency} onChange={(e) => setCardCurrency(e.target.value)}>
                  {CURRENCIES.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>
              <div className="flex items-end">
                <button onClick={() => void handleCreateCard()} disabled={creatingCard} className="bg-gray-900 text-white rounded-lg px-4 py-2 text-sm font-medium disabled:opacity-40">
                  {creatingCard ? "…" : "Créer"}
                </button>
              </div>
            </div>
          </div>

          {loadingCards ? (
            <div className="space-y-2">{[1, 2].map((i) => <div key={i} className="h-20 bg-gray-100 rounded-xl animate-pulse" />)}</div>
          ) : cards.length === 0 ? (
            <div className="border rounded-xl p-8 text-center text-gray-400">
              <p className="text-3xl mb-2">🃏</p>
              <p>Aucune carte virtuelle.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {cards.map((card) => (
                <div key={card.id} className="bg-white border rounded-xl p-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-semibold capitalize">{card.card_type} · {card.currency}</p>
                      {card.masked_number && <p className="text-sm text-gray-600 font-mono">{card.masked_number}</p>}
                      <p className="text-xs text-gray-400">{new Date(card.created_at).toLocaleDateString("fr-FR")}</p>
                    </div>
                    <span className={`text-xs px-3 py-1 rounded-full font-medium ${card.status === "active" ? "bg-green-100 text-green-700" : card.status === "frozen" ? "bg-blue-100 text-blue-700" : "bg-red-100 text-red-700"}`}>
                      {card.status === "active" ? "Active" : card.status === "frozen" ? "Gelée" : "Annulée"}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
