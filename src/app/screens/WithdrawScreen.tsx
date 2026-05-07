import { useState, useEffect } from 'react';
import { ArrowLeft, CheckCircle, AlertCircle, Smartphone, Plus } from 'lucide-react';
import { apiClient, walletService } from '@zaska/shared-services';
import type { SavedPaymentMethod } from '@zaska/shared-services';
import { getOperators, getCountry, type MobileMoneyOperator } from '../config/countries';

interface WithdrawScreenProps {
  onBack: () => void;
  onSuccess: () => void;
}

type Step = 'method' | 'amount' | 'confirm' | 'success' | 'error';

const PRESETS_XOF = ['5 000', '10 000', '25 000', '50 000'];
const PRESETS_OTHER = ['500', '1 000', '2 500', '5 000'];
const FEE_RATE = 0.02;

export function WithdrawScreen({ onBack, onSuccess }: WithdrawScreenProps) {
  const countryCode = apiClient.getCountryCode() ?? 'TG';
  const currency = apiClient.getCurrency() ?? 'XOF';
  const country = getCountry(countryCode);
  const operators = getOperators(countryCode);

  const [step, setStep] = useState<Step>('method');
  const [savedMethods, setSavedMethods] = useState<SavedPaymentMethod[]>([]);
  const [selectedOperator, setSelectedOperator] = useState<MobileMoneyOperator | null>(operators[0] ?? null);
  const [selectedSaved, setSelectedSaved] = useState<SavedPaymentMethod | null>(null);
  const [customPhone, setCustomPhone] = useState('');
  const [useCustomPhone, setUseCustomPhone] = useState(false);
  const [amount, setAmount] = useState('');
  const [balance, setBalance] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [txRef, setTxRef] = useState('');

  useEffect(() => {
    walletService.getBalance(currency)
      .then(b => setBalance(b.balance))
      .catch(() => null);

    walletService.listPaymentMethods()
      .then(methods => {
        setSavedMethods(methods.filter(m => m.country_code === countryCode));
        const def = methods.find(m => m.is_default && m.country_code === countryCode);
        if (def) setSelectedSaved(def);
      })
      .catch(() => null);
  }, [currency, countryCode]);

  const amountNum = parseFloat(amount.replace(/\s/g, '')) || 0;
  const fee = Math.round(amountNum * FEE_RATE);
  const netAmount = amountNum - fee;

  const targetPhone = useCustomPhone
    ? customPhone
    : (selectedSaved?.phone_number ?? customPhone);

  const targetProvider = useCustomPhone
    ? (selectedOperator?.id ?? '')
    : (selectedSaved?.provider ?? selectedOperator?.id ?? '');

  const phoneValid = /^\+[1-9]\d{6,14}$/.test(targetPhone);
  const canProceed = amountNum > 0 && phoneValid && (selectedOperator !== null || selectedSaved !== null);

  const handleWithdraw = async () => {
    setLoading(true);
    setErrorMsg('');
    try {
      const result = await walletService.withdraw({
        amount: String(amountNum),
        currency,
        provider: targetProvider,
        phone_number: targetPhone,
        country_code: countryCode,
      });
      setTxRef(result.reference);
      setStep('success');
    } catch (e) {
      setErrorMsg(e instanceof Error ? e.message : 'Retrait échoué');
      setStep('error');
    } finally {
      setLoading(false);
    }
  };

  const formatAmount = (v: string) =>
    v.replace(/\D/g, '').replace(/\B(?=(\d{3})+(?!\d))/g, ' ');

  const presets = currency === 'XOF' || currency === 'XAF' ? PRESETS_XOF : PRESETS_OTHER;

  // ── Succès ──────────────────────────────────────────────────────────────────
  if (step === 'success') {
    return (
      <div className="h-full flex flex-col bg-white items-center justify-center px-8 text-center">
        <div className="w-20 h-20 bg-green-100 rounded-full flex items-center justify-center mb-6">
          <CheckCircle size={40} className="text-green-500" />
        </div>
        <h2 className="text-2xl font-bold text-gray-900 mb-2">Retrait initié !</h2>
        <p className="text-gray-500 text-sm mb-1">
          {amountNum.toLocaleString()} {currency} → {targetProvider.toUpperCase()}
        </p>
        <p className="text-gray-500 text-sm mb-1">{targetPhone}</p>
        <p className="text-xs text-gray-400 mt-2">Réf: {txRef}</p>
        <p className="text-xs text-gray-400 mt-1">Traitement sous 24h</p>
        <button
          onClick={onSuccess}
          className="mt-8 w-full py-4 rounded-xl font-bold text-white text-base"
          style={{ background: 'linear-gradient(135deg, #6D28D9 0%, #7C3AED 100%)' }}
        >
          Retour au wallet
        </button>
      </div>
    );
  }

  // ── Erreur ──────────────────────────────────────────────────────────────────
  if (step === 'error') {
    return (
      <div className="h-full flex flex-col bg-white items-center justify-center px-8 text-center">
        <div className="w-20 h-20 bg-red-100 rounded-full flex items-center justify-center mb-6">
          <AlertCircle size={40} className="text-red-500" />
        </div>
        <h2 className="text-2xl font-bold text-gray-900 mb-2">Retrait échoué</h2>
        <p className="text-sm text-red-600 bg-red-50 rounded-xl px-4 py-3 mt-2">{errorMsg}</p>
        <button
          onClick={() => setStep('method')}
          className="mt-8 w-full py-4 rounded-xl font-bold text-white text-base"
          style={{ background: 'linear-gradient(135deg, #6D28D9 0%, #7C3AED 100%)' }}
        >
          Réessayer
        </button>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col bg-white" style={{ fontFamily: "'Poppins', sans-serif" }}>
      {/* Header */}
      <div className="px-6 pt-8 pb-4 border-b border-gray-100">
        <div className="flex items-center gap-3">
          <button onClick={step === 'method' ? onBack : () => setStep('method')} className="p-2 -ml-2 hover:bg-gray-100 rounded-full transition-colors">
            <ArrowLeft size={24} className="text-gray-700" />
          </button>
          <div>
            <h2 className="text-xl font-bold text-gray-900">Retirer des fonds</h2>
            <p className="text-xs text-gray-400">{country?.flag} {country?.name} · {currency}</p>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-auto">
        {/* Solde */}
        <div className="mx-6 mt-5 rounded-2xl p-5 text-center"
          style={{ background: 'linear-gradient(135deg, #6D28D9 0%, #7C3AED 100%)' }}>
          <p className="text-white/70 text-xs mb-1">Solde disponible</p>
          <h3 className="text-3xl font-extrabold text-white">
            {balance !== null
              ? `${parseFloat(balance).toLocaleString()} ${currency}`
              : '— ' + currency}
          </h3>
        </div>

        {step === 'method' && (
          <div className="px-6 mt-5 space-y-5 pb-6">
            {/* Opérateur */}
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
                Opérateur Mobile Money
              </p>
              {operators.length === 0 ? (
                <p className="text-sm text-gray-400">Mobile money non disponible pour {country?.name}.</p>
              ) : (
                <div className="grid grid-cols-2 gap-2">
                  {operators.map(op => (
                    <button
                      key={op.id}
                      onClick={() => { setSelectedOperator(op); setSelectedSaved(null); setUseCustomPhone(true); }}
                      className={`p-4 rounded-xl border-2 transition-all text-left ${
                        selectedOperator?.id === op.id && useCustomPhone
                          ? 'border-[#6D28D9] bg-purple-50'
                          : 'border-gray-200 bg-gray-50'
                      }`}
                    >
                      <div className="flex items-center gap-2 mb-1">
                        <div className="w-3 h-3 rounded-full" style={{ background: op.color }} />
                        <p className="font-semibold text-gray-900 text-sm">{op.name}</p>
                      </div>
                      <p className="text-xs text-gray-400">{country?.dialCode}</p>
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Comptes enregistrés */}
            {savedMethods.length > 0 && (
              <div>
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
                  Comptes enregistrés
                </p>
                <div className="space-y-2">
                  {savedMethods.map(m => (
                    <button
                      key={m.id}
                      onClick={() => { setSelectedSaved(m); setSelectedOperator(null); setUseCustomPhone(false); }}
                      className={`w-full p-4 rounded-xl border-2 transition-all flex items-center gap-3 ${
                        selectedSaved?.id === m.id && !useCustomPhone
                          ? 'border-[#6D28D9] bg-purple-50'
                          : 'border-gray-200 bg-gray-50'
                      }`}
                    >
                      <div className="w-10 h-10 rounded-full bg-orange-100 flex items-center justify-center">
                        <Smartphone size={18} className="text-orange-600" />
                      </div>
                      <div className="flex-1 text-left">
                        <p className="font-semibold text-gray-900 text-sm">{m.nickname}</p>
                        <p className="text-xs text-gray-500">{m.phone_number}</p>
                      </div>
                      {m.is_default && (
                        <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full font-medium">
                          Défaut
                        </span>
                      )}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Nouveau numéro */}
            {(useCustomPhone || savedMethods.length === 0) && selectedOperator && (
              <div>
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
                  Numéro {selectedOperator.name}
                </p>
                <input
                  type="tel"
                  placeholder={`${country?.dialCode}XXXXXXXX`}
                  value={customPhone}
                  onChange={e => setCustomPhone(e.target.value)}
                  className={`w-full px-4 py-3.5 rounded-xl border-2 bg-gray-50 focus:bg-white focus:outline-none transition-all text-gray-900 font-medium placeholder:text-gray-400 ${
                    customPhone && !phoneValid ? 'border-red-300' : 'border-gray-100 focus:border-[#6D28D9]'
                  }`}
                />
                {customPhone && !phoneValid && (
                  <p className="text-xs text-red-500 mt-1">Format international requis (ex: {country?.dialCode}90123456)</p>
                )}
              </div>
            )}

            {savedMethods.length > 0 && !useCustomPhone && (
              <button
                onClick={() => { setUseCustomPhone(true); setSelectedSaved(null); }}
                className="w-full flex items-center gap-2 py-3 text-[#6D28D9] font-semibold text-sm"
              >
                <Plus size={16} />
                Utiliser un autre numéro
              </button>
            )}

            <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
              <p className="text-xs text-amber-800 font-medium">
                Frais de retrait : {(FEE_RATE * 100).toFixed(0)}% — Traitement sous 24h
              </p>
            </div>
          </div>
        )}

        {step === 'amount' && (
          <div className="px-6 mt-5 space-y-5 pb-6">
            <div className="flex items-center gap-3 p-4 bg-gray-50 rounded-xl">
              <div className="w-3 h-3 rounded-full" style={{ background: selectedOperator?.color ?? '#6D28D9' }} />
              <div>
                <p className="font-semibold text-gray-900 text-sm">
                  {selectedSaved?.nickname ?? selectedOperator?.name}
                </p>
                <p className="text-xs text-gray-500">{targetPhone}</p>
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
                Montant ({currency})
              </label>
              <input
                type="text"
                inputMode="numeric"
                value={amount}
                onChange={e => setAmount(formatAmount(e.target.value))}
                placeholder="0"
                className="w-full px-5 py-4 rounded-xl border-2 border-gray-100 bg-gray-50 focus:bg-white focus:border-[#6D28D9] focus:outline-none text-2xl font-bold text-gray-900 text-center"
              />
            </div>

            <div className="grid grid-cols-4 gap-2">
              {presets.map(p => (
                <button
                  key={p}
                  onClick={() => setAmount(p)}
                  className="py-2 px-1 border-2 border-gray-200 rounded-xl text-xs font-semibold text-gray-700 hover:border-[#6D28D9] hover:text-[#6D28D9] transition-colors"
                >
                  {p}
                </button>
              ))}
            </div>

            {amountNum > 0 && (
              <div className="bg-gray-50 rounded-xl p-4 space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-gray-500">Montant brut</span>
                  <span className="font-medium">{amountNum.toLocaleString()} {currency}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-500">Frais ({(FEE_RATE * 100).toFixed(0)}%)</span>
                  <span className="font-medium text-red-500">- {fee.toLocaleString()} {currency}</span>
                </div>
                <div className="border-t border-gray-200 pt-2 flex justify-between">
                  <span className="font-bold text-gray-900">Vous recevrez</span>
                  <span className="font-bold text-[#6D28D9]">{netAmount.toLocaleString()} {currency}</span>
                </div>
              </div>
            )}
          </div>
        )}

        {step === 'confirm' && (
          <div className="px-6 mt-5 space-y-4 pb-6">
            <div className="bg-purple-50 border border-purple-200 rounded-2xl p-5 space-y-3">
              <h3 className="font-bold text-gray-900">Récapitulatif du retrait</h3>
              {[
                { label: 'Opérateur', value: selectedSaved?.nickname ?? selectedOperator?.name ?? '' },
                { label: 'Numéro', value: targetPhone },
                { label: 'Montant envoyé', value: `${amountNum.toLocaleString()} ${currency}` },
                { label: 'Frais', value: `${fee.toLocaleString()} ${currency}` },
                { label: 'Montant reçu', value: `${netAmount.toLocaleString()} ${currency}` },
              ].map(({ label, value }) => (
                <div key={label} className="flex justify-between text-sm">
                  <span className="text-gray-500">{label}</span>
                  <span className="font-semibold text-gray-900">{value}</span>
                </div>
              ))}
            </div>
            <p className="text-xs text-gray-400 text-center">
              En confirmant, vous acceptez les conditions de retrait ZASKA.
            </p>
          </div>
        )}
      </div>

      {/* CTA bas */}
      <div className="px-6 pb-6 pt-3 border-t border-gray-100">
        {step === 'method' && (
          <button
            onClick={() => setStep('amount')}
            disabled={!phoneValid || (!selectedOperator && !selectedSaved)}
            className="w-full py-4 rounded-xl font-bold text-base text-white transition-all"
            style={{
              background: (phoneValid && (selectedOperator || selectedSaved))
                ? 'linear-gradient(135deg, #6D28D9 0%, #7C3AED 100%)'
                : '#D1D5DB',
            }}
          >
            Continuer
          </button>
        )}
        {step === 'amount' && (
          <button
            onClick={() => setStep('confirm')}
            disabled={amountNum <= 0}
            className="w-full py-4 rounded-xl font-bold text-base text-white transition-all"
            style={{
              background: amountNum > 0 ? 'linear-gradient(135deg, #6D28D9 0%, #7C3AED 100%)' : '#D1D5DB',
            }}
          >
            Voir le récapitulatif
          </button>
        )}
        {step === 'confirm' && (
          <button
            onClick={handleWithdraw}
            disabled={loading}
            className="w-full py-4 rounded-xl font-bold text-base text-white transition-all"
            style={{ background: 'linear-gradient(135deg, #6D28D9 0%, #7C3AED 100%)' }}
          >
            {loading ? 'Traitement...' : `Confirmer le retrait de ${amountNum.toLocaleString()} ${currency}`}
          </button>
        )}
      </div>
    </div>
  );
}
