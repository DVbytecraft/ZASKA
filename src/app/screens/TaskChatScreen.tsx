import { useEffect, useState } from 'react';
import { ArrowLeft } from 'lucide-react';
import { ChatInterface } from '../components/ChatInterface';
import { CallScreen } from './CallScreen';
import { apiClient, taskService } from '@zaska/shared-services';

interface TaskChatScreenProps {
  taskId?: string;
  onBack: () => void;
}

interface ActiveCall {
  callId: string;
  mediaType: 'audio' | 'video';
}

export function TaskChatScreen({ taskId, onBack }: TaskChatScreenProps) {
  const [partnerName, setPartnerName] = useState('');
  const [partnerAvatar, setPartnerAvatar] = useState<string | null>(null);
  const [activeCall, setActiveCall] = useState<ActiveCall | null>(null);
  const [callError, setCallError] = useState<string | null>(null);

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

  // ── Initiate outgoing call (caller side) ──────────────────────────────────
  const handleStartCall = async (mediaType: 'audio' | 'video') => {
    if (!taskId) return;
    setCallError(null);
    try {
      const res = await apiClient.post<{ call_id: string; callee_online: boolean }>('/calls', {
        task_id: taskId,
        media_type: mediaType,
      });
      if (!res.callee_online) {
        setCallError("L'autre utilisateur est hors ligne. L'appel n'a pas pu aboutir.");
        setTimeout(() => setCallError(null), 5000);
        return;
      }
      setActiveCall({ callId: res.call_id, mediaType });
    } catch {
      setCallError("Impossible de démarrer l'appel. Vérifiez votre connexion.");
      setTimeout(() => setCallError(null), 4000);
    }
  };

  // ── Active call — caller view (full screen) ───────────────────────────────
  if (activeCall) {
    return (
      <CallScreen
        callId={activeCall.callId}
        isCaller
        mediaType={activeCall.mediaType}
        partnerName={partnerName}
        partnerAvatar={partnerAvatar}
        onEnd={() => setActiveCall(null)}
      />
    );
  }

  return (
    <div className="h-full flex flex-col bg-white">
      {/* Header */}
      <div className="px-4 pt-10 pb-3 bg-white border-b border-gray-100 flex items-center gap-3">
        <button
          onClick={onBack}
          className="p-2 -ml-1 hover:bg-gray-100 rounded-full transition-colors flex-shrink-0"
        >
          <ArrowLeft size={22} className="text-gray-700" />
        </button>
        <h2 className="font-bold text-gray-900 truncate">
          {partnerName || 'Discussion'}
        </h2>
      </div>

      {callError && (
        <div className="mx-4 mt-2 px-3 py-2 bg-red-50 border border-red-200 rounded-xl text-sm text-red-700">
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
