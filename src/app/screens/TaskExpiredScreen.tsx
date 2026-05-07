import { Button } from '../components/Button';
import { Clock } from 'lucide-react';

interface TaskExpiredScreenProps {
  onRepost: () => void;
  onBackHome: () => void;
}

export function TaskExpiredScreen({ onRepost, onBackHome }: TaskExpiredScreenProps) {
  return (
    <div className="h-full flex flex-col items-center justify-center px-8 bg-white">
      <div className="w-20 h-20 rounded-full bg-gray-100 flex items-center justify-center mb-6">
        <Clock size={40} className="text-gray-400" />
      </div>

      <h3 className="text-xl font-bold text-gray-900 mb-2 text-center">Task expired</h3>
      <p className="text-gray-600 text-center mb-8 max-w-xs text-sm">
        This task has expired without being accepted
      </p>

      <div className="w-full max-w-sm space-y-3">
        <Button fullWidth onClick={onRepost}>
          Post again
        </Button>
        <button onClick={onBackHome} className="w-full py-3 text-gray-600 font-medium hover:text-gray-900 transition-colors">
          Back to home
        </button>
      </div>
    </div>
  );
}
