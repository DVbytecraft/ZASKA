import { Link, useNavigate, useParams } from "react-router-dom";
import { useEffect, useState } from "react";
import { api, type Task, type NegotiationEvent } from "../api";

const STATUS_LABELS: Record<string, string> = {
  OPEN: "Ouvert",
  ASSIGNED: "Assigné",
  IN_PROGRESS: "En cours",
  COMPLETED: "Complété",
  CONFIRMED: "Confirmé",
  CANCELLED: "Annulé",
  DISPUTED: "Contesté",
  PAUSED: "En pause",
};

const STATUS_COLORS: Record<string, string> = {
  OPEN: "bg-blue-100 text-blue-700",
  ASSIGNED: "bg-amber-100 text-amber-700",
  IN_PROGRESS: "bg-amber-100 text-amber-700",
  COMPLETED: "bg-purple-100 text-purple-700",
  CONFIRMED: "bg-green-100 text-green-700",
  CANCELLED: "bg-gray-100 text-gray-500",
  DISPUTED: "bg-red-100 text-red-700",
  PAUSED: "bg-gray-100 text-gray-500",
};

function ActionBtn({
  onClick,
  variant = "primary",
  loading,
  children,
}: {
  onClick: () => void;
  variant?: "primary" | "secondary" | "danger" | "success";
  loading?: boolean;
  children: React.ReactNode;
}) {
  const base = "px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-40 transition-colors";
  const variants = {
    primary: "bg-gray-900 text-white hover:bg-gray-700",
    secondary: "bg-white border border-gray-300 text-gray-700 hover:bg-gray-50",
    danger: "bg-red-600 text-white hover:bg-red-500",
    success: "bg-green-600 text-white hover:bg-green-500",
  };
  return (
    <button className={`${base} ${variants[variant]}`} onClick={onClick} disabled={loading}>
      {loading ? "…" : children}
    </button>
  );
}

