import { useEffect, useRef, useState } from 'react';
import { Send, Phone } from 'lucide-react';
import { Avatar } from './Avatar';
import { apiClient, chatService } from '@zaska/shared-services';
import type { ChatMessage } from '@zaska/shared-services';

interface ChatInterfaceProps {
  taskerName: string;
  taskId?: string;
  onCall?: () => void;
}

export function ChatInterface({ taskerName, taskId, onCall }: ChatInterfaceProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [newMessage, setNewMessage] = useState('');
  const [sending, setSending] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!taskId) return;
    chatService.listMessages(taskId)
      .then(setMessages)
      .catch(() => setMessages([]));
  }, [taskId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const userId = apiClient.getUserId() ?? '';

  const sendMessage = async () => {
    const text = newMessage.trim();
    if (!text || !taskId || sending) return;
    setSending(true);
    setNewMessage('');
    try {
      const msg = await chatService.sendMessage(taskId, text);
      setMessages((prev) => [...prev, msg]);
    } catch {
      setNewMessage(text);
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="flex flex-col h-full">
      <div className="px-4 py-3 bg-white border-b border-gray-200 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Avatar name={taskerName || 'Tasker'} size="sm" />
          <div>
            <h4 className="font-semibold text-gray-900">{taskerName || 'Tasker'}</h4>
            <p className="text-xs text-green-600 flex items-center gap-1">
              <span className="w-2 h-2 bg-green-500 rounded-full inline-block" />
              En ligne
            </p>
          </div>
        </div>
        {onCall && (
          <button
            onClick={onCall}
            className="w-10 h-10 bg-[#6D28D9] rounded-full flex items-center justify-center hover:bg-[#5B21B6] transition-colors"
          >
            <Phone size={18} className="text-white" />
          </button>
        )}
      </div>

      <div className="flex-1 overflow-auto px-4 py-4 space-y-3 bg-gray-50">
        {!taskId && (
          <p className="text-xs text-center text-gray-400 py-8">Sélectionnez une tâche pour démarrer la conversation.</p>
        )}
        {taskId && messages.length === 0 && (
          <p className="text-xs text-center text-gray-400 py-8">Aucun message pour l'instant.</p>
        )}
        {messages.map((msg) => {
          const isMe = msg.senderId === userId;
          return (
            <div key={msg.id} className={`flex ${isMe ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-[75%] rounded-2xl px-4 py-2.5 ${
                isMe ? 'bg-[#6D28D9] text-white' : 'bg-white text-gray-900 border border-gray-200'
              }`}>
                <p className="text-sm">{msg.message}</p>
                <p className={`text-xs mt-1 ${isMe ? 'text-white/70' : 'text-gray-500'}`}>
                  {new Date(msg.createdAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </p>
              </div>
            </div>
          );
        })}
        <div ref={bottomRef} />
      </div>

      <div className="px-4 py-3 bg-white border-t border-gray-200">
        <div className="flex items-center gap-2">
          <input
            type="text"
            value={newMessage}
            onChange={(e) => setNewMessage(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); void sendMessage(); } }}
            placeholder="Écrire un message..."
            disabled={!taskId}
            className="flex-1 px-4 py-2.5 rounded-full border-2 border-gray-200 focus:border-[#6D28D9] focus:outline-none text-sm disabled:bg-gray-50"
          />
          <button
            onClick={() => void sendMessage()}
            disabled={!newMessage.trim() || !taskId || sending}
            className="w-9 h-9 rounded-full bg-[#6D28D9] hover:bg-[#5B21B6] disabled:bg-gray-300 flex items-center justify-center transition-colors"
          >
            <Send size={18} className="text-white" />
          </button>
        </div>
      </div>
    </div>
  );
}
