import { useEffect, useRef, useState, useCallback } from 'react';
import {
  Mic, MicOff, Video, VideoOff, PhoneOff,
  Volume2, VolumeX, Wifi, WifiOff, Loader2,
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
  videoRef,
}: {
  stream: MediaStream | null;
  muted?: boolean;
  className?: string;
  mirror?: boolean;
  videoRef?: React.RefObject<HTMLVideoElement>;
}) {
  const internalRef = useRef<HTMLVideoElement>(null);
  const ref = videoRef ?? internalRef;

  useEffect(() => {
    const el = ref.current;
    if (el && stream) el.srcObject = stream;
  }, [stream, ref]);

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

// ── Speaker toggle ─────────────────────────────────────────────────────────────

async function applySpeaker(
  videoEl: HTMLVideoElement | null,
  enabled: boolean,
): Promise<void> {
  if (!videoEl || !('setSinkId' in videoEl)) return;
  try {
    const devices = await navigator.mediaDevices.enumerateDevices();
    const outputs = devices.filter((d) => d.kind === 'audiooutput');
    if (enabled) {
      // Default output device (loudspeaker)
      const deviceId =
        outputs.find(
          (d) =>
            d.deviceId === 'default' ||
            (!d.label.toLowerCase().includes('earpiece') && !d.label.toLowerCase().includes('handset')),
        )?.deviceId ?? '';
      await (videoEl as HTMLVideoElement & { setSinkId(id: string): Promise<void> }).setSinkId(deviceId);
    } else {
      // Communications/earpiece device
      const deviceId =
        outputs.find(
          (d) =>
            d.deviceId === 'communications' ||
            d.label.toLowerCase().includes('earpiece') ||
            d.label.toLowerCase().includes('handset'),
        )?.deviceId ?? 'communications';
      await (videoEl as HTMLVideoElement & { setSinkId(id: string): Promise<void> }).setSinkId(deviceId);
    }
  } catch {
    // setSinkId not supported on this browser — visual feedback only
  }
}

// ── Reusable control button ───────────────────────────────────────────────────

function ControlButton({
  icon,
  label,
  onClick,
  active,
  danger = false,
  light = false,
}: {
  icon: React.ReactNode;
  label: string;
  onClick: () => void;
  active: boolean;
  danger?: boolean;
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
          danger && !active
            ? 'bg-red-500/30 text-red-300'
            : active
            ? light
              ? 'bg-white/20 text-white'
              : 'bg-gray-700 text-white'
            : light
            ? 'bg-white/10 text-white/40'
            : 'bg-gray-600 text-gray-500'
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

  const [speakerOn, setSpeakerOn] = useState(true);
  const remoteVideoRef = useRef<HTMLVideoElement>(null);

  const toggleSpeaker = useCallback(async () => {
    const next = !speakerOn;
    setSpeakerOn(next);
    await applySpeaker(remoteVideoRef.current, next);
  }, [speakerOn]);

  // Apply initial speaker state once remote stream is available
  useEffect(() => {
    if (remoteStream && remoteVideoRef.current) {
      void applySpeaker(remoteVideoRef.current, speakerOn);
    }
  }, [remoteStream]); // eslint-disable-line react-hooks/exhaustive-deps

  const isVideo = mediaType === 'video';

  // ── Ended / Failed ────────────────────────────────────────────────────────
  if (state === 'ended' || state === 'failed') {
    return (
      <div className="fixed inset-0 z-[60] bg-gray-900 flex flex-col items-center justify-center gap-4">
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
      <div className="fixed inset-0 z-[60] bg-black flex flex-col">
        {/* Remote video */}
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
              videoRef={remoteVideoRef}
              className="absolute inset-0 w-full h-full object-cover"
            />
          )}

          {/* Local PiP */}
          {localStream && (
            <div className="absolute top-12 right-3 w-24 h-36 rounded-2xl overflow-hidden border-2 border-white/30 shadow-xl bg-gray-800">
              <StreamVideo
                stream={localStream}
                muted
                mirror
                className="w-full h-full object-cover"
              />
              {!camEnabled && (
                <div className="absolute inset-0 bg-gray-800 flex items-center justify-center">
                  <VideoOff size={18} className="text-gray-400" />
                </div>
              )}
            </div>
          )}

          {/* Header overlay */}
          <div className="absolute top-0 left-0 right-0 px-5 pt-10 pb-6 bg-gradient-to-b from-black/60 to-transparent">
            <p className="text-white font-bold text-xl">{partnerName}</p>
            {state === 'active' ? (
              <div className="flex items-center gap-1.5 mt-1">
                <Wifi size={12} className="text-green-400" />
                <p className="text-green-300 text-sm font-medium">{formatDuration(elapsed)}</p>
              </div>
            ) : (
              <p className="text-gray-300 text-sm mt-1">Connexion…</p>
            )}
          </div>
        </div>

        {/* Controls */}
        <div className="bg-black/90 px-6 py-8 flex items-center justify-between safe-area-bottom">
          <ControlButton
            icon={micEnabled ? <Mic size={20} /> : <MicOff size={20} />}
            label={micEnabled ? 'Micro' : 'Muet'}
            onClick={toggleMic}
            active={micEnabled}
          />
          <ControlButton
            icon={speakerOn ? <Volume2 size={20} /> : <VolumeX size={20} />}
            label={speakerOn ? 'Enceinte' : 'Oreillette'}
            onClick={() => void toggleSpeaker()}
            active={speakerOn}
          />
          <button
            onClick={hangup}
            className="w-16 h-16 rounded-full bg-red-500 hover:bg-red-600 flex items-center justify-center shadow-lg transition-colors"
            aria-label="Raccrocher"
          >
            <PhoneOff size={26} className="text-white" />
          </button>
          <ControlButton
            icon={camEnabled ? <Video size={20} /> : <VideoOff size={20} />}
            label={camEnabled ? 'Caméra' : 'Off'}
            onClick={toggleCam}
            active={camEnabled}
          />
        </div>
      </div>
    );
  }

  // ── AUDIO CALL ─────────────────────────────────────────────────────────────

  // Hidden audio element for remote stream (audio-only calls)
  return (
    <div
      className="fixed inset-0 z-[60] flex flex-col"
      style={{ background: 'linear-gradient(160deg, #1a0533 0%, #4C1D95 45%, #6D28D9 100%)' }}
    >
      {/* Hidden video element to route remote audio */}
      <StreamVideo
        stream={remoteStream}
        videoRef={remoteVideoRef}
        muted={false}
        className="hidden"
      />

      {/* Partner info */}
      <div className="flex-1 flex flex-col items-center justify-center gap-6 px-8">
        <div className="relative">
          {state === 'connecting' && (
            <>
              <span className="absolute inset-0 rounded-full bg-white/10 animate-ping scale-110" />
              <span
                className="absolute inset-0 rounded-full bg-white/5 animate-ping scale-125"
                style={{ animationDelay: '400ms' }}
              />
            </>
          )}
          <Avatar name={partnerName} size="xl" src={partnerAvatar ?? undefined} />
        </div>

        <div className="text-center">
          <h2 className="text-white font-bold text-2xl">{partnerName}</h2>
          {state === 'connecting' ? (
            <p className="text-white/60 text-sm mt-1">
              {isCaller ? 'Appel en cours…' : 'Connexion…'}
            </p>
          ) : (
            <div className="flex items-center justify-center gap-1.5 mt-2">
              <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
              <p className="text-green-300 text-sm font-medium tabular-nums">
                {formatDuration(elapsed)}
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Controls */}
      <div className="px-8 pb-14 pt-6 flex items-center justify-between max-w-xs mx-auto w-full">
        <ControlButton
          icon={micEnabled ? <Mic size={22} /> : <MicOff size={22} />}
          label={micEnabled ? 'Micro' : 'Muet'}
          onClick={toggleMic}
          active={micEnabled}
          light
        />
        <button
          onClick={hangup}
          className="w-[72px] h-[72px] rounded-full bg-red-500 hover:bg-red-600 flex items-center justify-center shadow-2xl transition-all active:scale-95"
          aria-label="Raccrocher"
        >
          <PhoneOff size={28} className="text-white" />
        </button>
        <ControlButton
          icon={speakerOn ? <Volume2 size={22} /> : <VolumeX size={22} />}
          label={speakerOn ? 'Enceinte' : 'Oreillette'}
          onClick={() => void toggleSpeaker()}
          active={speakerOn}
          light
        />
      </div>
    </div>
  );
}
