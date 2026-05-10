import { useEffect, useRef } from 'react';
import { Phone, PhoneOff, Video } from 'lucide-react';
import { Avatar } from '../components/Avatar';

export interface IncomingCallData {
  callId: string;
  callerName: string;
  callerAvatar?: string | null;
  mediaType: 'audio' | 'video';
}

interface IncomingCallScreenProps {
  call: IncomingCallData;
  onAnswer: (callId: string, mediaType: 'audio' | 'video') => void;
  onDecline: () => void;
}

export function IncomingCallScreen({ call, onAnswer, onDecline }: IncomingCallScreenProps) {
  // Auto-decline after 45 seconds (no answer)
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    timeoutRef.current = setTimeout(onDecline, 45_000);
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, [onDecline]);

  return (
    <div
      className="fixed inset-0 z-50 flex flex-col"
      style={{ background: 'linear-gradient(160deg, #1a0533 0%, #4C1D95 50%, #6D28D9 100%)' }}
    >
      {/* Status bar spacer */}
      <div className="pt-16" />

      {/* Incoming call info */}
      <div className="flex-1 flex flex-col items-center justify-center gap-6 px-8">
        {/* Ripple */}
        <div className="relative">
          <span className="absolute inset-0 rounded-full bg-white/10 animate-ping scale-110" />
          <span
            className="absolute inset-0 rounded-full bg-white/5 animate-ping scale-125"
            style={{ animationDelay: '0.4s' }}
          />
          <span
            className="absolute inset-0 rounded-full bg-white/5 animate-ping scale-150"
            style={{ animationDelay: '0.8s' }}
          />
          <Avatar name={call.callerName} size="xl" src={call.callerAvatar ?? undefined} />
        </div>

        <div className="text-center">
          <p className="text-white/70 text-sm font-medium mb-1">
            {call.mediaType === 'video' ? 'Appel vidéo entrant' : 'Appel audio entrant'}
          </p>
          <h2 className="text-white font-bold text-3xl">{call.callerName}</h2>
          <p className="text-white/50 text-sm mt-2">via ZASKA</p>
        </div>
      </div>

      {/* Action buttons */}
      <div className="px-12 pb-20 flex items-center justify-between">
        {/* Decline */}
        <div className="flex flex-col items-center gap-2">
          <button
            onClick={onDecline}
            className="w-[68px] h-[68px] rounded-full bg-red-500 hover:bg-red-600 flex items-center justify-center shadow-2xl transition-all active:scale-90"
            aria-label="Refuser l'appel"
          >
            <PhoneOff size={28} className="text-white" />
          </button>
          <span className="text-white/60 text-xs font-medium">Refuser</span>
        </div>

        {/* Answer */}
        <div className="flex flex-col items-center gap-2">
          <button
            onClick={() => onAnswer(call.callId, call.mediaType)}
            className="w-[68px] h-[68px] rounded-full bg-green-500 hover:bg-green-600 flex items-center justify-center shadow-2xl transition-all active:scale-90"
            aria-label="Répondre à l'appel"
          >
            {call.mediaType === 'video' ? (
              <Video size={28} className="text-white" />
            ) : (
              <Phone size={28} className="text-white" />
            )}
          </button>
          <span className="text-white/60 text-xs font-medium">Répondre</span>
        </div>
      </div>
    </div>
  );
}
