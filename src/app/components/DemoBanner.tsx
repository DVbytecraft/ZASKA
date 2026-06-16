import { X } from 'lucide-react';

interface DemoBannerProps {
  onExit: () => void;
}

export function DemoBanner({ onExit }: DemoBannerProps) {
  return (
    <div
      className="flex items-center justify-between px-4 py-2 text-white text-xs font-medium shrink-0"
      style={{ background: 'linear-gradient(90deg, #5B21B6 0%, #7C3AED 100%)' }}
    >
      <div className="flex items-center gap-2">
        <span
          className="w-2 h-2 rounded-full bg-yellow-300 animate-pulse"
          aria-hidden="true"
        />
        <span>Mode Démo — données non sauvegardées</span>
      </div>
      <button
        onClick={onExit}
        className="ml-3 p-1 rounded hover:bg-white/20 transition-colors"
        aria-label="Quitter le mode démo"
      >
        <X size={14} />
      </button>
    </div>
  );
}
