import { useState, useEffect } from 'react';
import { ArrowLeft, Plus, Smartphone, Trash2, Star, AlertCircle } from 'lucide-react';
import { walletService, apiClient } from '@zaska/shared-services';
import type { SavedPaymentMethod } from '@zaska/shared-services';
import { getOperators, getCountry, SUPPORTED_COUNTRIES, type SupportedCountry, type MobileMoneyOperator } from '../config/countries';

interface PaymentMethodsScreenProps {
  onBack: () => void;
  onAddPaymentMethod?: () => void;
}

export function PaymentMethodsScreen({ onBack }: PaymentMethodsScreenProps) {
  const countryCode = apiClient.getCountryCode() ?? 'TG';
  const country = getCountry(countryCode);

  const [methods, setMethods] = useState<SavedPaymentMethod[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  // Form add
  const [addOperator, setAddOperator] = useState<MobileMoneyOperator | null>(null);
  const [addPhone, setAddPhone] = useState('');
  const [addNickname, setAddNickname] = useState('');
  const [addDefault, setAddDefault] = useState(false);
  const [addCountry, setAddCountry] = useState<SupportedCountry>(
    SUPPORTED_COUNTRIES.find(c => c.code === countryCode) ?? SUPPORTED_COUNTRIES[0]
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const operators = getOperators(addCountry.code);

  const load = () => {
    setLoading(true);
    setLoadError(null);
    walletService.listPaymentMethods()
      .then(setMethods)
      .catch((err) => setLoadError(err instanceof Error ? err.message : 'Failed to load payment methods'))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const handleDelete = async (id: string) => {
    setDeleting(id);
    setDeleteError(null);
    try {
      await walletService.deletePaymentMethod(id);
      setMethods(prev => prev.filter(m => m.id !== id));
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : 'Failed to delete payment method');
    } finally {
      setDeleting(null);
    }
  };

  const handleAdd = async () => {
    if (!addOperator || !addPhone) return;
    setSaving(true);
    setError('');
    try {
      const m = await walletService.addPaymentMethod({
        provider: addOperator.id,
        phone_number: addPhone,
        country_code: addCountry.code,
        nickname: addNickname || undefined,
        is_default: addDefault,
      });
      setMethods(prev => addDefault
        ? [m, ...prev.map(x => ({ ...x, is_default: false }))]
        : [...prev, m]
      );
      setShowAdd(false);
      setAddPhone('');
      setAddNickname('');
      setAddDefault(false);
      setAddOperator(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erreur lors de l\'ajout');
    } finally {
      setSaving(false);
    }
  };

  const phoneValid = /^\+[1-9]\d{6,14}$/.test(addPhone);

  const providerColor: Record<string, string> = Object.fromEntries(
    getOperators(addCountry.code).map(op => [op.id, op.color])
  );

  return (
    <div className="h-full flex flex-col bg-gray-50" style={{ fontFamily: "'Poppins', sans-serif" }}>
      {/* Add overlay */}
      {showAdd && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-end">
          <div className="w-full bg-white rounded-t-3xl max-h-[85vh] flex flex-col">
            <div className="px-6 pt-5 pb-3 border-b border-gray-100 flex items-center justify-between">
              <h3 className="text-lg font-bold text-gray-900">Ajouter un compte</h3>
              <button onClick={() => setShowAdd(false)} className="text-gray-400 font-bold text-xl">✕</button>
            </div>
            <div className="overflow-y-auto flex-1 px-6 py-4 space-y-4">
              {/* Pays */}
              <div>
                <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Pays</label>
                <div className="grid grid-cols-2 gap-2 max-h-40 overflow-y-auto">
                  {SUPPORTED_COUNTRIES.filter(c => c.mobileMoneyEnabled).map(c => (
                    <button
                      key={c.code}
                      onClick={() => { setAddCountry(c); setAddOperator(null); }}
                      className={`flex items-center gap-2 p-2.5 rounded-xl border-2 text-left ${
                        addCountry.code === c.code ? 'border-[#6D28D9] bg-purple-50' : 'border-gray-100 bg-gray-50'
                      }`}
                    >
                      <span className="text-xl">{c.flag}</span>
                      <div>
                        <p className="text-xs font-semibold text-gray-900">{c.name}</p>
                        <p className="text-xs text-gray-400">{c.currency}</p>
                      </div>
                    </button>
                  ))}
                </div>
              </div>

              {/* Opérateur */}
              <div>
                <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Opérateur</label>
                <div className="grid grid-cols-2 gap-2">
                  {operators.map(op => (
                    <button
                      key={op.id}
                      onClick={() => setAddOperator(op)}
                      className={`p-3 rounded-xl border-2 flex items-center gap-2 ${
                        addOperator?.id === op.id ? 'border-[#6D28D9] bg-purple-50' : 'border-gray-100 bg-gray-50'
                      }`}
                    >
                      <div className="w-3 h-3 rounded-full" style={{ background: op.color }} />
                      <span className="text-sm font-semibold text-gray-900">{op.name}</span>
                    </button>
                  ))}
                </div>
              </div>

              {/* Numéro */}
              <div>
                <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Numéro</label>
                <input
                  type="tel"
                  placeholder={`${addCountry.dialCode}XXXXXXXX`}
                  value={addPhone}
                  onChange={e => setAddPhone(e.target.value)}
                  className={`w-full px-4 py-3.5 rounded-xl border-2 bg-gray-50 focus:bg-white focus:outline-none transition-all text-gray-900 font-medium placeholder:text-gray-400 ${
                    addPhone && !phoneValid ? 'border-red-300' : 'border-gray-100 focus:border-[#6D28D9]'
                  }`}
                />
              </div>

              {/* Surnom */}
              <div>
                <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Surnom (optionnel)</label>
                <input
                  type="text"
                  placeholder="ex: Mon T-Money principal"
                  value={addNickname}
                  onChange={e => setAddNickname(e.target.value)}
                  className="w-full px-4 py-3.5 rounded-xl border-2 border-gray-100 bg-gray-50 focus:bg-white focus:border-[#6D28D9] focus:outline-none text-gray-900 font-medium placeholder:text-gray-400"
                />
              </div>

              {/* Par défaut */}
              <label className="flex items-center gap-3 cursor-pointer">
                <div
                  onClick={() => setAddDefault(!addDefault)}
                  className={`w-12 h-6 rounded-full transition-colors ${addDefault ? 'bg-[#6D28D9]' : 'bg-gray-300'}`}
                >
                  <div className={`w-5 h-5 bg-white rounded-full shadow transition-transform mt-0.5 ${addDefault ? 'ml-6' : 'ml-0.5'}`} />
                </div>
                <span className="text-sm font-medium text-gray-700">Définir comme méthode par défaut</span>
              </label>

              {error && <p className="text-sm text-red-600 bg-red-50 rounded-xl px-3 py-2">{error}</p>}
            </div>

            <div className="px-6 pb-6 pt-3 border-t border-gray-100">
              <button
                onClick={handleAdd}
                disabled={!addOperator || !phoneValid || saving}
                className="w-full py-4 rounded-xl font-bold text-base text-white transition-all"
                style={{
                  background: (addOperator && phoneValid && !saving)
                    ? 'linear-gradient(135deg, #6D28D9 0%, #7C3AED 100%)'
                    : '#D1D5DB',
                }}
              >
                {saving ? 'Enregistrement...' : 'Enregistrer le compte'}
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="px-6 pt-8 pb-4 bg-white border-b border-gray-100">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button onClick={onBack} className="p-2 -ml-2 hover:bg-gray-100 rounded-full transition-colors">
              <ArrowLeft size={24} className="text-gray-700" />
            </button>
            <div>
              <h2 className="text-xl font-bold text-gray-900">Méthodes de paiement</h2>
              <p className="text-xs text-gray-400">{country?.flag} {country?.name}</p>
            </div>
          </div>
          <button
            onClick={() => setShowAdd(true)}
            className="flex items-center gap-1.5 px-4 py-2 bg-purple-50 text-[#6D28D9] rounded-xl font-semibold text-sm"
          >
            <Plus size={16} />
            Ajouter
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-auto p-6">
        {loadError && (
          <div className="flex items-center gap-2 bg-red-50 border border-red-100 rounded-xl px-3 py-2 mb-4">
            <AlertCircle size={16} className="text-red-500 flex-shrink-0" />
            <p className="text-sm text-red-600 flex-1">{loadError}</p>
            <button onClick={load} className="text-xs font-semibold text-red-600 underline ml-2">Réessayer</button>
          </div>
        )}
        {deleteError && (
          <div className="flex items-center gap-2 bg-red-50 border border-red-100 rounded-xl px-3 py-2 mb-4">
            <AlertCircle size={16} className="text-red-500 flex-shrink-0" />
            <p className="text-sm text-red-600">{deleteError}</p>
          </div>
        )}
        {loading ? (
          <div className="space-y-3">
            {[1, 2].map(i => (
              <div key={i} className="h-20 bg-white rounded-2xl animate-pulse" />
            ))}
          </div>
        ) : methods.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-48 text-center">
            <div className="w-16 h-16 bg-orange-100 rounded-2xl flex items-center justify-center mb-4">
              <Smartphone size={28} className="text-orange-500" />
            </div>
            <p className="font-semibold text-gray-700 mb-1">Aucun compte enregistré</p>
            <p className="text-sm text-gray-400">Ajoutez votre TMoney, Flooz, Orange Money…</p>
            <button
              onClick={() => setShowAdd(true)}
              className="mt-4 px-6 py-2.5 bg-purple-50 text-[#6D28D9] rounded-xl font-semibold text-sm"
            >
              Ajouter un compte
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            {methods.map(m => {
              const color = providerColor[m.provider] ?? '#6D28D9';
              const countryInfo = getCountry(m.country_code);
              return (
                <div key={m.id} className="bg-white rounded-2xl p-4 shadow-sm flex items-center gap-4">
                  <div className="w-12 h-12 rounded-xl flex items-center justify-center" style={{ background: `${color}20` }}>
                    <Smartphone size={22} style={{ color }} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <p className="font-bold text-gray-900 text-sm truncate">{m.nickname}</p>
                      {m.is_default && (
                        <Star size={12} className="text-yellow-400 fill-yellow-400 shrink-0" />
                      )}
                    </div>
                    <p className="text-xs text-gray-500">{m.phone_number}</p>
                    <p className="text-xs text-gray-400">{countryInfo?.flag} {m.provider}</p>
                  </div>
                  <button
                    onClick={() => handleDelete(m.id)}
                    disabled={deleting === m.id}
                    className="p-2 text-red-400 hover:bg-red-50 rounded-xl transition-colors"
                  >
                    <Trash2 size={18} />
                  </button>
                </div>
              );
            })}
          </div>
        )}

      </div>
    </div>
  );
}