export function TaskDetailPage() {
  const { taskId = "" } = useParams();
  const navigate = useNavigate();
  const userId = localStorage.getItem("zaska_user_id") ?? "";

  const [task, setTask] = useState<Task | null>(null);
  const [history, setHistory] = useState<NegotiationEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [msg, setMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [loading, setLoading] = useState(true);

  // Action states
  const [applyMsg, setApplyMsg] = useState("");
  const [applyPrice, setApplyPrice] = useState("");
  const [applying, setApplying] = useState(false);
  const [hasApplied, setHasApplied] = useState(false);

  const [completing, setCompleting] = useState(false);
  const [completePct, setCompletePct] = useState("100");

  const [confirming, setConfirming] = useState(false);
  const [contesting, setContesting] = useState(false);
  const [contestReason, setContestReason] = useState("");
  const [showContestForm, setShowContestForm] = useState(false);

  const [rating, setRating] = useState(false);
  const [ratingScore, setRatingScore] = useState(5);

  const [cancelling, setCancelling] = useState(false);

  const [negotiatePrice, setNegotiatePrice] = useState("");
  const [negotiating, setNegotiating] = useState(false);
  const [showNegotiate, setShowNegotiate] = useState(false);

  const isCreator = task?.createdBy === userId;
  const isTasker = task?.assignedTo === userId;
  const isParticipant = isCreator || isTasker;

  async function load() {
    const [taskRes, histRes] = await Promise.all([
      api.getTask(taskId),
      api.getNegotiationHistory(taskId),
    ]);
    setLoading(false);
    if (!taskRes.success) { setError(taskRes.error ?? "Chargement impossible"); return; }
    setTask(taskRes.data);
    if (histRes.success) setHistory(histRes.data);
    // Check if current user already applied
    const appsRes = await api.getMyApplications();
    if (appsRes.success) {
      setHasApplied(appsRes.data.some((a) => a.taskId === taskId));
    }
  }

  useEffect(() => { void load(); }, [taskId]);

  async function handleApply() {
    setApplying(true);
    const price = applyPrice ? parseFloat(applyPrice) : undefined;
    const res = await api.applyTask(taskId, applyMsg || undefined, price);
    setApplying(false);
    if (res.success) { setMsg({ type: "success", text: "Candidature envoyée !" }); setHasApplied(true); }
    else setMsg({ type: "error", text: res.error ?? "Erreur lors de la candidature" });
  }

  async function handleComplete() {
    setCompleting(true);
    const pct = parseInt(completePct, 10) || 100;
    const res = await api.completeTask(taskId, pct);
    setCompleting(false);
    if (res.success) { setTask(res.data); setMsg({ type: "success", text: "Tâche marquée complétée." }); }
    else setMsg({ type: "error", text: res.error ?? "Erreur" });
  }

  async function handleConfirm() {
    setConfirming(true);
    const res = await api.confirmTask(taskId);
    setConfirming(false);
    if (res.success) { setTask(res.data); setMsg({ type: "success", text: "Tâche confirmée, paiement libéré." }); }
    else setMsg({ type: "error", text: res.error ?? "Erreur" });
  }

  async function handleContest() {
    if (!contestReason.trim()) { setMsg({ type: "error", text: "Veuillez préciser la raison." }); return; }
    setContesting(true);
    const res = await api.contestTask(taskId, contestReason);
    setContesting(false);
    if (res.success) { setTask(res.data); setMsg({ type: "success", text: "Contestation envoyée." }); setShowContestForm(false); }
    else setMsg({ type: "error", text: res.error ?? "Erreur" });
  }

  async function handleRate() {
    setRating(true);
    const res = await api.rateTask(taskId, ratingScore);
    setRating(false);
    if (res.success) setMsg({ type: "success", text: "Évaluation envoyée !" });
    else setMsg({ type: "error", text: res.error ?? "Erreur" });
  }

  async function handleCancel() {
    if (!confirm("Annuler cette tâche ?")) return;
    setCancelling(true);
    const res = await api.cancelTask(taskId);
    setCancelling(false);
    if (res.success) navigate("/tasks");
    else setMsg({ type: "error", text: res.error ?? "Erreur" });
  }

  async function handleNegotiate() {
    const price = parseFloat(negotiatePrice);
    if (!negotiatePrice || isNaN(price) || price <= 0) { setMsg({ type: "error", text: "Prix invalide." }); return; }
    setNegotiating(true);
    const res = await api.negotiateTask(taskId, price);
    setNegotiating(false);
    if (res.success) {
      setTask(res.data);
      setMsg({ type: "success", text: "Proposition envoyée." });
      setNegotiatePrice("");
      const histRes = await api.getNegotiationHistory(taskId);
      if (histRes.success) setHistory(histRes.data);
    } else setMsg({ type: "error", text: res.error ?? "Erreur" });
  }

  async function handleRespondNegotiation(accept: boolean) {
    const res = await api.respondNegotiation(taskId, accept);
    if (res.success) { setTask(res.data); setMsg({ type: "success", text: accept ? "Proposition acceptée." : "Proposition refusée." }); }
    else setMsg({ type: "error", text: res.error ?? "Erreur" });
  }

  if (loading) return <p className="text-gray-500">Chargement…</p>;
  if (error) return <p className="text-red-600">{error}</p>;
  if (!task) return null;

  const status = task.status;
  const pendingNeg = history.find((h) => h.type === "proposed" || h.type === "counter");
  const isMyProposal = pendingNeg?.userId === userId;

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold">{task.title}</h2>
          {(task.city || task.address) && (
            <p className="text-sm text-gray-500 mt-0.5">{[task.city, task.address].filter(Boolean).join(" · ")}</p>
          )}
        </div>
        <span className={`text-xs font-semibold px-3 py-1 rounded-full flex-shrink-0 ${STATUS_COLORS[status] ?? "bg-gray-100 text-gray-500"}`}>
          {STATUS_LABELS[status] ?? status}
        </span>
      </div>

      {/* Description */}
      <p className="text-gray-700 leading-relaxed whitespace-pre-line">{task.description}</p>

      {/* Price */}
      <div className="bg-white border rounded-xl p-4 flex items-center justify-between">
        <div>
          <p className="text-xs text-gray-500">Prix</p>
          <p className="text-2xl font-bold">{parseFloat(String(task.price)).toFixed(2)} <span className="text-base font-medium">{task.currency}</span></p>
          {task.negotiatedPrice && (
            <p className="text-sm text-amber-600">Négocié : {parseFloat(String(task.negotiatedPrice)).toFixed(2)} {task.currency}</p>
          )}
        </div>
        {isParticipant && (
          <Link className="text-sm text-blue-600 underline" to={`/chat/${task.id}`}>
            Ouvrir le chat →
          </Link>
        )}
      </div>

      {/* Feedback banner */}
      {msg && (
        <div className={`text-sm px-4 py-3 rounded-xl border flex justify-between items-center ${msg.type === "success" ? "bg-green-50 border-green-200 text-green-800" : "bg-red-50 border-red-200 text-red-700"}`}>
          <span>{msg.text}</span>
          <button onClick={() => setMsg(null)} className="font-bold opacity-60 hover:opacity-100 ml-3">×</button>
        </div>
      )}

      {/* ── Creator Actions ───────────────────────────────────────────────── */}
      {isCreator && (
        <div className="bg-white border rounded-xl p-4 space-y-3">
          <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide">Actions créateur</h3>
          <div className="flex flex-wrap gap-2">
            {status === "OPEN" && (
              <>
                <Link to={`/tasks/${taskId}/applicants`}>
                  <ActionBtn variant="primary" onClick={() => {}}>Voir les candidatures</ActionBtn>
                </Link>
                <ActionBtn variant="danger" loading={cancelling} onClick={() => void handleCancel()}>Annuler la tâche</ActionBtn>
              </>
            )}
            {(status === "COMPLETED") && (
              <>
                <ActionBtn variant="success" loading={confirming} onClick={() => void handleConfirm()}>
                  Confirmer et payer le tasker
                </ActionBtn>
                {!showContestForm && (
                  <ActionBtn variant="danger" onClick={() => setShowContestForm(true)}>Contester</ActionBtn>
                )}
              </>
            )}
            {status === "CONFIRMED" && (
              <div className="flex items-center gap-3 w-full">
                <span className="text-sm text-gray-600">Noter le tasker :</span>
                <select className="border rounded px-2 py-1 text-sm" value={ratingScore} onChange={(e) => setRatingScore(Number(e.target.value))}>
                  {[5, 4, 3, 2, 1].map((s) => <option key={s} value={s}>{s} ★</option>)}
                </select>
                <ActionBtn variant="primary" loading={rating} onClick={() => void handleRate()}>Envoyer</ActionBtn>
              </div>
            )}
          </div>
          {/* Contest form */}
          {showContestForm && (
            <div className="space-y-2 pt-2 border-t">
              <textarea
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-gray-900"
                rows={3}
                placeholder="Expliquez la raison de la contestation…"
                value={contestReason}
                onChange={(e) => setContestReason(e.target.value)}
              />
              <div className="flex gap-2">
                <ActionBtn variant="danger" loading={contesting} onClick={() => void handleContest()}>Confirmer contestation</ActionBtn>
                <ActionBtn variant="secondary" onClick={() => setShowContestForm(false)}>Annuler</ActionBtn>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Tasker Actions ────────────────────────────────────────────────── */}
      {!isCreator && (
        <div className="bg-white border rounded-xl p-4 space-y-3">
          <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide">Actions tasker</h3>
          {/* Apply */}
          {status === "OPEN" && !hasApplied && !isTasker && (
            <div className="space-y-2">
              <input
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gray-900"
                placeholder="Message (optionnel)"
                value={applyMsg}
                onChange={(e) => setApplyMsg(e.target.value)}
              />
              <div className="flex gap-2">
                <input
                  type="number"
                  className="w-32 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gray-900"
                  placeholder={`Prix (${task.currency})`}
                  value={applyPrice}
                  onChange={(e) => setApplyPrice(e.target.value)}
                />
                <ActionBtn variant="primary" loading={applying} onClick={() => void handleApply()}>Postuler</ActionBtn>
              </div>
            </div>
          )}
          {status === "OPEN" && hasApplied && !isTasker && (
            <p className="text-sm text-green-700 font-medium">✓ Candidature envoyée</p>
          )}
          {/* Complete */}
          {isTasker && (status === "ASSIGNED" || status === "IN_PROGRESS") && (
            <div className="flex items-center gap-3">
              <label className="text-sm text-gray-600">Complétion :</label>
              <select
                className="border rounded px-2 py-1 text-sm"
                value={completePct}
                onChange={(e) => setCompletePct(e.target.value)}
              >
                {["25", "50", "75", "100"].map((v) => <option key={v} value={v}>{v}%</option>)}
              </select>
              <ActionBtn variant="primary" loading={completing} onClick={() => void handleComplete()}>
                Marquer complété
              </ActionBtn>
            </div>
          )}
          {/* Rate after confirm */}
          {isTasker && status === "CONFIRMED" && (
            <div className="flex items-center gap-3">
              <span className="text-sm text-gray-600">Noter le client :</span>
              <select className="border rounded px-2 py-1 text-sm" value={ratingScore} onChange={(e) => setRatingScore(Number(e.target.value))}>
                {[5, 4, 3, 2, 1].map((s) => <option key={s} value={s}>{s} ★</option>)}
              </select>
              <ActionBtn variant="primary" loading={rating} onClick={() => void handleRate()}>Envoyer</ActionBtn>
            </div>
          )}
        </div>
      )}

      {/* ── Négociation ───────────────────────────────────────────────────── */}
      {(status === "OPEN" || status === "ASSIGNED") && isParticipant && (
        <div className="bg-white border rounded-xl p-4 space-y-3">
          <button
            className="flex items-center justify-between w-full text-sm font-semibold"
            onClick={() => setShowNegotiate((v) => !v)}
          >
            <span>Négociation de prix</span>
            <span className="text-gray-400">{showNegotiate ? "▲" : "▼"}</span>
          </button>

          {showNegotiate && (
            <>
              {/* Pending response */}
              {pendingNeg && !isMyProposal && (
                <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-sm">
                  <p className="font-medium">Proposition en attente : <span className="text-amber-700">{pendingNeg.proposedPrice} {task.currency}</span></p>
                  <div className="flex gap-2 mt-2">
                    <ActionBtn variant="success" onClick={() => void handleRespondNegotiation(true)}>Accepter</ActionBtn>
                    <ActionBtn variant="danger" onClick={() => void handleRespondNegotiation(false)}>Refuser</ActionBtn>
                  </div>
                </div>
              )}
              {/* Propose form */}
              <div className="flex gap-2">
                <input
                  type="number"
                  className="w-36 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gray-900"
                  placeholder={`Prix (${task.currency})`}
                  value={negotiatePrice}
                  onChange={(e) => setNegotiatePrice(e.target.value)}
                />
                <ActionBtn variant="secondary" loading={negotiating} onClick={() => void handleNegotiate()}>
                  Proposer
                </ActionBtn>
              </div>
              {/* History */}
              {history.length > 0 && (
                <div className="space-y-1 max-h-40 overflow-y-auto">
                  <p className="text-xs text-gray-400 font-medium">Historique</p>
                  {history.map((h, i) => (
                    <div key={i} className="flex justify-between text-xs text-gray-600 border-b py-1">
                      <span>{h.type} — {h.proposedPrice ? `${h.proposedPrice} ${task.currency}` : "—"}</span>
                      <span className="text-gray-400">{new Date(h.createdAt).toLocaleDateString("fr-FR")}</span>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
