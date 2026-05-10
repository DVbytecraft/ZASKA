import { useEffect, useRef } from 'react';
import {
  Mic, MicOff, Video, VideoOff, PhoneOff, Phone,
  Wifi, WifiOff, Loader2,
} from 'lucide-react';
import { Avatar } from '../components/Avatar';
import { useWebRTCCall, formatDuration } from '../hooks/useWebRTCCall';

interface CallScreenProps {
  callId: string;
  isCaller: boolean;
  mediaType: 'audio' | 'video';
  partnerName: string;
  partnerAvatar?: string | null;
  onEnd: () => void;
}

// ── Video element bound to a MediaStream ──────────────────────────────────────
function StreamVideo({
  stream,
  muted = false,
  className = '',
  mirror = false,
}: {
  stream: MediaStream | null;
  muted?: boolean;
  className?: string;
  mirror?: boolean;
}) {
  const ref = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    if (ref.current && stream) ref.current.srcObject = stream;
  }, [stream]);

  return (
    <video
      ref={ref}
      autoPlay
      playsInline
      muted={muted}
      className={className}
      style={mirror ? { transform: 'scaleX(-1)' } : undefined}
    />
  );
}

// ── Main call screen ──────────────────────────────────────────────────────────
export function CallScreen({
  callId,
  isCaller,
  mediaType,
  partnerName,
  partnerAvatar,
  onEnd,
}: CallScreenProps) {
  const {
    state,
    localStream,
    remoteStream,
    micEnabled,
    camEnabled,
    elapsed,
    hangup,
    toggleMic,
    toggleCam,
  } = useWebRTCCall({ callId, isCaller, mediaType, onEnded: onEnd });

  const isVideo = mediaType === 'video';

  // ── Connecting / failed states ────────────────────────────────────────────
  if (state === 'ended' || state === 'failed') {
    return (
      <div className="fixed inset-0 z-50 bg-gray-900 flex flex-col items-center justify-center gap-4">
        {state === 'failed' ? (
          <>
            <WifiOff size={48} className="text-red-400" />
            <p className="text-white font-semibold">Connexion échouée</p>
            <p className="text-gray-400 text-sm text-center px-8">
              Vérifiez votre connexion réseau et réessayez.
            </p>
          </>
        ) : (
          <>
            <PhoneOff size={48} className="text-gray-400" />
            <p className="text-white font-semibold">Appel terminé</p>
          </>
        )}
        <button
          onClick={onEnd}
          className="mt-4 px-8 py-3 bg-white/10 rounded-2xl text-white font-medium"
        >
          Fermer
        </button>
      </div>
    );
  }

  // ── VIDEO CALL ─────────────────────────────────────────────────────────────
  if (isVideo) {
    return (
      <div className="fixed inset-0 z-50 bg-black flex flex-col">
        {/* Remote video — full screen */}
        <div className="relative flex-1 bg-gray-900">
          {state === 'connecting' ? (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-4">
              <Avatar name={partnerName} size="xl" src={partnerAvatar ?? undefined} />
              <p className="text-white font-semibold text-lg">{partnerName}</p>
              <div className="flex items-center gap-2 text-gray-300 text-sm">
                <Loader2 size={16} className="animate-spin" />
                Connexion en cours…
              </div>
            </div>
          ) : (
            <StreamVideo
              stream={remoteStream}
              className="absolute inset-0 w-full h-full object-cover"
            />
          )}

          {/* Local PiP — top right */}
          {localStream && (
            <div className="absolute top-12 right-4 w-28 h-40 rounded-2xl overflow-hidden border-2 border-white/30 shadow-xl bg-gray-800">
              <StreamVideo
                stream={localStream}
                muted
                mirror
                className="w-full h-full object-cover"
              />
              {!camEnabled && (
                <div className="absolute inset-0 bg-gray-800 flex items-center justify-center">
                  <VideoOff size={20} className="text-gray-400" />
                </div>
              )}
            </div>
          )}

          {/* Header overlay */}
          <div className="absolute top-0 left-0 right-0 px-6 pt-12 pb-6 bg-gradient-to-b from-black/60 to-transparent">
            <p className="text-white font-bold text-xl">{partnerName}</p>
            {state === 'active' ? (
              <div className="flex items-center gap-1.5 mt-1">
                <Wifi size={13} className="text-green-400" />
                <p className="text-green-300 text-sm font-medium">{formatDuration(elapsed)}</p>
              </div>
            ) : (
              <p className="text-gray-300 text-sm mt-1">Connexion…</p>
            )}
          </div>
        </div>

        {/* Controls bar */}
        <div className="bg-black/90 px-8 py-8 flex items-center justify-center gap-8 safe-area-bottom">
          <ControlButton
            icon={micEnabled ? <Mic size={22} /> : <MicOff size={22} />}
            label={micEnabled ? 'Micro' : 'Muet'}
            onClick={toggleMic}
            active={micEnabled}
          />
          <button
            onClick={hangup}
            className="w-16 h-16 rounded-full bg-red-500 hover:bg-red-600 flex items-center justify-center shadow-lg transition-colors"
            aria-label="Raccrocher"
          >
            <PhoneOff size={26} className="text-white" />
          </button>
          <ControlButton
            icon={camEnabled ? <Video size={22} /> : <VideoOff size={22} />}
            label={camEnabled ? 'Caméra' : 'Off'}
            onClick={toggleCam}
            active={camEnabled}
          />
        </div>
      </div>
    );
  }

  // ── AUDIO CALL ─────────────────────────────────────────────────────────────
  return (
    <div
      className="fixed inset-0 z-50 flex flex-col"
      style={{ background: 'linear-gradient(160deg, #3B0764 0%, #6D28D9 60%, #7C3AED 100%)' }}
    >
      {/* Partner info */}
      <div className="flex-1 flex flex-col items-center justify-center gap-6 px-8">
        {/* Ripple animation around avatar */}
        <div className="relative">
          {state === 'connecting' && (
            <>
              <span className="absolute inset-0 rounded-full bg-white/10 animate-ping scale-110" />
              <span className="absolute inset-0 rounded-full bg-white/5 animate-ping scale-125 animation-delay-300" />
            </>
          )}
          <Avatar name={partnerName} size="xl" src={partnerAvatar ?? undefined} />
        </div>

        <div className="text-center">
          <h2 className="text-white font-bold text-2xl">{partnerName}</h2>
          {state === 'connecting' ? (
            <p className="text-white/70 text-sm mt-1">
              {isCaller ? 'Appel en cours…' : 'Connexion…'}
            </p>
          ) : (
            <div className="flex items-center justify-center gap-1.5 mt-1">
              <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
              <p className="text-green-300 text-sm font-medium">{formatDuration(elapsed)}</p>
            </div>
          )}
        </div>
      </div>

      {/* Controls */}
      <div className="px-8 py-12 flex items-center justify-center gap-10">
        <ControlButton
          icon={micEnabled ? <Mic size={22} /> : <MicOff size={22} />}
          label={micEnabled ? 'Micro' : 'Muet'}
          onClick={toggleMic}
          active={micEnabled}
          light
        />
        <button
          onClick={hangup}
          className="w-18 h-18 w-[72px] h-[72px] rounded-full bg-red-500 hover:bg-red-600 flex items-center justify-center shadow-2xl transition-all active:scale-95"
          aria-label="Raccrocher"
        >
          <PhoneOff size={28} className="text-white" />
        </button>
        {/* Placeholder for speaker toggle */}
        <ControlButton
          icon={<Phone size={22} />}
          label="Haut-parleur"
          onClick={() => {}}
          active
          light
        />
      </div>
    </div>
  );
}

// ── Reusable control button ───────────────────────────────────────────────────
function ControlButton({
  icon,
  label,
  onClick,
  active,
  light = false,
}: {
  icon: React.ReactNode;
  label: string;
  onClick: () => void;
  active: boolean;
  light?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      className="flex flex-col items-center gap-1.5"
      aria-label={label}
    >
      <div
        className={`w-14 h-14 rounded-full flex items-center justify-center transition-colors ${
          active
            ? light
              ? 'bg-white/20 text-white'
              : 'bg-gray-700 text-white'
            : light
            ? 'bg-white/10 text-white/50'
            : 'bg-gray-600 text-gray-400'
        }`}
      >
        {icon}
      </div>
      <span className={`text-xs font-medium ${light ? 'text-white/70' : 'text-gray-400'}`}>
        {label}
      </span>
    </button>
  );
}
