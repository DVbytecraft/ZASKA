import { useEffect, useState } from 'react';
import { ArrowLeft, CreditCard, Loader2, Smartphone, Building2, Check } from 'lucide-react';
import { Button } from '../components/Button';
import { walletService, apiClient } from '@zaska/shared-services';

interface AddFundsScreenProps {
  onBack: () => void;
  onSuccess: () => void;
}

interface DepositResult {
  mode: string;
  checkout_url?: string;
  tx_id?: string;
  amount: string;
  currency: string;
  status?: string;
}

// ── Demo payment method catalogue ─────────────────────────────────────────
interface DemoMethod {
  id: string;
  label: string;
  sub: string;
  icon: React.ReactNode;
}

const GOOGLE_ICON = (
  <svg viewBox="0 0 24 24" className="w-5 h-5" fill="none">
    <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
    <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
    <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z" fill="#FBBC05"/>
    <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
  </svg>
);

const APPLE_ICON = (
  <svg viewBox="0 0 24 24" className="w-5 h-5" fill="currentColor">
    <path d="M18.71 19.5c-.83 1.24-1.71 2.45-3.05 2.47-1.34.03-1.77-.79-3.29-.79-1.53 0-2 .77-3.27.82-1.31.05-2.3-1.32-3.14-2.53C4.25 17 2.94 12.45 4.7 9.39c.87-1.52 2.43-2.48 4.12-2.51 1.28-.02 2.5.87 3.29.87.78 0 2.26-1.07 3.8-.91.65.03 2.47.26 3.64 1.98-.09.06-2.17 1.28-2.15 3.81.03 3.02 2.65 4.03 2.68 4.04-.03.07-.42 1.44-1.38 2.83M13 3.5c.73-.83 1.94-1.46 2.94-1.5.13 1.17-.34 2.35-1.04 3.19-.69.85-1.83 1.51-2.95 1.42-.15-1.15.41-2.35 1.05-3.11z"/>
  </svg>
);

const DEMO_METHODS: DemoMethod[] = [
  {
    id: 'card',
    label: 'Carte bancaire',
    sub: 'Visa / Mastercard / Amex',
    icon: <CreditCard size={20} className="text-[#6D28D9]" />,
  },
  {
    id: 'google_pay',
    label: 'Google Pay',
    sub: 'Compte Google associé',
    icon: <span className="flex items-center">{GOOGLE_ICON}</span>,
  },
  {
    id: 'apple_pay',
    label: 'Apple Pay',
    sub: 'Face ID / Touch ID',
    icon: <span className="text-gray-900">{APPLE_ICON}</span>,
  },
  {
    id: 'bank',
    label: 'Virement bancaire',
    sub: 'IBAN / BIC — Europe & international',
    icon: <Building2 size={20} className="text-blue-600" />,
  },
  {
    id: 'mobile_money',
    label: 'Mobile Money',
    sub: 'Orange Money, Wave, M-Pesa, MTN...',
    icon: <Smartphone size={20} className="text-orange-500" />,
  },
];

const PRESET_EUR = ['10', '50', '200'];
const PRESET_XOF = ['5000', '10000', '25000'];
const PRESET_USD = ['5', '20', '50'];

function getPresets(currency: string): string[] {
  if (currency === 'EUR') return PRESET_EUR;
  if (currency === 'USD') return PRESET_USD;
  return PRESET_XOF;
}

