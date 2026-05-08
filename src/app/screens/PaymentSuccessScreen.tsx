import { Button } from '../components/Button';
import { CheckCircle2, Receipt, ArrowRight } from 'lucide-react';

interface PaymentSuccessScreenProps {
  amount?: string;
  currency?: string;
  description?: string;
  onDone: () => void;
  onViewReceipt?: () => void;
}

export function PaymentSuccessScreen({
  amount,
  currency,
  description,
  onDone,
  onViewReceipt,
}: PaymentSuccessScreenProps) {
  const displayAmount = amount
    ? `${currency ? currency + ' ' : ''}${parseFloat(amount).toFixed(2)}`
    : null;

  return (
    <div className="h-full flex flex-col items-center justify-center px-8 bg-white">
      <div className="w-24 h-24 rounded-full bg-gradient-to-br from-green-400 to-emerald-600 flex items-center justify-center mb-6 shadow-xl">
        <CheckCircle2 size={52} className="text-white" strokeWidth={2.5} />
      </div>

      <h2 className="text-2xl font-bold text-gray-900 mb-2">Paiement libéré !</h2>
      <p className="text-gray-500 text-sm mb-6 text-center">
        {description ?? 'Le séquestre a été libéré au prestataire.'}
      </p>

      {displayAmount && (
        <div className="bg-green-50 border border-green-100 rounded-2xl px-6 py-4 mb-8 text-center">
          <p className="text-xs text-gray-500 mb-1">Montant libéré</p>
          <p className="text-3xl font-bold text-green-700">{displayAmount}</p>
        </div>
      )}

      <div className="w-full max-w-sm space-y-3">
        {onViewReceipt && (
          <Button fullWidth variant="secondary" onClick={onViewReceipt}>
            <span className="flex items-center justify-center gap-2">
              <Receipt size={18} />
              Voir l'historique des transactions
            </span>
          </Button>
        )}
        <Button fullWidth onClick={onDone}>
          <span className="flex items-center justify-center gap-2">
            Terminer
            <ArrowRight size={18} />
          </span>
        </Button>
      </div>
    </div>
  );
}
