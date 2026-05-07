import { useEffect } from 'react';
import { Loader2 } from 'lucide-react';

interface MatchingScreenProps {
  onComplete: () => void;
}

export function MatchingScreen({ onComplete }: MatchingScreenProps) {
  useEffect(() => {
    const timer = setTimeout(onComplete, 3000);
    return () => clearTimeout(timer);
  }, [onComplete]);

  return (
    <div className="h-full bg-gradient-to-br from-[#6D28D9] via-[#5B21B6] to-[#4C1D95] flex flex-col items-center justify-center px-8 relative overflow-hidden">
      <div className="absolute inset-0 opacity-10">
        <div className="absolute top-1/4 left-1/4 w-64 h-64 bg-white rounded-full blur-3xl animate-pulse"></div>
        <div className="absolute bottom-1/4 right-1/4 w-80 h-80 bg-white rounded-full blur-3xl animate-pulse" style={{ animationDelay: '1s' }}></div>
      </div>

      <div className="relative z-10 text-center">
        <div className="w-24 h-24 bg-white/20 backdrop-blur-sm rounded-full flex items-center justify-center mb-8 mx-auto">
          <Loader2 size={48} className="text-white animate-spin" strokeWidth={2.5} />
        </div>
        <h2 className="text-2xl font-bold text-white mb-2">Finding nearby taskers</h2>
        <p className="text-white/75 text-base">This usually takes a few seconds</p>
      </div>
    </div>
  );
}
