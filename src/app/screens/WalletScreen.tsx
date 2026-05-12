import { useCallback, useEffect, useRef, useState } from 'react';
import { Button } from '../components/Button';
import { Card } from '../components/Card';
import { walletService } from '@zaska/shared-services';
import type { Transaction, WalletBalance } from '@zaska/shared-services';
import { Send, Download, CreditCard, TrendingUp, TrendingDown } from 'lucide-react';
import { formatCurrency } from '../../services/fxService';

interface WalletScreenProps {
  currency?: string;
  onSendMoney?: () => void;
  onWithdraw?: () => void;
  onAddFunds?: () => void;
  onTransactionHistory?: () => void;
}

function formatDate(iso: string) {
  try {
    return new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }).format(new Date(iso));
  } catch {
    return iso;
  }
}

export function WalletScreen({
  currency = 'USD',
  onSendMoney,
  onWithdraw,
  onAddFunds,
  onTransactionHistory,
}: WalletScreenProps = {}) {
  const [wallet, setWallet] = useState<WalletBalance | null>(null);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const cancelledRef = useRef(false);

  const load = useCallback(async () => {
    cancelledRef.current = false;
    setLoading(true);
    setError(null);
    try {
      const [bal, txs] = await Promise.all([
        walletService.getBalance(currency),
        walletService.getTransactions(currency),
      ]);
      if (!cancelledRef.current) { setWallet(bal); setTransactions(txs); }
    } catch (err) {
      const msg = err instanceof Error ? err.message : '';
      if (msg.includes('failed: 404')) {
        try {
          await walletService.createWallet(currency);
          const [bal, txs] = await Promise.all([
            walletService.getBalance(currency),
            walletService.getTransactions(currency),
          ]);
          if (!cancelledRef.current) { setWallet(bal); setTransactions(txs); }
        } catch (createErr) {
          if (!cancelledRef.current) setError(createErr instanceof Error ? createErr.message : 'Impossible d\'initialiser le portefeuille');
        }
      } else {
        if (!cancelledRef.current) setError(msg || 'Impossible de charger le portefeuille');
      }
    } finally {
      if (!cancelledRef.current) setLoading(false);
    }
  }, [currency]);

  useEffect(() => {
    cancelledRef.current = false;
    void load();
    return () => { cancelledRef.current = true; };
  }, [load]);

  // Refresh on tab visibility (mobile foreground recovery)
  useEffect(() => {
    const onVisibility = () => {
      if (document.visibilityState === 'visible') void load();
    };
    document.addEventListener('visibilitychange', onVisibility);
    return () => document.removeEventListener('visibilitychange', onVisibility);
  }, [load]);

  // Refresh on network recovery
  useEffect(() => {
    window.addEventListener('online', load);
    return () => window.removeEventListener('online', load);
  }, [load]);

  const balanceDisplay = wallet
    ? formatCurrency(parseFloat(wallet.balance), wallet.currency)
    : loading
    ? '—'
    : 'N/A';

  const recentTransactions = transactions.slice(0, 10);

  return (
    <div className="h-full overflow-auto pb-24 bg-gray-50">
      <div className="px-6 pt-8 pb-6 bg-gradient-to-br from-[#6D28D9] to-[#5B21B6]">
        <p className="text-white/70 text-sm font-medium mb-1">Solde disponible</p>
        <h1 className="text-5xl font-bold text-white mb-8 tracking-tight">
          {loading ? (
            <span className="inline-block w-40 h-10 bg-white/20 rounded-xl animate-pulse" />
          ) : (
            balanceDisplay
          )}
        </h1>

        <div className="grid grid-cols-3 gap-2.5">
          <button onClick={onSendMoney} className="bg-white/15 hover:bg-white/25 backdrop-blur-sm rounded-2xl p-4 flex flex-col items-center gap-2 transition-all border border-white/10 active:scale-95">
            <div className="w-11 h-11 bg-white/20 rounded-xl flex items-center justify-center">
              <Send size={20} className="text-white" strokeWidth={2.5} />
            </div>
            <span className="text-xs font-semibold text-white">Envoyer</span>
          </button>
          <button onClick={onWithdraw} className="bg-white/15 hover:bg-white/25 backdrop-blur-sm rounded-2xl p-4 flex flex-col items-center gap-2 transition-all border border-white/10 active:scale-95">
            <div className="w-11 h-11 bg-white/20 rounded-xl flex items-center justify-center">
              <Download size={20} className="text-white" strokeWidth={2.5} />
            </div>
            <span className="text-xs font-semibold text-white">Retirer</span>
          </button>
          <button onClick={onAddFunds} className="bg-white/15 hover:bg-white/25 backdrop-blur-sm rounded-2xl p-4 flex flex-col items-center gap-2 transition-all border border-white/10 active:scale-95">
            <div className="w-11 h-11 bg-white/20 rounded-xl flex items-center justify-center">
              <CreditCard size={20} className="text-white" strokeWidth={2.5} />
            </div>
            <span className="text-xs font-semibold text-white">Recharger</span>
          </button>
        </div>
      </div>

      <div className="px-6 py-4">
        <div className="flex items-center justify-between mb-3 px-1">
          <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Transactions récentes</h3>
          {onTransactionHistory && (
            <button onClick={onTransactionHistory} className="text-xs font-semibold text-[#6D28D9] hover:text-[#5B21B6]">
              Voir tout
            </button>
          )}
        </div>

        {loading && (
          <div className="space-y-2">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-16 bg-gray-200 rounded-2xl animate-pulse" />
            ))}
          </div>
        )}

        {error && !loading && (
          <div className="bg-red-50 border border-red-100 rounded-2xl p-4 text-center">
            <p className="text-sm text-red-600">{error}</p>
          </div>
        )}

        {!loading && !error && recentTransactions.length === 0 && (
          <div className="bg-gray-100 rounded-2xl p-8 text-center">
            <p className="text-sm text-gray-500">Aucune transaction pour l'instant.</p>
          </div>
        )}

        {!loading && !error && (
          <div className="space-y-2">
            {recentTransactions.map((tx) => (
              <Card key={tx.id} className="hover:shadow-lg transition-all">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${
                      tx.type === 'credit' ? 'bg-green-50' : 'bg-gray-50'
                    }`}>
                      {tx.type === 'credit' ? (
                        <TrendingUp size={18} className="text-green-600" strokeWidth={2.5} />
                      ) : (
                        <TrendingDown size={18} className="text-gray-600" strokeWidth={2.5} />
                      )}
                    </div>
                    <div>
                      <p className="font-medium text-gray-900 capitalize">
                        {tx.type === 'credit' ? 'Reçu via' : 'Envoyé via'} {tx.provider}
                      </p>
                      <p className="text-xs text-gray-500">{formatDate(tx.created_at)}</p>
                    </div>
                  </div>
                  <span className={`text-base font-semibold ${
                    tx.type === 'credit' ? 'text-green-600' : 'text-gray-900'
                  }`}>
                    {tx.type === 'credit' ? '+' : '-'}{parseFloat(tx.amount).toFixed(2)}
                  </span>
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
