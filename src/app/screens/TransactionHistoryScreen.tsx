import { useEffect, useState } from 'react';
import { ArrowLeft, ArrowUpRight, ArrowDownLeft, RefreshCw, AlertCircle } from 'lucide-react';
import { Card } from '../components/Card';
import { walletService } from '@zaska/shared-services';
import type { Transaction } from '@zaska/shared-services';
import { apiClient } from '@zaska/shared-services';

interface TransactionHistoryScreenProps {
  onBack: () => void;
}

function formatAmount(tx: Transaction): string {
  const sign = tx.type === 'credit' ? '+' : '-';
  return `${sign}${parseFloat(tx.amount).toLocaleString()} ${tx.currency ?? ''}`.trim();
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, {
      year: 'numeric', month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

function txLabel(tx: Transaction): string {
  if (tx.reference?.startsWith('withdraw:')) return 'Withdrawal';
  if (tx.reference?.startsWith('rollback:')) return 'Refund';
  if (tx.reference?.startsWith('escrow:') || tx.reference?.startsWith('release:')) return 'Task Payment';
  if (tx.provider === 'stripe' || tx.provider === 'fedapay' || tx.provider === 'flutterwave') return 'Wallet Top-up';
  if (tx.type === 'credit') return 'Incoming Transfer';
  return 'Outgoing Transfer';
}

export function TransactionHistoryScreen({ onBack }: TransactionHistoryScreenProps) {
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const currency = apiClient.getCurrency() ?? 'XOF';

  const load = () => {
    setLoading(true);
    setError(null);
    walletService.getTransactions(currency)
      .then(setTransactions)
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load transactions'))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, [currency]);

  return (
    <div className="h-full flex flex-col bg-gray-50">
      <div className="px-6 pt-8 pb-4 bg-white border-b border-gray-200">
        <div className="flex items-center gap-3">
          <button onClick={onBack} className="p-2 -ml-2 hover:bg-gray-100 rounded-full transition-colors" aria-label="Go back">
            <ArrowLeft size={24} className="text-gray-700" />
          </button>
          <h2 className="text-2xl font-bold text-gray-900">Transaction History</h2>
        </div>
      </div>

      <div className="flex-1 overflow-auto p-6">
        {loading ? (
          <div className="space-y-3">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-20 bg-gray-200 rounded-2xl animate-pulse" />
            ))}
          </div>
        ) : error ? (
          <div className="flex flex-col items-center justify-center h-48 gap-3">
            <AlertCircle size={40} className="text-red-400" />
            <p className="text-sm text-red-600 text-center">{error}</p>
            <button
              onClick={load}
              className="flex items-center gap-2 text-sm font-medium text-[#6D28D9] hover:underline"
            >
              <RefreshCw size={16} /> Retry
            </button>
          </div>
        ) : transactions.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-48 text-gray-400">
            <ArrowDownLeft size={40} className="mb-3 text-gray-200" />
            <p className="text-sm">No transactions yet.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {transactions.map((tx) => {
              const isCredit = tx.type === 'credit';
              return (
                <Card key={tx.id} className="hover:shadow-md transition-all">
                  <div className="flex items-start gap-4">
                    <div className={`w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0 ${isCredit ? 'bg-green-50' : 'bg-red-50'}`}>
                      {isCredit
                        ? <ArrowDownLeft size={24} className="text-green-600" />
                        : <ArrowUpRight size={24} className="text-red-600" />}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-start justify-between gap-2 mb-1">
                        <div>
                          <h4 className="font-semibold text-gray-900">{txLabel(tx)}</h4>
                          <p className="text-xs text-gray-500 capitalize">{tx.provider}</p>
                        </div>
                        <span className={`font-bold whitespace-nowrap ${isCredit ? 'text-green-600' : 'text-gray-900'}`}>
                          {formatAmount(tx)}
                        </span>
                      </div>
                      <div className="flex items-center justify-between">
                        <p className="text-xs text-gray-500">{formatDate(tx.created_at)}</p>
                        <span className={`text-xs px-2 py-0.5 rounded-full ${
                          tx.status === 'completed' ? 'bg-green-100 text-green-700' :
                          tx.status === 'failed' ? 'bg-red-100 text-red-700' :
                          'bg-amber-100 text-amber-700'
                        }`}>{tx.status}</span>
                      </div>
                    </div>
                  </div>
                </Card>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
