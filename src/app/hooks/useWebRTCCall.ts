import { useCallback, useEffect, useRef, useState } from 'react';
import { apiClient } from '@zaska/shared-services';

// ── Types ──────────────────────────────────────────────────────────────────────

export type CallState = 'connecting' | 'active' | 'ended' | 'failed';

type Signal =
  | { type: 'offer'; sdp: string }
  | { type: 'answer'; sdp: string }
  | { type: 'ice'; candidate: RTCIceCandidateInit }
  | { type: 'hangup' };

export interface UseWebRTCCallProps {
  callId: string;
  isCaller: boolean;
  mediaType: 'audio' | 'video';
  onEnded: () => void;
}

// ── Env helper ────────────────────────────────────────────────────────────────

function env(key: string): string | undefined {
  return (import.meta as unknown as { env?: Record<string, string> }).env?.[key];
}

// ── ICE servers via zaska.metered.live (falls back to public STUN) ────────────

const FALLBACK_ICE: RTCIceServer[] = [
  { urls: ['stun:stun.l.google.com:19302', 'stun:stun1.l.google.com:19302'] },
  { urls: 'stun:stun.cloudflare.com:3478' },
];

async function fetchIceServers(): Promise<RTCIceServer[]> {
  const apiKey = env('VITE_TURN_SECRET');
  const domain = env('VITE_TURN_DOMAIN') ?? 'zaska.metered.live';
  if (!apiKey) return FALLBACK_ICE;
  try {
    const res = await fetch(`https://${domain}/api/v1/turn/credentials?apiKey=${apiKey}`);
    if (!res.ok) return FALLBACK_ICE;
    const servers: RTCIceServer[] = await res.json();
    return servers.length ? servers : FALLBACK_ICE;
  } catch {
    return FALLBACK_ICE;
  }
}

// ── WS ticket — uses apiClient so auth header is always correct ───────────────

async function fetchWsTicket(callId: string): Promise<string> {
  const res = await apiClient.post<{ ticket: string }>(
    `/calls/${callId}/ws-ticket`,
    {},
  );
  return res.ticket;
}

function getWsUrl(callId: string): string {
  const base = env('VITE_WS_URL') ?? 'ws://localhost:6969';
  return `${base}/ws/calls/${callId}`;
}

// ── Hook ───────────────────────────────────────────────────────────────────────

