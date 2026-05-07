import { ArrowLeft, Zap, Users } from 'lucide-react';

interface TaskModeSelectionScreenProps {
  onBack: () => void;
  onSelect: (mode: 'fast' | 'choose') => void;
}

export function TaskModeSelectionScreen({ onBack, onSelect }: TaskModeSelectionScreenProps) {
  return (
    <div className="h-full flex flex-col bg-white">
      <div className="px-6 pt-6 pb-4">
        <button onClick={onBack} className="p-2 -ml-2 hover:bg-gray-100 rounded-full transition-colors">
          <ArrowLeft size={24} className="text-gray-700" />
        </button>
      </div>

      <div className="flex-1 flex items-center justify-center px-6">
        <div className="w-full max-w-sm space-y-3">
          <button
            onClick={() => onSelect('fast')}
            className="w-full flex items-center gap-4 p-4 rounded-xl border-2 border-gray-200 hover:border-[#6D28D9] hover:bg-[#6D28D9]/5 transition-all active:scale-[0.98]"
          >
            <div className="w-12 h-12 rounded-xl bg-amber-50 flex items-center justify-center flex-shrink-0">
              <Zap size={24} className="text-amber-600" fill="currentColor" />
            </div>
            <div className="flex-1 text-left">
              <h3 className="font-bold text-gray-900">Fast</h3>
              <p className="text-sm text-gray-500">Instant</p>
            </div>
          </button>

          <button
            onClick={() => onSelect('choose')}
            className="w-full flex items-center gap-4 p-4 rounded-xl border-2 border-gray-200 hover:border-[#6D28D9] hover:bg-[#6D28D9]/5 transition-all active:scale-[0.98]"
          >
            <div className="w-12 h-12 rounded-xl bg-purple-50 flex items-center justify-center flex-shrink-0">
              <Users size={24} className="text-[#6D28D9]" />
            </div>
            <div className="flex-1 text-left">
              <h3 className="font-bold text-gray-900">Choose</h3>
              <p className="text-sm text-gray-500">Compare</p>
            </div>
          </button>
        </div>
      </div>
    </div>
  );
}
