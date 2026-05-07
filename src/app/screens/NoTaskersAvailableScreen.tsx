import { Button } from '../components/Button';
import { Users, MapPin, RefreshCw } from 'lucide-react';

interface NoTaskersAvailableScreenProps {
  onTryAgain: () => void;
  onExpandSearch: () => void;
  onBackHome: () => void;
}

export function NoTaskersAvailableScreen({
  onTryAgain,
  onExpandSearch,
  onBackHome
}: NoTaskersAvailableScreenProps) {
  return (
    <div className="h-full flex flex-col items-center justify-center px-8 bg-white">
      <div className="w-20 h-20 rounded-full bg-gray-100 flex items-center justify-center mb-6">
        <Users size={40} className="text-gray-400" />
      </div>

      <h3 className="text-xl font-bold text-gray-900 mb-2 text-center">No taskers available</h3>
      <p className="text-gray-600 text-center mb-8 max-w-xs text-sm">
        No taskers are available in your area right now
      </p>

      <div className="w-full max-w-sm space-y-3">
        <Button fullWidth onClick={onTryAgain}>
          <RefreshCw size={20} />
          Try again
        </Button>
        <Button fullWidth variant="outline" onClick={onExpandSearch}>
          <MapPin size={20} />
          Expand search area
        </Button>
        <button onClick={onBackHome} className="w-full py-3 text-gray-600 font-medium hover:text-gray-900 transition-colors">
          Back to home
        </button>
      </div>

      <div className="mt-6 bg-blue-50 border border-blue-200 rounded-xl p-4 max-w-sm">
        <p className="text-sm text-blue-900 text-center">
          Try posting in <span className="font-semibold">Choose mode</span> to collect applications over time
        </p>
      </div>
    </div>
  );
}
