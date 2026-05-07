import { ArrowLeft } from 'lucide-react';
import { ChatInterface } from '../components/ChatInterface';

interface TaskChatScreenProps {
  taskerName: string;
  taskId?: string;
  onBack: () => void;
}

export function TaskChatScreen({ taskerName, taskId, onBack }: TaskChatScreenProps) {
  return (
    <div className="h-full flex flex-col bg-white">
      <div className="px-6 pt-8 pb-4 bg-white border-b border-gray-200">
        <div className="flex items-center gap-3">
          <button onClick={onBack} className="p-2 -ml-2 hover:bg-gray-100 rounded-full transition-colors">
            <ArrowLeft size={24} className="text-gray-700" />
          </button>
          <h2 className="font-bold text-gray-900">{taskerName || 'Chat'}</h2>
        </div>
      </div>

      <div className="flex-1 overflow-hidden">
        <ChatInterface taskerName={taskerName} taskId={taskId} onCall={() => {}} />
      </div>
    </div>
  );
}
