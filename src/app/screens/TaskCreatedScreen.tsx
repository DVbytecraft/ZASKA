import { Button } from '../components/Button';
import { CheckCircle2, Zap, Users, Home } from 'lucide-react';

interface TaskCreatedScreenProps {
  taskMode: 'fast' | 'choose';
  onViewTask: () => void;
  onBackHome: () => void;
}

export function TaskCreatedScreen({ taskMode, onViewTask, onBackHome }: TaskCreatedScreenProps) {
  return (
    <div className="h-full flex flex-col items-center justify-center px-8 bg-white">
      <div className="w-20 h-20 rounded-full bg-gradient-to-br from-[#6D28D9] to-[#5B21B6] flex items-center justify-center mb-6 shadow-lg">
        <CheckCircle2 size={48} className="text-white" strokeWidth={3} />
      </div>

      <h2 className="text-2xl font-bold text-gray-900 mb-8">Task created</h2>

      <div className="w-full max-w-sm space-y-3">
        <Button fullWidth onClick={onViewTask}>
          View task
        </Button>
        <button onClick={onBackHome} className="w-full py-3 text-gray-600 font-medium hover:text-gray-900 transition-colors">
          Back to home
        </button>
      </div>
    </div>
  );
}
