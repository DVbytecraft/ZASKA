import { Zap, Users } from 'lucide-react';

interface ModeIndicatorProps {
  mode: 'fast' | 'choose';
  size?: 'sm' | 'md';
}

export function ModeIndicator({ mode, size = 'md' }: ModeIndicatorProps) {
  const config = {
    fast: {
      icon: Zap,
      label: 'FAST',
      gradient: 'from-amber-400 to-orange-500',
      emoji: '⚡'
    },
    choose: {
      icon: Users,
      label: 'CHOOSE',
      gradient: 'from-purple-500 to-purple-600',
      emoji: '🤝'
    }
  };

  const current = config[mode];
  const Icon = current.icon;

  const sizes = {
    sm: 'px-2 py-0.5 text-xs',
    md: 'px-2.5 py-1 text-xs'
  };

  return (
    <span className={`inline-flex items-center gap-1 bg-gradient-to-r ${current.gradient} text-white font-bold rounded-full ${sizes[size]}`}>
      {mode === 'fast' ? (
        <Zap size={10} fill="white" />
      ) : (
        <span>{current.emoji}</span>
      )}
      {current.label}
    </span>
  );
}
