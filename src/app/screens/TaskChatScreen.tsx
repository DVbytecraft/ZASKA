import { useEffect, useRef, useState } from 'react';
import { ArrowLeft } from 'lucide-react';
import { ChatInterface } from '../components/ChatInterface';
import { CallScreen } from './CallScreen';
import { IncomingCallScreen, type IncomingCallData } from './IncomingCallScreen';
import { apiClient, taskService } from '@zaska/shared-services';

interface TaskChatScreenProps {
  taskId?: string;
  onBack: () => void;
}

interface ActiveCall {
  callId: string;
  isCaller: boolean;
  mediaType: 'audio' | 'video';
}

function env(key: string): string | undefined {
  return (import.meta as unknown as { env?: Record<string, string> }).env?.[key];
}

function getNotificationWsUrl(userId: string): string {
  const base = env('VITE_WS_URL') ?? 'ws://localhost:6969';
  return `${base}/ws/users/${userId}/calls`;
}

// ── Component ─────────────────────────────────────────────────────────────────

export function TaskChatScreen({ taskId, onBack }: TaskChatScreenProps) {
  const [partnerName, setPartnerName] = useState('');
  const [partnerAvatar, setPartnerAvatar] = useState<string | null>(null);
  const [activeCall, setActiveCall] = useState<ActiveCall | null>(null);
  const [incomingCall, setIncomingCall] = useState<IncomingCallData | null>(null);
  const [callError, setCallError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);

  // ── Load partner profile ──────────────────────────────────────────────────
  useEffect(() => {
    if (!taskId) return;
    const myId = apiClient.getUserId();
    taskService
      .getTask(taskId)
      .then(async (task) => {
        const partnerId = task.createdBy === myId ? task.assignedTo : task.createdBy;
        if (!partnerId) return;
        try {
          const profile = await apiClient.get<{
            first_name?: string | null;
            last_name?: string | null;
            full_name?: string | null;
            avatar_url?: string | null;
          }>(`/users/${partnerId}`);
          const name =
            [profile.first_name, profile.last_name].filter(Boolean).join(' ') ||
            profile.full_name ||
            'ZASKA';
          setPartnerName(name);
          setPartnerAvatar(profile.avatar_url ?? null);
        } catch {
          setPartnerName('Utilisateur');
        }
      })
      .catch(() => {});
  }, [taskId]);

  // ── Incoming call notification WebSocket ──────────────────────────────────
  useEffect(() => {
    const myId = apiClient.getUserId();
    if (!myId) return;

    let ws: WebSocket | null = null;
    let closed = false;

    async function connect() {
      // Get one-time ticket via apiClient (handles auth header correctly)
      let ticket: string;
      try {
        const res = await apiClient.post<{ ticket: string }>('/calls/user/ws-ticket', {});
        ticket = res.ticket;
      } catch {
        return; // Non-fatal — incoming calls won't ring but chat still works
      }

      if (closed) return;

      ws = new WebSocket(getNotificationWsUrl(myId!));
      wsRef.current = ws;

      ws.onopen = () => {
        ws!.send(JSON.stringify({ type: 'auth', ticket }));
      };

      ws.onmessage = ({ data }) => {
        try {
          const msg = JSON.parse(data as string) as {
            type: string;
            call_id: string;
            caller_name: string;
            caller_avatar?: string;
            media_type: 'audio' | 'video';
          };
          if (msg.type === 'incoming_call') {
            setIncomingCall({
              callId: msg.call_id,
              callerName: msg.caller_name,
              callerAvatar: msg.caller_avatar ?? null,
              mediaType: msg.media_type,
            });
          }
        } catch {
          // Ignore malformed frames
        }
      };

      ws.onerror = () => {};
    }

    void connect();

    return () => {
      closed = true;
      ws?.close();
      wsRef.current = null;
    };
  }, []);

  // ── Initiate call ─────────────────────────────────────────────────────────
  const handleStartCall = async (mediaType: 'audio' | 'video') => {
    if (!taskId) return;
    setCallError(null);
    try {
      const res = await apiClient.post<{ call_id: string }>('/calls', {
        task_id: taskId,
        media_type: mediaType,
      });
      setActiveCall({ callId: res.call_id, isCaller: true, mediaType });
    } catch {
      setCallError("Impossible de démarrer l'appel. Vérifiez votre connexion.");
      setTimeout(() => setCallError(null), 4000);
    }
  };

  // ── Answer incoming call ──────────────────────────────────────────────────
  const handleAnswer = (callId: string, mediaType: 'audio' | 'video') => {
    setIncomingCall(null);
    setActiveCall({ callId, isCaller: false, mediaType });
  };

  // ── Decline incoming call ─────────────────────────────────────────────────
  const handleDecline = () => {
    if (incomingCall) {
      apiClient.post(`/calls/${incomingCall.callId}/end`, {}).catch(() => {});
    }
    setIncomingCall(null);
  };

  // ── Active call — full screen ─────────────────────────────────────────────
  if (activeCall) {
    return (
      <CallScreen
        callId={activeCall.callId}
        isCaller={activeCall.isCaller}
        mediaType={activeCall.mediaType}
        partnerName={partnerName}
        partnerAvatar={partnerAvatar}
        onEnd={() => setActiveCall(null)}
      />
    );
  }

  return (
    <div className="h-full flex flex-col bg-white">
      {incomingCall && (
        <IncomingCallScreen
          call={incomingCall}
          onAnswer={handleAnswer}
          onDecline={handleDecline}
        />
      )}

      <div className="px-6 pt-8 pb-4 bg-white border-b border-gray-200">
        <div className="flex items-center gap-3">
          <button
            onClick={onBack}
            className="p-2 -ml-2 hover:bg-gray-100 rounded-full transition-colors"
          >
            <ArrowLeft size={24} className="text-gray-700" />
          </button>
          <h2 className="font-bold text-gray-900">{partnerName || 'Discussion'}</h2>
        </div>
      </div>

      {callError && (
        <div className="mx-4 mt-3 px-4 py-2 bg-red-50 border border-red-200 rounded-xl text-sm text-red-700">
          {callError}
        </div>
      )}

      <div className="flex-1 overflow-hidden">
        <ChatInterface
          taskerName={partnerName}
          partnerSrc={partnerAvatar}
          taskId={taskId}
          onCall={handleStartCall}
        />
      </div>
    </div>
  );
}
