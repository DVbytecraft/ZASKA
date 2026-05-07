import { useEffect, useState } from 'react';
import { ArrowLeft, User, DollarSign } from 'lucide-react';
import { Button } from '../components/Button';
import { walletService, apiClient } from '@zaska/shared-services';

interface SendMoneyScreenProps {
  onBack: () => void;
  onSuccess: () => void;
}

export function SendMoneyScreen({ onBack, onSuccess }: SendMoneyScreenProps) {
  const [recipient, setRecipient] = useState('');
  const [amount, setAmount] = useState('');
  const [balance, setBalance] = useState<string | null>(null);
  const currency = apiClient.getCurrency() ?? 'XOF';

  useEffect(() => {
    walletService.getBalance(currency)
      .then((data) => setBalance(data.balance))
      .catch(() => setBalance(null));
  }, [currency]);

  return (
    <div className="h-full flex flex-col bg-white">
      <div className="px-6 pt-8 pb-4 border-b border-gray-200">
        <div className="flex items-center justify-between">
          <button onClick={onBack} className="p-2 -ml-2 hover:bg-gray-100 rounded-full transition-colors">
            <ArrowLeft size={24} className="text-gray-700" />
          </button>
          <h2 className="text-xl font-semibold text-gray-900">Send Money</h2>
          <div className="w-10" />
        </div>
      </div>

      <div className="flex-1 overflow-auto p-6">
        <div className="bg-purple-50 rounded-2xl p-6 mb-6 text-center">
          <p className="text-sm text-gray-600 mb-1">Available Balance</p>
          <h3 className="text-3xl font-bold text-gray-900">
            {balance === null
              ? '—'
              : `${parseFloat(balance).toLocaleString()} ${currency}`}
          </h3>
        </div>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Recipient Phone Number</label>
            <div className="relative">
              <User size={20} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                type="tel"
                value={recipient}
                onChange={(e) => setRecipient(e.target.value)}
                className="w-full pl-11 pr-4 py-3 border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-[#6D28D9] focus:border-transparent"
                placeholder="+228 90 000 000"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Amount</label>
            <div className="relative">
              <DollarSign size={20} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                type="number"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                className="w-full pl-11 pr-20 py-3 border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-[#6D28D9] focus:border-transparent"
                placeholder="0"
              />
              <span className="absolute right-4 top-1/2 -translate-y-1/2 text-gray-600 font-medium">{currency}</span>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-2 pt-2">
            {['5000', '10000', '20000'].map((preset) => (
              <button
                key={preset}
                onClick={() => setAmount(preset)}
                className="py-2 px-3 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
              >
                {parseInt(preset).toLocaleString()}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="p-6 border-t border-gray-200">
        <Button fullWidth onClick={onSuccess} disabled={!recipient || !amount}>
          Continue
        </Button>
      </div>
    </div>
  );
}
