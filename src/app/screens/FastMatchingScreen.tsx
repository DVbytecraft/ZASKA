import { useState, useEffect } from 'react';
import { Avatar } from '../components/Avatar';
import { CheckCircle2, Loader2 } from 'lucide-react';

interface FastMatchingScreenProps {
  onMatched: () => void;
  taskerName?: string;
}

export function FastMatchingScreen({ onMatched, taskerName = 'Tasker disponible' }: FastMatchingScreenProps) {
  const [stage, setStage] = useState<'searching' | 'matched'>('searching');

  useEffect(() => {
    const timer = setTimeout(() => {
      setStage('matched');
      setTimeout(onMatched, 2000);
    }, 3000);
    return () => clearTimeout(timer);
  }, [onMatched]);

  if (stage === 'searching') {
    return (
      <div className="h-full bg-gradient-to-br from-amber-500 via-orange-500 to-orange-600 flex flex-col items-center justify-center px-8 relative overflow-hidden">
        <div className="absolute inset-0 opacity-10">
          <div className="absolute top-1/4 left-1/4 w-64 h-64 bg-white rounded-full blur-3xl animate-pulse"></div>
          <div className="absolute bottom-1/4 right-1/4 w-80 h-80 bg-white rounded-full blur-3xl animate-pulse" style={{ animationDelay: '1s' }}></div>
        </div>

        <div className="relative z-10 text-center">
          <div className="w-28 h-28 bg-white/20 backdrop-blur-sm rounded-full flex items-center justify-center mb-8 mx-auto animate-pulse">
            <Loader2 size={56} className="text-white animate-spin" strokeWidth={2.5} />
          </div>
          <h2 className="text-3xl font-bold text-white mb-3">Finding nearby taskers</h2>
          <p className="text-white/80 text-base">This usually takes just a few seconds...</p>

          <div className="mt-8 flex justify-center gap-2">
            <div className="w-2 h-2 bg-white/60 rounded-full animate-bounce"></div>
            <div className="w-2 h-2 bg-white/60 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
            <div className="w-2 h-2 bg-white/60 rounded-full animate-bounce" style={{ animationDelay: '0.4s' }}></div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full bg-gradient-to-br from-green-500 to-emerald-600 flex flex-col items-center justify-center px-8 relative overflow-hidden">
      <div className="absolute inset-0 opacity-10">
        <div className="absolute inset-0 bg-white rounded-full blur-3xl scale-150"></div>
      </div>

      <div className="relative z-10 text-center">
        <div className="w-28 h-28 bg-white rounded-full flex items-center justify-center mb-6 mx-auto shadow-2xl animate-scale-in">
          <CheckCircle2 size={64} className="text-green-600" strokeWidth={3} />
        </div>

        <h2 className="text-3xl font-bold text-white mb-3">Task accepted!</h2>
        <p className="text-white/90 text-lg mb-6">A tasker is ready to help</p>

        <div className="bg-white/20 backdrop-blur-sm rounded-2xl p-6 max-w-sm mx-auto">
          <div className="flex items-center gap-4 mb-4">
            <Avatar name={taskerName} size="lg" />
            <div className="text-left">
              <h4 className="font-bold text-white text-lg">{taskerName}</h4>
              <p className="text-white/80 text-sm">Tasker vérifié</p>
            </div>
          </div>
          <div className="bg-white/10 rounded-xl p-3">
            <p className="text-white/90 text-sm">
              En route · Arrivée prévue sous peu
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
