import { Button } from '../components/Button';
import { XCircle, CreditCard, AlertCircle } from 'lucide-react';

interface PaymentFailedScreenProps {
  reason?: string;
  onRetry: () => void;
  onChangePaymentMethod: () => void;
  onCancel: () => void;
}

export function PaymentFailedScreen({
  reason = 'Payment could not be processed',
  onRetry,
  onChangePaymentMethod,
  onCancel
}: PaymentFailedScreenProps) {
  return (
    <div className="h-full flex flex-col items-center justify-center px-8 bg-white">
      <div className="w-20 h-20 rounded-full bg-red-50 flex items-center justify-center mb-6">
        <XCircle size={40} className="text-red-600" />
      </div>

      <h3 className="text-xl font-bold text-gray-900 mb-2 text-center">Payment failed</h3>
      <p className="text-gray-600 text-center mb-8 max-w-xs text-sm">{reason}</p>

      <div className="w-full max-w-sm space-y-3">
        <Button fullWidth onClick={onRetry}>
          Try again
        </Button>
        <Button fullWidth variant="outline" onClick={onChangePaymentMethod}>
          <CreditCard size={20} />
          Change payment method
        </Button>
        <button onClick={onCancel} className="w-full py-3 text-gray-600 font-medium hover:text-gray-900 transition-colors">
          Cancel task
        </button>
      </div>

      <div className="mt-6 bg-blue-50 border border-blue-200 rounded-xl p-4 max-w-sm">
        <div className="flex items-start gap-2">
          <AlertCircle size={16} className="text-blue-600 flex-shrink-0 mt-0.5" />
          <p className="text-sm text-blue-900">
            Your payment method was not charged. No funds have been deducted.
          </p>
        </div>
      </div>
    </div>
  );
}
