import { Button } from '../components/Button';
import { AlertCircle } from 'lucide-react';

interface ErrorScreenProps {
  title?: string;
  message?: string;
  onRetry?: () => void;
  onBack?: () => void;
}

export function ErrorScreen({
  title = 'Something went wrong',
  message = 'Please try again',
  onRetry,
  onBack
}: ErrorScreenProps) {
  return (
    <div className="h-full flex flex-col items-center justify-center px-8 bg-white">
      <div className="w-20 h-20 rounded-full bg-red-50 flex items-center justify-center mb-6">
        <AlertCircle size={40} className="text-red-600" />
      </div>

      <h3 className="text-xl font-bold text-gray-900 mb-8 text-center">{title}</h3>

      <div className="space-y-3 w-full max-w-xs">
        {onRetry && <Button fullWidth onClick={onRetry}>Try again</Button>}
        {onBack && (
          <button onClick={onBack} className="w-full py-3 text-gray-600 font-medium hover:text-gray-900 transition-colors">
            Go back
          </button>
        )}
      </div>
    </div>
  );
}
