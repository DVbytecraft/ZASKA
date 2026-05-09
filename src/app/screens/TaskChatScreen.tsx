import { useEffect, useState } from 'react';
import { ArrowLeft } from 'lucide-react';
import { ChatInterface } from '../components/ChatInterface';
import { apiClient, taskService } from '@zaska/shared-services';

interface TaskChatScreenProps {
  taskId?: string;
  onBack: () => void;
}

export function TaskChatScreen({ taskId, onBack }: TaskChatScreenProps) {
  const [partnerName, setPartnerName] = useState<string>('');
  const [partnerSrc, setPartnerSrc] = useState<string | null>(null);

  useEffect(() => {
    if (!taskId) return;
    const myId = apiClient.getUserId();
    taskService.getTask(taskId)
      .then(async (task) => {
        const partnerId = task.createdBy === myId ? task.assignedTo : task.createdBy;
        if (!partnerId) return;
        try {
          const profile = await apiClient.get<{ first_name?: string | null; last_name?: string | null; full_name?: string | null; avatar_url?: string | null }>(`/users/${partnerId}`);
          const name = [profile.first_name, profile.last_name].filter(Boolean).join(' ') || profile.full_name || 'ZASKA';
          setPartnerName(name);
          setPartnerSrc(profile.avatar_url ?? null);
        } catch {
          setPartnerName('Utilisateur');
        }
      })
      .catch(() => {});
  }, [taskId]);

  return (
    <div className="h-full flex flex-col bg-white">
      <div className="px-6 pt-8 pb-4 bg-white border-b border-gray-200">
        <div className="flex items-center gap-3">
          <button onClick={onBack} className="p-2 -ml-2 hover:bg-gray-100 rounded-full transition-colors">
            <ArrowLeft size={24} className="text-gray-700" />
          </button>
          <h2 className="font-bold text-gray-900">{partnerName || 'Discussion'}</h2>
        </div>
      </div>

      <div className="flex-1 overflow-hidden">
        <ChatInterface taskerName={partnerName} partnerSrc={partnerSrc} taskId={taskId} onCall={() => {}} />
      </div>
    </div>
  );
}
