import { Button } from '../components/Button';
import { WifiOff } from 'lucide-react';

interface NoInternetScreenProps {
  onRetry: () => void;
}

export function NoInternetScreen({ onRetry }: NoInternetScreenProps) {
  return (
    <div className="h-full flex flex-col items-center justify-center px-8 bg-white">
      <div className="w-20 h-20 rounded-full bg-gray-100 flex items-center justify-center mb-6">
        <WifiOff size={40} className="text-gray-400" />
      </div>

      <h3 className="text-xl font-bold text-gray-900 mb-8 text-center">No connection</h3>

      <Button onClick={onRetry}>Try again</Button>
    </div>
  );
}
