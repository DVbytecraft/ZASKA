import { useState, useEffect } from 'react';
import { ArrowLeft, Plus, Smartphone, Trash2, Star, AlertCircle, CreditCard, Building2, Loader, ChevronRight } from 'lucide-react';
import { walletService, apiClient } from '@zaska/shared-services';
import type { SavedPaymentMethod } from '@zaska/shared-services';
import { getOperators, getCountry, SUPPORTED_COUNTRIES, type SupportedCountry, type MobileMoneyOperator } from '../config/countries';

interface PaymentMethodsScreenProps {
  onBack: () => void;
  onVirtualCards?: () => void;
}

type Tab = 'mobile_money' | 'card' | 'bank';

// ── Mobile Money Tab ──────────────────────────────────────────────────────────
function MobileMoneyTab() {
  const countryCode = apiClient.getCountryCode() ?? 'TG';
  const [methods, setMethods] = useState<SavedPaymentMethod[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

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
      .then(data => setMethods(data.filter(m => !m.method_type || m.method_type === 'mobile_money')))
      .catch(err => setLoadError(err instanceof Error ? err.message : 'Erreur de chargement'))
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
      setDeleteError(err instanceof Error ? err.message : 'Échec de la suppression');
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
        method_type: 'mobile_money',
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
    SUPPORTED_COUNTRIES.flatMap(c => getOperators(c.code)).map(op => [op.id, op.color])
  );

  return (
    <>
      {showAdd && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-end">
          <div className="w-full bg-white rounded-t-3xl max-h-[85vh] flex flex-col">
            <div className="px-6 pt-5 pb-3 border-b border-gray-100 flex items-center justify-between">
              <h3 className="text-lg font-bold text-gray-900">Ajouter Mobile Money</h3>
              <button onClick={() => setShowAdd(false)} className="text-gray-400 font-bold text-xl">✕</button>
            </div>
            <div className="overflow-y-auto flex-1 px-6 py-4 space-y-4">
              <div>
                <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Pays</label>
                <div className="grid grid-cols-2 gap-2 max-h-40 overflow-y-auto">
                  {SUPPORTED_COUNTRIES.filter(c => c.mobileMoneyEnabled).map(c => (
                    <button key={c.code} onClick={() => { setAddCountry(c); setAddOperator(null); }}
                      className={`flex items-center gap-2 p-2.5 rounded-xl border-2 text-left ${addCountry.code === c.code ? 'border-[#6D28D9] bg-purple-50' : 'border-gray-100 bg-gray-50'}`}
                    >
                      <span className="text-xl">{c.flag}</span>
                      <div><p className="text-xs font-semibold text-gray-900">{c.name}</p><p className="text-xs text-gray-400">{c.currency}</p></div>
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Opérateur</label>
                <div className="grid grid-cols-2 gap-2">
                  {operators.map(op => (
                    <button key={op.id} onClick={() => setAddOperator(op)}
                      className={`p-3 rounded-xl border-2 flex items-center gap-2 ${addOperator?.id === op.id ? 'border-[#6D28D9] bg-purple-50' : 'border-gray-100 bg-gray-50'}`}
                    >
                      <div className="w-3 h-3 rounded-full" style={{ background: op.color }} />
                      <span className="text-sm font-semibold text-gray-900">{op.name}</span>
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Numéro</label>
                <input type="tel" placeholder={`${addCountry.dialCode}XXXXXXXX`} value={addPhone}
                  onChange={e => setAddPhone(e.target.value)}
                  className={`w-full px-4 py-3.5 rounded-xl border-2 bg-gray-50 focus:bg-white focus:outline-none transition-all text-gray-900 font-medium placeholder:text-gray-400 ${addPhone && !phoneValid ? 'border-red-300' : 'border-gray-100 focus:border-[#6D28D9]'}`}
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Surnom (optionnel)</label>
                <input type="text" placeholder="ex: Mon T-Money principal" value={addNickname}
                  onChange={e => setAddNickname(e.target.value)}
                  className="w-full px-4 py-3.5 rounded-xl border-2 border-gray-100 bg-gray-50 focus:bg-white focus:border-[#6D28D9] focus:outline-none text-gray-900 font-medium placeholder:text-gray-400"
                />
              </div>

              <label className="flex items-center gap-3 cursor-pointer">
                <div onClick={() => setAddDefault(!addDefault)} className={`w-12 h-6 rounded-full transition-colors ${addDefault ? 'bg-[#6D28D9]' : 'bg-gray-300'}`}>
                  <div className={`w-5 h-5 bg-white rounded-full shadow transition-transform mt-0.5 ${addDefault ? 'ml-6' : 'ml-0.5'}`} />
                </div>
                <span className="text-sm font-medium text-gray-700">Définir comme méthode par défaut</span>
              </label>

              {error && <p className="text-sm text-red-600 bg-red-50 rounded-xl px-3 py-2">{error}</p>}
            </div>
            <div className="px-6 pb-6 pt-3 border-t border-gray-100">
              <button onClick={handleAdd} disabled={!addOperator || !phoneValid || saving}
                className="w-full py-4 rounded-xl font-bold text-base text-white transition-all"
                style={{ background: (addOperator && phoneValid && !saving) ? 'linear-gradient(135deg,#6D28D9,#7C3AED)' : '#D1D5DB' }}
              >
                {saving ? 'Enregistrement…' : 'Enregistrer'}
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="p-5 space-y-3">
        {loadError && (
          <div className="flex items-center gap-2 bg-red-50 border border-red-100 rounded-xl px-3 py-2">
            <AlertCircle size={16} className="text-red-500 shrink-0" />
            <p className="text-sm text-red-600 flex-1">{loadError}</p>
            <button onClick={load} className="text-xs font-semibold text-red-600 underline">Réessayer</button>
          </div>
        )}
        {deleteError && (
          <div className="flex items-center gap-2 bg-red-50 border border-red-100 rounded-xl px-3 py-2">
            <AlertCircle size={16} className="text-red-500 shrink-0" />
            <p className="text-sm text-red-600">{deleteError}</p>
          </div>
        )}

        <button onClick={() => setShowAdd(true)}
          className="w-full flex items-center gap-3 p-4 rounded-2xl border-2 border-dashed border-[#6D28D9]/30 hover:border-[#6D28D9] hover:bg-purple-50 transition-all text-[#6D28D9] font-semibold text-sm"
        >
          <Plus size={18} />
          Ajouter un compte Mobile Money
        </button>

        {loading ? (
          [1, 2].map(i => <div key={i} className="h-20 bg-white rounded-2xl animate-pulse" />)
        ) : methods.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-10 text-center">
            <div className="w-14 h-14 bg-orange-100 rounded-2xl flex items-center justify-center mb-3">
              <Smartphone size={24} className="text-orange-500" />
            </div>
            <p className="font-semibold text-gray-700 text-sm mb-1">Aucun compte enregistré</p>
            <p className="text-xs text-gray-400">Ajoutez votre T-Money, Flooz, Orange Money…</p>
          </div>
        ) : (
          methods.map(m => {
            const color = providerColor[m.provider] ?? '#6D28D9';
            const countryInfo = getCountry(m.country_code);
            return (
              <div key={m.id} className="bg-white rounded-2xl p-4 shadow-sm flex items-center gap-4">
                <div className="w-11 h-11 rounded-xl flex items-center justify-center shrink-0" style={{ background: `${color}20` }}>
                  <Smartphone size={20} style={{ color }} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="font-bold text-gray-900 text-sm truncate">{m.nickname || m.provider}</p>
                    {m.is_default && <Star size={12} className="text-yellow-400 fill-yellow-400 shrink-0" />}
                  </div>
                  <p className="text-xs text-gray-500">{m.phone_number}</p>
                  <p className="text-xs text-gray-400">{countryInfo?.flag} {m.provider}</p>
                </div>
                <button onClick={() => handleDelete(m.id)} disabled={deleting === m.id}
                  className="p-2 text-red-400 hover:bg-red-50 rounded-xl transition-colors"
                >
                  {deleting === m.id ? <Loader size={16} className="animate-spin" /> : <Trash2 size={16} />}
                </button>
              </div>
            );
          })
        )}
      </div>
    </>
  );
}

// ── Card Tab ──────────────────────────────────────────────────────────────────
function CardTab({ onVirtualCards }: { onVirtualCards?: () => void }) {
  return (
    <div className="p-5 space-y-4">
      <div className="bg-gradient-to-br from-[#1a1a2e] to-[#0f3460] rounded-3xl p-6 text-white relative overflow-hidden">
        <div className="absolute -top-8 -right-8 w-32 h-32 rounded-full bg-white/5" />
        <div className="absolute -bottom-4 -left-4 w-24 h-24 rounded-full bg-white/5" />
        <div className="relative">
          <div className="flex items-center gap-2 mb-6">
            <CreditCard size={18} className="text-white/70" />
            <span className="text-xs font-semibold text-white/70 uppercase tracking-widest">Zaska Card</span>
          </div>
          <p className="text-white/60 text-sm mb-1">Visa · Mastercard</p>
          <p className="font-bold text-lg mb-4">Carte virtuelle sécurisée</p>
          <p className="text-white/70 text-xs">
            Recevez votre argent directement sur votre carte. Utilisez-la pour des paiements en ligne dans le monde entier.
          </p>
        </div>
      </div>

      <button
        onClick={onVirtualCards}
        className="w-full flex items-center justify-between p-4 bg-white rounded-2xl shadow-sm hover:shadow-md transition-all"
      >
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-purple-50 flex items-center justify-center">
            <CreditCard size={20} className="text-[#6D28D9]" />
          </div>
          <div className="text-left">
            <p className="font-bold text-gray-900 text-sm">Gérer mes cartes virtuelles</p>
            <p className="text-xs text-gray-400">Créer, geler, annuler</p>
          </div>
        </div>
        <ChevronRight size={18} className="text-gray-400" />
      </button>

      <div className="bg-blue-50 border border-blue-100 rounded-2xl p-4">
        <p className="text-xs font-semibold text-blue-800 mb-1">Comment ça fonctionne ?</p>
        <ul className="space-y-1.5 text-xs text-blue-700">
          <li>• Créez une carte Visa ou Mastercard virtuelle</li>
          <li>• Recevez vos paiements Zaska directement dessus</li>
          <li>• Utilisez-la pour tous vos achats en ligne</li>
          <li>• Gérez-la depuis l'application (gel, annulation)</li>
        </ul>
      </div>
    </div>
  );
}

// ── Bank Tab ──────────────────────────────────────────────────────────────────
function BankTab() {
  const [methods, setMethods] = useState<SavedPaymentMethod[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [deleting, setDeleting] = useState<string | null>(null);

  // Form state
  const [bankName, setBankName] = useState('');
  const [accountNumber, setAccountNumber] = useState('');
  const [accountHolder, setAccountHolder] = useState('');
  const [country, setCountry] = useState('');
  const [isDefault, setIsDefault] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const load = () => {
    setLoading(true);
    walletService.listPaymentMethods()
      .then(data => setMethods(data.filter(m => m.method_type === 'bank')))
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const formValid = bankName.trim() && accountNumber.trim() && accountHolder.trim() && country.trim();

  const handleAdd = async () => {
    if (!formValid) return;
    setSaving(true);
    setError('');
    try {
      const m = await walletService.addPaymentMethod({
        method_type: 'bank',
        provider: bankName.trim(),
        phone_number: accountNumber.trim(),
        country_code: country.trim().toUpperCase().slice(0, 4),
        nickname: accountHolder.trim(),
        is_default: isDefault,
      });
      setMethods(prev => isDefault ? [m, ...prev.map(x => ({ ...x, is_default: false }))] : [...prev, m]);
      setShowAdd(false);
      setBankName(''); setAccountNumber(''); setAccountHolder(''); setCountry(''); setIsDefault(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erreur lors de l\'ajout');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    setDeleting(id);
    try {
      await walletService.deletePaymentMethod(id);
      setMethods(prev => prev.filter(m => m.id !== id));
    } catch {
      // silent
    } finally {
      setDeleting(null);
    }
  };

  return (
    <>
      {showAdd && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-end">
          <div className="w-full bg-white rounded-t-3xl max-h-[85vh] flex flex-col">
            <div className="px-6 pt-5 pb-3 border-b border-gray-100 flex items-center justify-between">
              <h3 className="text-lg font-bold text-gray-900">Ajouter un compte bancaire</h3>
              <button onClick={() => setShowAdd(false)} className="text-gray-400 font-bold text-xl">✕</button>
            </div>
            <div className="overflow-y-auto flex-1 px-6 py-4 space-y-4">
              <div>
                <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Nom de la banque</label>
                <input type="text" placeholder="Ex : Ecobank, UBA, Société Générale…" value={bankName}
                  onChange={e => setBankName(e.target.value)}
                  className="w-full px-4 py-3.5 rounded-xl border-2 border-gray-100 bg-gray-50 focus:bg-white focus:border-[#6D28D9] focus:outline-none text-gray-900 font-medium placeholder:text-gray-400"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Numéro de compte / IBAN</label>
                <input type="text" placeholder="Ex : TG53TG0090604310346500400070" value={accountNumber}
                  onChange={e => setAccountNumber(e.target.value)}
                  className="w-full px-4 py-3.5 rounded-xl border-2 border-gray-100 bg-gray-50 focus:bg-white focus:border-[#6D28D9] focus:outline-none text-gray-900 font-mono placeholder:text-gray-400"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Titulaire du compte</label>
                <input type="text" placeholder="Prénom et Nom" value={accountHolder}
                  onChange={e => setAccountHolder(e.target.value)}
                  className="w-full px-4 py-3.5 rounded-xl border-2 border-gray-100 bg-gray-50 focus:bg-white focus:border-[#6D28D9] focus:outline-none text-gray-900 font-medium placeholder:text-gray-400"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Pays</label>
                <input type="text" placeholder="Ex : Togo, Bénin, Côte d'Ivoire…" value={country}
                  onChange={e => setCountry(e.target.value)}
                  className="w-full px-4 py-3.5 rounded-xl border-2 border-gray-100 bg-gray-50 focus:bg-white focus:border-[#6D28D9] focus:outline-none text-gray-900 font-medium placeholder:text-gray-400"
                />
              </div>
              <label className="flex items-center gap-3 cursor-pointer">
                <div onClick={() => setIsDefault(!isDefault)} className={`w-12 h-6 rounded-full transition-colors ${isDefault ? 'bg-[#6D28D9]' : 'bg-gray-300'}`}>
                  <div className={`w-5 h-5 bg-white rounded-full shadow transition-transform mt-0.5 ${isDefault ? 'ml-6' : 'ml-0.5'}`} />
                </div>
                <span className="text-sm font-medium text-gray-700">Compte par défaut</span>
              </label>
              {error && <p className="text-sm text-red-600 bg-red-50 rounded-xl px-3 py-2">{error}</p>}
            </div>
            <div className="px-6 pb-6 pt-3 border-t border-gray-100">
              <button onClick={handleAdd} disabled={!formValid || saving}
                className="w-full py-4 rounded-xl font-bold text-base text-white"
                style={{ background: formValid && !saving ? 'linear-gradient(135deg,#6D28D9,#7C3AED)' : '#D1D5DB' }}
              >
                {saving ? 'Enregistrement…' : 'Enregistrer le compte'}
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="p-5 space-y-3">
        <button onClick={() => setShowAdd(true)}
          className="w-full flex items-center gap-3 p-4 rounded-2xl border-2 border-dashed border-[#6D28D9]/30 hover:border-[#6D28D9] hover:bg-purple-50 transition-all text-[#6D28D9] font-semibold text-sm"
        >
          <Plus size={18} />
          Ajouter un compte bancaire
        </button>

        {loading ? (
          [1].map(i => <div key={i} className="h-20 bg-white rounded-2xl animate-pulse" />)
        ) : methods.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-10 text-center">
            <div className="w-14 h-14 bg-blue-100 rounded-2xl flex items-center justify-center mb-3">
              <Building2 size={24} className="text-blue-500" />
            </div>
            <p className="font-semibold text-gray-700 text-sm mb-1">Aucun compte bancaire</p>
            <p className="text-xs text-gray-400">Ajoutez votre IBAN ou numéro de compte</p>
          </div>
        ) : (
          methods.map(m => (
            <div key={m.id} className="bg-white rounded-2xl p-4 shadow-sm flex items-center gap-4">
              <div className="w-11 h-11 rounded-xl bg-blue-50 flex items-center justify-center shrink-0">
                <Building2 size={20} className="text-blue-600" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <p className="font-bold text-gray-900 text-sm truncate">{m.provider}</p>
                  {m.is_default && <Star size={12} className="text-yellow-400 fill-yellow-400 shrink-0" />}
                </div>
                <p className="text-xs text-gray-500 font-mono truncate">{m.phone_number}</p>
                <p className="text-xs text-gray-400">Titulaire : {m.nickname}</p>
              </div>
              <button onClick={() => handleDelete(m.id)} disabled={deleting === m.id}
                className="p-2 text-red-400 hover:bg-red-50 rounded-xl transition-colors"
              >
                {deleting === m.id ? <Loader size={16} className="animate-spin" /> : <Trash2 size={16} />}
              </button>
            </div>
          ))
        )}
      </div>
    </>
  );
}

// ── Main screen ───────────────────────────────────────────────────────────────
export function PaymentMethodsScreen({ onBack, onVirtualCards }: PaymentMethodsScreenProps) {
  const [activeTab, setActiveTab] = useState<Tab>('mobile_money');
  const countryCode = apiClient.getCountryCode() ?? 'TG';
  const country = getCountry(countryCode);

  const tabs: { id: Tab; label: string; icon: typeof Smartphone }[] = [
    { id: 'mobile_money', label: 'Mobile Money', icon: Smartphone },
    { id: 'card', label: 'Carte', icon: CreditCard },
    { id: 'bank', label: 'Banque', icon: Building2 },
  ];

  return (
    <div className="h-full flex flex-col bg-gray-50" style={{ fontFamily: "'Poppins', sans-serif" }}>
      <div className="px-6 pt-8 pb-4 bg-white border-b border-gray-100">
        <div className="flex items-center gap-3 mb-4">
          <button onClick={onBack} className="p-2 -ml-2 hover:bg-gray-100 rounded-full transition-colors">
            <ArrowLeft size={24} className="text-gray-700" />
          </button>
          <div>
            <h2 className="text-xl font-bold text-gray-900">Moyens de paiement</h2>
            <p className="text-xs text-gray-400">{country?.flag} {country?.name}</p>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 bg-gray-100 rounded-2xl p-1">
          {tabs.map(tab => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex-1 flex items-center justify-center gap-1.5 py-2 px-2 rounded-xl text-xs font-semibold transition-all ${
                  activeTab === tab.id
                    ? 'bg-white text-[#6D28D9] shadow-sm'
                    : 'text-gray-500'
                }`}
              >
                <Icon size={14} />
                {tab.label}
              </button>
            );
          })}
        </div>
      </div>

      <div className="flex-1 overflow-auto">
        {activeTab === 'mobile_money' && <MobileMoneyTab />}
        {activeTab === 'card' && <CardTab onVirtualCards={onVirtualCards} />}
        {activeTab === 'bank' && <BankTab />}
      </div>
    </div>
  );
}