export function useWebRTCCall({ callId, isCaller, mediaType, onEnded }: UseWebRTCCallProps) {
  const [state, setState] = useState<CallState>('connecting');
  const [localStream, setLocalStream] = useState<MediaStream | null>(null);
  const [remoteStream] = useState<MediaStream>(() => new MediaStream());
  const [micEnabled, setMicEnabled] = useState(true);
  const [camEnabled, setCamEnabled] = useState(true);
  const [elapsed, setElapsed] = useState(0);

  const wsRef = useRef<WebSocket | null>(null);
  const pcRef = useRef<RTCPeerConnection | null>(null);
  const localStreamRef = useRef<MediaStream | null>(null);
  const pendingIce = useRef<RTCIceCandidateInit[]>([]);
  const remoteReady = useRef(false);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const endedRef = useRef(false);
  // Track how long we've been in "disconnected" state to distinguish transient
  // network blips (< 8s) from actual failures that need to terminate the call.
  const disconnectedAt = useRef<number | null>(null);
  const disconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const send = useCallback((msg: Signal) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(msg));
    }
  }, []);

  const endCall = useCallback(() => {
    if (endedRef.current) return;
    endedRef.current = true;
    if (timerRef.current) clearInterval(timerRef.current);
    if (disconnectTimerRef.current) clearTimeout(disconnectTimerRef.current);
    localStreamRef.current?.getTracks().forEach((t) => t.stop());
    pcRef.current?.close();
    wsRef.current?.close();
    setState('ended');
    onEnded();
  }, [onEnded]);

  const hangup = useCallback(() => {
    send({ type: 'hangup' });
    endCall();
  }, [send, endCall]);

  const toggleMic = useCallback(() => {
    localStreamRef.current?.getAudioTracks().forEach((t) => {
      t.enabled = !t.enabled;
    });
    setMicEnabled((v) => !v);
  }, []);

  const toggleCam = useCallback(() => {
    localStreamRef.current?.getVideoTracks().forEach((t) => {
      t.enabled = !t.enabled;
    });
    setCamEnabled((v) => !v);
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function setup() {
      // Fetch ICE servers and WS ticket in parallel
      let iceServers: RTCIceServer[];
      let ticket: string;
      try {
        [iceServers, ticket] = await Promise.all([
          fetchIceServers(),
          fetchWsTicket(callId),
        ]);
      } catch {
        setState('failed');
        endCall();
        return;
      }

      if (cancelled) return;

      const ws = new WebSocket(getWsUrl(callId));
      wsRef.current = ws;

      const pc = new RTCPeerConnection({ iceServers });
      pcRef.current = pc;

      pc.ontrack = (e) => {
        e.streams[0]?.getTracks().forEach((t) => remoteStream.addTrack(t));
      };

      pc.onicecandidate = (e) => {
        if (e.candidate) send({ type: 'ice', candidate: e.candidate.toJSON() });
      };

      pc.onconnectionstatechange = () => {
        const s = pc.connectionState;

        if (s === 'connected') {
          // Clear any pending disconnect timer — we recovered
          if (disconnectTimerRef.current) {
            clearTimeout(disconnectTimerRef.current);
            disconnectTimerRef.current = null;
          }
          disconnectedAt.current = null;
          setState('active');
          if (!timerRef.current) {
            timerRef.current = setInterval(() => setElapsed((v) => v + 1), 1000);
          }
        }

        if (s === 'disconnected') {
          // Attempt ICE restart immediately — handles mobile network switch (WiFi→4G),
          // brief packet loss, NAT timeout.  Caller creates a new offer with iceRestart:true;
          // callee automatically responds with an answer via ws.onmessage.
          disconnectedAt.current = Date.now();
          if (isCaller && pc.signalingState === 'stable') {
            pc.createOffer({ iceRestart: true })
              .then((offer) => pc.setLocalDescription(offer))
              .then(() => {
                if (pc.localDescription?.sdp) {
                  send({ type: 'offer', sdp: pc.localDescription.sdp });
                }
              })
              .catch(() => { /* ICE restart failed silently — safety timer handles termination */ });
          }
          // Safety timer: if still not recovered in 8s, terminate the call
          disconnectTimerRef.current = setTimeout(() => {
            if (!endedRef.current && pc.connectionState !== 'connected') {
              setState('failed');
              endCall();
            }
          }, 8_000);
        }

        if (s === 'failed' || s === 'closed') {
          if (disconnectTimerRef.current) {
            clearTimeout(disconnectTimerRef.current);
            disconnectTimerRef.current = null;
          }
          setState('failed');
          endCall();
        }
      };

      const drainIce = async () => {
        for (const c of pendingIce.current) {
          await pc.addIceCandidate(new RTCIceCandidate(c)).catch(() => {});
        }
        pendingIce.current = [];
        remoteReady.current = true;
      };

      ws.onmessage = async ({ data }) => {
        let msg: Signal;
        try {
          msg = JSON.parse(data as string) as Signal;
        } catch {
          return;
        }
        // Ignore keepalive pong frames
        if ((msg as { type: string }).type === 'pong') return;
        if (msg.type === 'offer') {
          await pc.setRemoteDescription({ type: 'offer', sdp: msg.sdp });
          await drainIce();
          const answer = await pc.createAnswer();
          await pc.setLocalDescription(answer);
          send({ type: 'answer', sdp: answer.sdp! });
        } else if (msg.type === 'answer') {
          await pc.setRemoteDescription({ type: 'answer', sdp: msg.sdp });
          await drainIce();
        } else if (msg.type === 'ice') {
          if (remoteReady.current) {
            pc.addIceCandidate(new RTCIceCandidate(msg.candidate)).catch(() => {});
          } else {
            pendingIce.current.push(msg.candidate);
          }
        } else if (msg.type === 'hangup') {
          endCall();
        }
      };

      ws.onerror = () => {
        clearInterval(pingInterval);
        endCall();
      };

      // P2-001 FIX: Handle WS close events explicitly.
      // Without onclose, a server-initiated close (code 1008 = ticket expired,
      // code 1011 = server error, or any rolling-deploy reconnect) would leave
      // the RTCPeerConnection open indefinitely, consuming media resources and
      // holding ICE candidates against a dead signaling channel.
      ws.onclose = (event) => {
        clearInterval(pingInterval);
        if (!endedRef.current) {
          // 1000 = normal close (hangup already handled by onmessage)
          // Anything else = unexpected close — treat as call failure
          if (event.code !== 1000) {
            setState('failed');
          }
          endCall();
        }
      };

      // Keepalive ping every 30s — prevents NAT / reverse-proxy timeout on idle calls
      const pingInterval = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send('{"type":"ping"}');
        }
      }, 30_000);

      ws.onopen = async () => {
        // Auth handshake with one-time ticket (matches backend pattern)
        ws.send(JSON.stringify({ type: 'auth', ticket }));

        // Acquire local media
        const constraints: MediaStreamConstraints = {
          audio: true,
          video: mediaType === 'video' ? { facingMode: 'user', width: 640, height: 480 } : false,
        };
        let stream: MediaStream;
        try {
          stream = await navigator.mediaDevices.getUserMedia(constraints);
        } catch {
          setState('failed');
          endCall();
          return;
        }
        if (cancelled) {
          stream.getTracks().forEach((t) => t.stop());
          return;
        }
        localStreamRef.current = stream;
        setLocalStream(stream);
        stream.getTracks().forEach((t) => pc.addTrack(t, stream));

        // Caller sends the offer; callee waits for it via ws.onmessage
        if (isCaller) {
          const offer = await pc.createOffer();
          await pc.setLocalDescription(offer);
          send({ type: 'offer', sdp: offer.sdp! });
        }
      };
    }

    void setup();
    return () => {
      cancelled = true;
      if (disconnectTimerRef.current) clearTimeout(disconnectTimerRef.current);
      endCall();
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return {
    state,
    localStream,
    remoteStream,
    micEnabled,
    camEnabled,
    elapsed,
    hangup,
    toggleMic,
    toggleCam,
  };
}

// ── Helpers ────────────────────────────────────────────────────────────────────

export function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60).toString().padStart(2, '0');
  const s = (seconds % 60).toString().padStart(2, '0');
  return `${m}:${s}`;
}
