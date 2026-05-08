import { useEffect, useState } from 'react';
import { ArrowLeft, CreditCard, Plus, Snowflake, X, Eye, EyeOff, AlertCircle, Loader, ShieldCheck } from 'lucide-react';
import { cardService, apiClient } from '@zaska/shared-services';
import type { VirtualCard, VirtualCardCreateResult } from '@zaska/shared-services';

interface VirtualCardScreenProps {
  onBack: () => void;
}

const CARD_GRADIENTS: Record<string, string> = {
  visa: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%)',
  mastercard: 'linear-gradient(135deg, #1a1a2e 0%, #2d1b69 50%, #6D28D9 100%)',
};

const STATUS_LABELS: Record<string, { label: string; color: string }> = {
  active: { label: 'Active', color: '#22C55E' },
  frozen: { label: 'Gelée', color: '#3B82F6' },
  cancelled: { label: 'Annulée', color: '#EF4444' },
};

function CardVisual({ card }: { card: VirtualCard }) {
  const gradient = CARD_GRADIENTS[card.cardType] ?? CARD_GRADIENTS.visa;
  const exp = `${String(card.expiryMonth).padStart(2, '0')}/${String(card.expiryYear).slice(-2)}`;
  const status = STATUS_LABELS[card.status] ?? STATUS_LABELS.active;

  return (
    <div
      className="relative w-full rounded-3xl p-6 text-white shadow-2xl overflow-hidden"
      style={{ background: gradient, minHeight: 190 }}
    >
      {/* Decorative circles */}
      <div className="absolute -top-8 -right-8 w-32 h-32 rounded-full bg-white/5" />
      <div className="absolute -bottom-4 -left-4 w-24 h-24 rounded-full bg-white/5" />

      <div className="relative">
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-2">
            <CreditCard size={20} className="text-white/70" />
            <span className="text-xs font-semibold text-white/70 uppercase tracking-widest">
              Zaska Card
            </span>
          </div>
          <div
            className="px-2.5 py-1 rounded-full text-xs font-bold"
            style={{ background: `${status.color}30`, color: status.color }}
          >
            {status.label}
          </div>
        </div>

        <p className="text-xl font-mono font-bold tracking-widest mb-6">
          {card.cardNumberMasked}
        </p>

        <div className="flex items-end justify-between">
          <div>
            <p className="text-white/50 text-xs mb-1">EXPIRE</p>
            <p className="font-mono font-bold">{exp}</p>
          </div>
          <div className="text-right">
            <p className="text-white/50 text-xs mb-1">DEVISE</p>
            <p className="font-bold text-sm">{card.walletCurrency}</p>
          </div>
          {/* Visa/MC logo */}
          {card.cardType === 'visa' ? (
            <div className="text-white font-black italic text-2xl tracking-tight">VISA</div>
          ) : (
            <div className="flex">
              <div className="w-8 h-8 rounded-full bg-red-500/80" />
              <div className="w-8 h-8 rounded-full bg-amber-400/80 -ml-4" />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function NewCardReveal({ result, onClose }: { result: VirtualCardCreateResult; onClose: () => void }) {
  const [showCvv, setShowCvv] = useState(false);
  return (
    <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-6">
      <div className="w-full max-w-sm bg-white rounded-3xl p-6">
        <div className="flex items-center gap-2 mb-4">
          <div className="w-8 h-8 rounded-full bg-green-100 flex items-center justify-center">
            <ShieldCheck size={18} className="text-green-600" />
          </div>
          <h3 className="font-bold text-gray-900">Carte créée !</h3>
        </div>

        <div className="bg-amber-50 border border-amber-200 rounded-2xl p-4 mb-5">
          <p className="text-xs text-amber-800 font-semibold mb-1">⚠ Copiez ces informations maintenant</p>
          <p className="text-xs text-amber-700">Le CVV ne sera plus visible après la fermeture de cette fenêtre.</p>
        </div>

        <div className="space-y-3 mb-5">
          <div className="bg-gray-50 rounded-xl p-3">
            <p className="text-xs text-gray-400 mb-1">Numéro</p>
            <p className="font-mono font-bold text-gray-900 text-base">{result.cardNumberMasked}</p>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="bg-gray-50 rounded-xl p-3">
              <p className="text-xs text-gray-400 mb-1">Expiration</p>
              <p className="font-mono font-bold text-gray-900">{result.expiryFormatted}</p>
            </div>
            <div className="bg-gray-50 rounded-xl p-3">
              <div className="flex items-center justify-between mb-1">
                <p className="text-xs text-gray-400">CVV</p>
                <button onClick={() => setShowCvv(!showCvv)} className="text-gray-400">
                  {showCvv ? <EyeOff size={12} /> : <Eye size={12} />}
                </button>
              </div>
              <p className="font-mono font-bold text-gray-900">
                {showCvv ? result.cvv : '•••'}
              </p>
            </div>
          </div>
        </div>

        <button
          onClick={onClose}
          className="w-full py-3.5 rounded-xl font-bold text-white"
          style={{ background: 'linear-gradient(135deg,#6D28D9,#7C3AED)' }}
        >
          J'ai noté mes informations
        </button>
      </div>
    </div>
  );
}

function CreateCardSheet({ onCreated, onClose }: { onCreated: (result: VirtualCardCreateResult) => void; onClose: () => void }) {
  const [cardType, setCardType] = useState<'visa' | 'mastercard'>('visa');
  const currency = apiClient.getCurrency() ?? 'USD';
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleCreate = async () => {
    setCreating(true);
    setError(null);
    try {
      const result = await cardService.createCard(cardType, currency);
      onCreated(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erreur lors de la création');
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/50 flex items-end" onClick={onClose}>
      <div className="w-full bg-white rounded-t-3xl" onClick={e => e.stopPropagation()}>
        <div className="px-6 pt-5 pb-3 border-b border-gray-100 flex items-center justify-between">
          <h3 className="text-lg font-bold text-gray-900">Créer une carte virtuelle</h3>
          <button onClick={onClose} className="text-gray-400 font-bold text-xl leading-none">✕</button>
        </div>
        <div className="px-6 py-5 space-y-4">
          <div>
            <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">Type de carte</label>
            <div className="grid grid-cols-2 gap-3">
              {(['visa', 'mastercard'] as const).map(type => (
                <button
                  key={type}
                  onClick={() => setCardType(type)}
                  className={`p-4 rounded-2xl border-2 text-center transition-all ${
                    cardType === type ? 'border-[#6D28D9] bg-purple-50' : 'border-gray-100'
                  }`}
                >
                  {type === 'visa' ? (
                    <p className="font-black italic text-2xl text-[#1a1f71] tracking-tight">VISA</p>
                  ) : (
                    <div className="flex items-center justify-center gap-1">
                      <div className="w-7 h-7 rounded-full bg-red-500" />
                      <div className="w-7 h-7 rounded-full bg-amber-400 -ml-3" />
                    </div>
                  )}
                  <p className="text-xs font-semibold text-gray-600 mt-1 capitalize">{type}</p>
                </button>
              ))}
            </div>
          </div>

          <div className="bg-gray-50 rounded-2xl p-4">
            <p className="text-xs text-gray-500 mb-1">Devise du portefeuille</p>
            <p className="font-bold text-gray-900">{currency}</p>
          </div>

          <div className="bg-blue-50 border border-blue-100 rounded-xl p-3">
            <p className="text-xs text-blue-800">
              Votre carte virtuelle sera liée à votre portefeuille Zaska. Vous pouvez recevoir des paiements et utiliser la carte pour des achats en ligne.
            </p>
          </div>

          {error && (
            <div className="flex items-center gap-2 bg-red-50 border border-red-100 rounded-xl px-3 py-2">
              <AlertCircle size={15} className="text-red-500 shrink-0" />
              <p className="text-sm text-red-600">{error}</p>
            </div>
          )}

          <button
            onClick={handleCreate}
            disabled={creating}
            className="w-full py-4 rounded-xl font-bold text-base text-white"
            style={{ background: creating ? '#D1D5DB' : 'linear-gradient(135deg,#6D28D9,#7C3AED)' }}
          >
            {creating ? <span className="flex items-center justify-center gap-2"><Loader size={16} className="animate-spin" /> Création…</span> : 'Créer ma carte'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Main screen ───────────────────────────────────────────────────────────────
export function VirtualCardScreen({ onBack }: VirtualCardScreenProps) {
  const [cards, setCards] = useState<VirtualCard[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [newCardResult, setNewCardResult] = useState<VirtualCardCreateResult | null>(null);
  const [statusUpdating, setStatusUpdating] = useState<string | null>(null);
  const [confirmCancel, setConfirmCancel] = useState<string | null>(null);

  const load = () => {
    setLoading(true);
    setLoadError(null);
    cardService.listCards()
      .then(setCards)
      .catch(err => setLoadError(err instanceof Error ? err.message : 'Erreur de chargement'))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const handleToggleFreeze = async (card: VirtualCard) => {
    const newStatus = card.status === 'frozen' ? 'active' : 'frozen';
    setStatusUpdating(card.id);
    try {
      const updated = await cardService.updateCardStatus(card.id, newStatus);
      setCards(prev => prev.map(c => c.id === card.id ? updated : c));
    } catch {
      // silent
    } finally {
      setStatusUpdating(null);
    }
  };

  const handleCancel = async (cardId: string) => {
    setStatusUpdating(cardId);
    try {
      const updated = await cardService.updateCardStatus(cardId, 'cancelled');
      setCards(prev => prev.map(c => c.id === cardId ? updated : c));
    } catch {
      // silent
    } finally {
      setStatusUpdating(null);
      setConfirmCancel(null);
    }
  };

  const handleCreated = (result: VirtualCardCreateResult) => {
    setShowCreate(false);
    setNewCardResult(result);
    setCards(prev => [result, ...prev]);
  };

  const activeCards = cards.filter(c => c.status !== 'cancelled');
  const canCreate = activeCards.length < 2;

  return (
    <div className="h-full flex flex-col bg-gray-50" style={{ fontFamily: "'Poppins', sans-serif" }}>
      {showCreate && (
        <CreateCardSheet
          onCreated={handleCreated}
          onClose={() => setShowCreate(false)}
        />
      )}

      {newCardResult && (
        <NewCardReveal
          result={newCardResult}
          onClose={() => setNewCardResult(null)}
        />
      )}

      {/* Confirm cancel */}
      {confirmCancel && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-6">
          <div className="bg-white rounded-3xl p-6 w-full max-w-sm">
            <h3 className="font-bold text-gray-900 mb-2">Annuler la carte ?</h3>
            <p className="text-sm text-gray-500 mb-5">Cette action est irréversible. La carte sera définitivement désactivée.</p>
            <div className="flex gap-3">
              <button onClick={() => setConfirmCancel(null)} className="flex-1 py-3 rounded-xl border-2 border-gray-200 font-semibold text-gray-700">
                Annuler
              </button>
              <button
                onClick={() => handleCancel(confirmCancel)}
                className="flex-1 py-3 rounded-xl bg-red-500 font-semibold text-white"
              >
                Confirmer
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Header */}
      <div className="px-6 pt-8 pb-4 bg-white border-b border-gray-100">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button onClick={onBack} className="p-2 -ml-2 hover:bg-gray-100 rounded-full transition-colors">
              <ArrowLeft size={24} className="text-gray-700" />
            </button>
            <div>
              <h2 className="text-xl font-bold text-gray-900">Cartes virtuelles</h2>
              <p className="text-xs text-gray-400">{activeCards.length} / 2 cartes actives</p>
            </div>
          </div>
          {canCreate && (
            <button
              onClick={() => setShowCreate(true)}
              className="flex items-center gap-1.5 px-4 py-2 bg-purple-50 text-[#6D28D9] rounded-xl font-semibold text-sm"
            >
              <Plus size={16} />
              Créer
            </button>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-auto p-6">
        {loadError && (
          <div className="flex items-center gap-2 bg-red-50 border border-red-100 rounded-xl px-3 py-2 mb-4">
            <AlertCircle size={16} className="text-red-500 shrink-0" />
            <p className="text-sm text-red-600 flex-1">{loadError}</p>
            <button onClick={load} className="text-xs font-semibold text-red-600 underline">Réessayer</button>
          </div>
        )}

        {loading ? (
          <div className="space-y-4">
            <div className="h-48 bg-gray-200 rounded-3xl animate-pulse" />
          </div>
        ) : cards.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-52 text-center">
            <div className="w-16 h-16 bg-purple-100 rounded-2xl flex items-center justify-center mb-4">
              <CreditCard size={28} className="text-[#6D28D9]" />
            </div>
            <p className="font-semibold text-gray-700 mb-1">Aucune carte virtuelle</p>
            <p className="text-sm text-gray-400 mb-4">Créez votre carte Visa ou Mastercard et recevez de l'argent directement dessus</p>
            <button
              onClick={() => setShowCreate(true)}
              className="px-6 py-2.5 bg-purple-50 text-[#6D28D9] rounded-xl font-semibold text-sm"
            >
              Créer une carte
            </button>
          </div>
        ) : (
          <div className="space-y-6">
            {cards.map(card => (
              <div key={card.id}>
                <CardVisual card={card} />
                {card.status !== 'cancelled' && (
                  <div className="flex gap-2 mt-3">
                    <button
                      onClick={() => handleToggleFreeze(card)}
                      disabled={statusUpdating === card.id}
                      className={`flex-1 flex items-center justify-center gap-2 py-3 rounded-2xl font-semibold text-sm transition-all ${
                        card.status === 'frozen'
                          ? 'bg-blue-500 text-white'
                          : 'bg-white border-2 border-gray-200 text-gray-700'
                      }`}
                    >
                      {statusUpdating === card.id ? (
                        <Loader size={14} className="animate-spin" />
                      ) : (
                        <Snowflake size={16} />
                      )}
                      {card.status === 'frozen' ? 'Dégeler' : 'Geler'}
                    </button>
                    <button
                      onClick={() => setConfirmCancel(card.id)}
                      disabled={statusUpdating === card.id}
                      className="flex items-center justify-center gap-2 px-4 py-3 rounded-2xl bg-white border-2 border-red-100 text-red-500 font-semibold text-sm"
                    >
                      <X size={16} />
                      Annuler
                    </button>
                  </div>
                )}
              </div>
            ))}

            {!canCreate && (
              <div className="bg-amber-50 border border-amber-100 rounded-2xl p-4 text-center">
                <p className="text-xs text-amber-700">
                  Limite de 2 cartes actives atteinte. Annulez une carte existante pour en créer une nouvelle.
                </p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
