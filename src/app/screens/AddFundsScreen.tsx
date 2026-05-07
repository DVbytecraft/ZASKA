import { useEffect, useState } from 'react';
import { ArrowLeft, CreditCard, Loader2 } from 'lucide-react';
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

const PRESET_XOF = ['5000', '10000', '25000'];
const PRESET_USD = ['5', '20', '50'];

export function AddFundsScreen({ onBack, onSuccess }: AddFundsScreenProps) {
  const [amount, setAmount] = useState('');
  const [balance, setBalance] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const currency = apiClient.getCurrency() ?? 'XOF';
  const presets = currency === 'USD' ? PRESET_USD : PRESET_XOF;

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
        // Stripe sandbox — redirect to hosted checkout page
        window.location.href = result.checkout_url;
        return;
      }

      // Mock / dev direct credit
      onSuccess();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erreur lors du paiement.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="h-full flex flex-col bg-white">
      <div className="px-6 pt-8 pb-4 border-b border-gray-200">
        <div className="flex items-center justify-between">
          <button
            onClick={onBack}
            className="p-2 -ml-2 hover:bg-gray-100 rounded-full transition-colors"
          >
            <ArrowLeft size={24} className="text-gray-700" />
          </button>
          <h2 className="text-xl font-semibold text-gray-900">Recharger</h2>
          <div className="w-10" />
        </div>
      </div>

      <div className="flex-1 overflow-auto p-6 space-y-6">
        {/* Current balance */}
        <div className="bg-purple-50 rounded-2xl p-6 text-center">
          <p className="text-sm text-gray-600 mb-1">Solde actuel</p>
          <h3 className="text-3xl font-bold text-gray-900">
            {balance === null
              ? '—'
              : `${parseFloat(balance).toLocaleString()} ${currency}`}
          </h3>
        </div>

        {/* Amount input */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Montant ({currency})
          </label>
          <div className="relative">
            <input
              type="number"
              min="1"
              step="1"
              value={amount}
              onChange={(e) => { setAmount(e.target.value); setError(null); }}
              className="w-full px-4 py-3 border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-[#6D28D9] focus:border-transparent text-lg font-semibold"
              placeholder="0"
            />
            <span className="absolute right-4 top-1/2 -translate-y-1/2 text-gray-500 font-medium text-sm">
              {currency}
            </span>
          </div>

          {/* Quick-select presets */}
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
                {parseInt(p).toLocaleString()}
              </button>
            ))}
          </div>
        </div>

        {/* Payment note */}
        <div className="flex items-start gap-3 bg-blue-50 border border-blue-100 rounded-xl p-4">
          <CreditCard size={18} className="text-blue-600 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-blue-900">Paiement sécurisé par Stripe</p>
            <p className="text-xs text-blue-700 mt-0.5">
              Carte test : 4242 4242 4242 4242 · exp : toute date future · CVC : tout
            </p>
          </div>
        </div>

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
              <Loader2 size={16} className="animate-spin" /> Redirection vers Stripe...
            </span>
          ) : (
            `Payer ${amount ? `${parseFloat(amount).toLocaleString()} ${currency}` : ''} par carte`
          )}
        </Button>
      </div>
    </div>
  );
}