export function AddFundsScreen({ onBack, onSuccess }: AddFundsScreenProps) {
  const [amount, setAmount] = useState('');
  const [balance, setBalance] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedMethod, setSelectedMethod] = useState<string>('card');

  const currency = apiClient.getCurrency() ?? 'XOF';
  const isDemo = apiClient.getIsDemo();
  const presets = getPresets(currency);

  useEffect(() => {
    walletService.getBalance(currency)
      .then((data) => setBalance(data.balance))
      .catch(() => setBalance(null));
  }, [currency]);

  const handleDeposit = async () => {
    const parsed = parseFloat(amount);
    if (!amount || isNaN(parsed) || parsed <= 0) {
      setError('Veuillez entrer un montant valide.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await walletService.deposit({ amount, currency }) as DepositResult;
      if (result.mode === 'stripe_checkout' && result.checkout_url) {
        window.location.href = result.checkout_url;
        return;
      }
      onSuccess();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erreur lors du paiement.');
    } finally {
      setLoading(false);
    }
  };

  const formatBalance = (raw: string) =>
    `${parseFloat(raw).toLocaleString('fr-FR', { minimumFractionDigits: currency === 'EUR' ? 2 : 0 })} ${currency}`;

  return (
    <div className="h-full flex flex-col bg-white">
      {/* Header */}
      <div className="px-6 pt-8 pb-4 border-b border-gray-200">
        <div className="flex items-center justify-between">
          <button onClick={onBack} className="p-2 -ml-2 hover:bg-gray-100 rounded-full transition-colors">
            <ArrowLeft size={24} className="text-gray-700" />
          </button>
          <h2 className="text-xl font-semibold text-gray-900">Recharger</h2>
          <div className="w-10" />
        </div>
      </div>

      <div className="flex-1 overflow-auto p-6 space-y-5">
        {/* Balance */}
        <div className="bg-purple-50 rounded-2xl p-5 text-center">
          <p className="text-sm text-gray-500 mb-1">Solde actuel</p>
          <h3 className="text-3xl font-bold text-gray-900">
            {balance === null ? '—' : formatBalance(balance)}
          </h3>
          {isDemo && (
            <p className="text-xs text-purple-500 mt-1 font-medium">Mode Démo</p>
          )}
        </div>

        {/* Amount */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Montant ({currency})
          </label>
          <div className="relative">
            <input
              type="number"
              min="1"
              step={currency === 'EUR' ? '0.01' : '1'}
              value={amount}
              onChange={(e) => { setAmount(e.target.value); setError(null); }}
              className="w-full px-4 py-3 border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-[#6D28D9] focus:border-transparent text-lg font-semibold"
              placeholder="0"
            />
            <span className="absolute right-4 top-1/2 -translate-y-1/2 text-gray-500 font-medium text-sm">
              {currency}
            </span>
          </div>
          <div className="grid grid-cols-3 gap-2 mt-3">
            {presets.map((p) => (
              <button
                key={p}
                onClick={() => { setAmount(p); setError(null); }}
                className={`py-2 px-3 border rounded-lg text-sm font-medium transition-colors ${
                  amount === p
                    ? 'border-[#6D28D9] bg-[#6D28D9]/5 text-[#6D28D9]'
                    : 'border-gray-300 text-gray-700 hover:bg-gray-50'
                }`}
              >
                {currency === 'EUR'
                  ? `${p} €`
                  : `${parseInt(p).toLocaleString()}`}
              </button>
            ))}
          </div>
        </div>

        {/* Payment method selector — full catalogue in demo, card-only otherwise */}
        {isDemo ? (
          <div>
            <p className="text-sm font-medium text-gray-700 mb-2">Méthode de paiement</p>
            <div className="space-y-2">
              {DEMO_METHODS.map((m) => (
                <button
                  key={m.id}
                  onClick={() => setSelectedMethod(m.id)}
                  className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl border-2 transition-all text-left ${
                    selectedMethod === m.id
                      ? 'border-[#6D28D9] bg-purple-50'
                      : 'border-gray-100 bg-gray-50 hover:border-gray-200'
                  }`}
                >
                  <span className="w-8 flex items-center justify-center">{m.icon}</span>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-gray-900">{m.label}</p>
                    <p className="text-xs text-gray-500 truncate">{m.sub}</p>
                  </div>
                  {selectedMethod === m.id && (
                    <Check size={16} className="text-[#6D28D9] shrink-0" />
                  )}
                </button>
              ))}
            </div>
            <p className="text-xs text-gray-400 mt-2 text-center">
              Mode Démo — aucun débit réel effectué
            </p>
          </div>
        ) : (
          <div className="flex items-start gap-3 bg-blue-50 border border-blue-100 rounded-xl p-4">
            <CreditCard size={18} className="text-blue-600 shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-medium text-blue-900">Paiement sécurisé par Stripe</p>
              <p className="text-xs text-blue-700 mt-0.5">
                Carte test : 4242 4242 4242 4242 · exp : toute date future · CVC : tout
              </p>
            </div>
          </div>
        )}

        {error && (
          <div className="bg-red-50 border border-red-100 rounded-xl p-3">
            <p className="text-sm text-red-600">{error}</p>
          </div>
        )}
      </div>

      <div className="p-6 border-t border-gray-200">
        <Button fullWidth onClick={handleDeposit} disabled={!amount || loading}>
          {loading ? (
            <span className="flex items-center justify-center gap-2">
              <Loader2 size={16} className="animate-spin" />
              {isDemo ? 'Simulation...' : 'Redirection...'}
            </span>
          ) : (
            isDemo
              ? `Simuler ${amount ? `${amount} ${currency}` : ''}`
              : `Payer ${amount ? `${parseFloat(amount).toLocaleString()} ${currency}` : ''} par carte`
          )}
        </Button>
      </div>
    </div>
  );
}
