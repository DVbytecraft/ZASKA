import { useEffect, useRef, useState } from 'react';
import {
  Send, Phone, Video, MapPin, X, Navigation, Loader,
  Paperclip, Image, FileText, Film, Download,
} from 'lucide-react';
import { Avatar } from './Avatar';
import { apiClient, chatService } from '@zaska/shared-services';
import type { ChatMessage, UserAddress } from '@zaska/shared-services';
import { requestGeolocation } from '../hooks/useTaskFlow';

interface ChatInterfaceProps {
  taskerName: string;
  taskId?: string;
  partnerSrc?: string | null;
  onCall?: () => void;
}

// ── Helpers ───────────────────────────────────────────────────────────────────
const ALLOWED_TYPES = [
  'image/jpeg', 'image/png', 'image/gif', 'image/webp',
  'video/mp4', 'video/webm', 'video/quicktime',
  'application/pdf',
];
const IMAGE_TYPES = new Set(['image/jpeg', 'image/png', 'image/gif', 'image/webp']);
const VIDEO_TYPES = new Set(['video/mp4', 'video/webm', 'video/quicktime']);

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// ── Call Modal ────────────────────────────────────────────────────────────────
function CallModal({ type, onClose }: { type: 'audio' | 'video'; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-6" onClick={onClose}>
      <div className="bg-white rounded-3xl p-8 text-center max-w-xs w-full shadow-2xl" onClick={e => e.stopPropagation()}>
        {type === 'video'
          ? <Video size={48} className="text-[#6D28D9] mx-auto mb-4" />
          : <Phone size={48} className="text-[#6D28D9] mx-auto mb-4" />
        }
        <h3 className="text-lg font-bold text-gray-900 mb-2">
          {type === 'video' ? 'Appel vidéo' : 'Appel audio'}
        </h3>
        <p className="text-sm text-gray-500 mb-6">Cette fonctionnalité sera disponible prochainement.</p>
        <button onClick={onClose} className="w-full py-3 bg-[#6D28D9] text-white rounded-2xl font-semibold text-sm">OK</button>
      </div>
    </div>
  );
}

// ── Location Drawer ───────────────────────────────────────────────────────────
interface LocationDrawerProps { onSend: (text: string) => void; onClose: () => void; }

function LocationDrawer({ onSend, onClose }: LocationDrawerProps) {
  const [addresses, setAddresses] = useState<UserAddress[]>([]);
  const [gpsLoading, setGpsLoading] = useState(false);

  useEffect(() => { apiClient.get<UserAddress[]>('/addresses').then(setAddresses).catch(() => {}); }, []);

  const sendGps = () => {
    setGpsLoading(true);
    requestGeolocation()
      .then(({ latitude, longitude }) => { onSend(`📍 Ma position : https://maps.google.com/?q=${latitude},${longitude}`); onClose(); })
      .catch(() => { onSend('📍 Position GPS non disponible (vérifiez les permissions)'); onClose(); })
      .finally(() => setGpsLoading(false));
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/50 flex items-end" onClick={onClose}>
      <div className="w-full bg-white rounded-t-3xl max-h-[60vh] flex flex-col" onClick={e => e.stopPropagation()}>
        <div className="px-6 pt-5 pb-3 border-b border-gray-100 flex items-center justify-between">
          <h3 className="text-base font-bold text-gray-900">Partager une adresse</h3>
          <button onClick={onClose}><X size={20} className="text-gray-400" /></button>
        </div>
        <div className="overflow-y-auto flex-1 px-6 py-4 space-y-3">
          <button
            onClick={sendGps}
            disabled={gpsLoading}
            className="w-full flex items-center gap-4 p-4 rounded-2xl border-2 border-gray-100 hover:border-[#6D28D9] hover:bg-purple-50 transition-all text-left disabled:opacity-60"
          >
            <div className="w-10 h-10 rounded-xl bg-blue-50 flex items-center justify-center shrink-0">
              {gpsLoading ? <Loader size={20} className="text-blue-600 animate-spin" /> : <Navigation size={20} className="text-blue-600" />}
            </div>
            <div><p className="font-semibold text-gray-900 text-sm">Ma position actuelle</p><p className="text-xs text-gray-400">Envoyer via GPS</p></div>
          </button>
          {addresses.filter(a => a.latitude && a.longitude).map(addr => (
            <button
              key={addr.id}
              onClick={() => { onSend(`📍 ${addr.label} — ${addr.city} : https://maps.google.com/?q=${addr.latitude},${addr.longitude}`); onClose(); }}
              className="w-full flex items-center gap-3 p-3 rounded-xl border border-gray-100 hover:border-[#6D28D9] hover:bg-purple-50 transition-all text-left"
            >
              <div className="w-8 h-8 rounded-lg bg-purple-50 flex items-center justify-center shrink-0">
                <MapPin size={14} className="text-[#6D28D9]" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="font-semibold text-gray-900 text-sm truncate">{addr.label}</p>
                <p className="text-xs text-gray-400 truncate">{addr.city}</p>
              </div>
              {addr.isDefault && <span className="text-xs text-[#6D28D9] font-semibold shrink-0">Défaut</span>}
            </button>
          ))}
          {addresses.length === 0 && <p className="text-xs text-center text-gray-400 py-4">Aucune adresse enregistrée. Ajoutez-en dans votre profil.</p>}
        </div>
      </div>
    </div>
  );
}

// ── Media Message Bubble ──────────────────────────────────────────────────────
function MediaBubble({ url, type, isMe }: { url: string; type: string; isMe: boolean }) {
  if (type === 'image') {
    return (
      <a href={url} target="_blank" rel="noopener noreferrer">
        <img
          src={url}
          alt="Image partagée"
          className="max-w-[220px] max-h-[200px] rounded-xl object-cover border border-white/20 cursor-pointer hover:opacity-90 transition-opacity"
          loading="lazy"
        />
      </a>
    );
  }
  if (type === 'video') {
    return (
      <video
        src={url}
        controls
        className="max-w-[220px] rounded-xl"
        style={{ maxHeight: 200 }}
      />
    );
  }
  // document
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className={`flex items-center gap-2 px-3 py-2 rounded-xl border ${isMe ? 'border-white/30 bg-white/10 text-white' : 'border-gray-200 bg-gray-50 text-gray-700'}`}
    >
      <FileText size={18} className={isMe ? 'text-white' : 'text-gray-500'} />
      <span className="text-sm font-medium truncate max-w-[160px]">Document</span>
      <Download size={14} className={isMe ? 'text-white/70' : 'text-gray-400'} />
    </a>
  );
}

// ── File Preview ──────────────────────────────────────────────────────────────
interface FilePreviewProps { file: File; onRemove: () => void; }

function FilePreview({ file, onRemove }: FilePreviewProps) {
  const [preview, setPreview] = useState<string | null>(null);
  useEffect(() => {
    if (IMAGE_TYPES.has(file.type)) {
      const url = URL.createObjectURL(file);
      setPreview(url);
      return () => URL.revokeObjectURL(url);
    }
  }, [file]);

  return (
    <div className="flex items-center gap-2 px-3 py-2 bg-purple-50 border border-purple-100 rounded-xl mx-4 mb-2">
      {preview
        ? <img src={preview} alt="" className="w-10 h-10 rounded-lg object-cover" />
        : VIDEO_TYPES.has(file.type)
        ? <Film size={20} className="text-[#6D28D9] shrink-0" />
        : <FileText size={20} className="text-[#6D28D9] shrink-0" />
      }
      <div className="flex-1 min-w-0">
        <p className="text-xs font-semibold text-gray-800 truncate">{file.name}</p>
        <p className="text-xs text-gray-400">{formatBytes(file.size)}</p>
      </div>
      <button onClick={onRemove} className="text-gray-400 hover:text-red-500 transition-colors">
        <X size={16} />
      </button>
    </div>
  );
}

// ── Main component ─────────────────────────────────────────────────────────────
export function ChatInterface({ taskerName, taskId, partnerSrc, onCall }: ChatInterfaceProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [newMessage, setNewMessage] = useState('');
  const [sending, setSending] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [callModal, setCallModal] = useState<'audio' | 'video' | null>(null);
  const [showLocationDrawer, setShowLocationDrawer] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!taskId) return;
    chatService.listMessages(taskId).then(setMessages).catch(() => setMessages([]));
  }, [taskId]);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

  const userId = apiClient.getUserId() ?? '';

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadError(null);
    if (!ALLOWED_TYPES.includes(file.type)) {
      setUploadError('Type de fichier non supporté. Formats : images, vidéos MP4/WebM, PDF.');
      return;
    }
    setPendingFile(file);
    e.target.value = '';
  };

  const sendMessage = async (text?: string) => {
    const body = (text ?? newMessage).trim();
    if (!body && !pendingFile) return;
    if (!taskId || sending || uploading) return;

    setSending(true);
    setUploadError(null);
    let mediaUrl: string | undefined;
    let mediaType: ChatMessage['mediaType'];

    if (pendingFile) {
      try {
        setUploading(true);
        setUploadProgress(0);
        const result = await chatService.uploadMedia(pendingFile, taskId);
        mediaUrl = result.secure_url;
        mediaType = result.media_type;
        setPendingFile(null);
      } catch (err) {
        setUploadError(err instanceof Error ? err.message : 'Échec de l\'envoi du fichier');
        setSending(false);
        setUploading(false);
        return;
      } finally {
        setUploading(false);
        setUploadProgress(0);
      }
    }

    if (!text) setNewMessage('');
    try {
      const sent = await chatService.sendMessage(taskId, body, mediaUrl, mediaType);
      setMessages(prev => [...prev, sent]);
    } catch {
      if (!text) setNewMessage(body);
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="flex flex-col h-full">
      {callModal && <CallModal type={callModal} onClose={() => setCallModal(null)} />}
      {showLocationDrawer && (
        <LocationDrawer
          onSend={t => { void sendMessage(t); }}
          onClose={() => setShowLocationDrawer(false)}
        />
      )}

      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        accept={ALLOWED_TYPES.join(',')}
        className="hidden"
        onChange={handleFileSelect}
      />

      {/* Header */}
      <div className="px-4 py-3 bg-white border-b border-gray-200 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Avatar name={taskerName || 'T'} size="sm" src={partnerSrc ?? undefined} />
          <div>
            <h4 className="font-semibold text-gray-900">{taskerName || 'Discussion'}</h4>
            <p className="text-xs text-green-600 flex items-center gap-1">
              <span className="w-2 h-2 bg-green-500 rounded-full inline-block" /> En ligne
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setCallModal('audio')}
            className="w-10 h-10 bg-gray-100 rounded-full flex items-center justify-center hover:bg-gray-200 transition-colors"
            title="Appel audio"
          >
            <Phone size={18} className="text-gray-600" />
          </button>
          <button
            onClick={() => setCallModal('video')}
            className="w-10 h-10 bg-[#6D28D9] rounded-full flex items-center justify-center hover:bg-[#5B21B6] transition-colors"
            title="Appel vidéo"
          >
            <Video size={18} className="text-white" />
          </button>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-auto px-4 py-4 space-y-3 bg-gray-50">
        {!taskId && <p className="text-xs text-center text-gray-400 py-8">Sélectionnez une tâche pour démarrer la conversation.</p>}
        {taskId && messages.length === 0 && <p className="text-xs text-center text-gray-400 py-8">Aucun message pour l'instant.</p>}
        {messages.map(msg => {
          const isMe = msg.senderId === userId;
          return (
            <div key={msg.id} className={`flex items-end gap-2 ${isMe ? 'justify-end' : 'justify-start'}`}>
              {!isMe && <Avatar name={taskerName || 'T'} size="xs" src={partnerSrc ?? undefined} />}
              <div className={`max-w-[75%] rounded-2xl px-4 py-2.5 ${isMe ? 'bg-[#6D28D9] text-white' : 'bg-white text-gray-900 border border-gray-200'}`}>
                {msg.mediaUrl && msg.mediaType && (
                  <div className="mb-2">
                    <MediaBubble url={msg.mediaUrl} type={msg.mediaType} isMe={isMe} />
                  </div>
                )}
                {msg.message && <p className="text-sm">{msg.message}</p>}
                <p className={`text-xs mt-1 ${isMe ? 'text-white/70' : 'text-gray-500'}`}>
                  {new Date(msg.createdAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </p>
              </div>
            </div>
          );
        })}
        <div ref={bottomRef} />
      </div>

      {/* Pending file preview */}
      {pendingFile && <FilePreview file={pendingFile} onRemove={() => setPendingFile(null)} />}

      {/* Upload error */}
      {uploadError && (
        <div className="mx-4 mb-2 flex items-center gap-2 bg-red-50 border border-red-100 rounded-xl px-3 py-2">
          <X size={14} className="text-red-500 shrink-0" />
          <p className="text-xs text-red-600">{uploadError}</p>
          <button onClick={() => setUploadError(null)} className="ml-auto text-red-400 hover:text-red-600"><X size={12} /></button>
        </div>
      )}

      {/* Upload progress */}
      {uploading && (
        <div className="mx-4 mb-2">
          <div className="h-1 bg-gray-200 rounded-full overflow-hidden">
            <div className="h-full bg-[#6D28D9] animate-pulse rounded-full" style={{ width: '60%' }} />
          </div>
          <p className="text-xs text-gray-400 mt-1 text-center">Envoi en cours…</p>
        </div>
      )}

      {/* Input bar */}
      <div className="px-3 py-3 bg-white border-t border-gray-200">
        <div className="flex items-center gap-2">
          {/* Media attachment */}
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={!taskId || uploading}
            className="w-9 h-9 rounded-full bg-gray-100 hover:bg-purple-50 hover:text-[#6D28D9] disabled:opacity-40 flex items-center justify-center transition-colors flex-shrink-0"
            title="Joindre un fichier"
          >
            <Paperclip size={17} className="text-gray-500" />
          </button>

          {/* Location share */}
          <button
            onClick={() => setShowLocationDrawer(true)}
            disabled={!taskId}
            className="w-9 h-9 rounded-full bg-gray-100 hover:bg-purple-50 hover:text-[#6D28D9] disabled:opacity-40 flex items-center justify-center transition-colors flex-shrink-0"
            title="Partager une adresse"
          >
            <MapPin size={17} className="text-gray-500" />
          </button>

          <input
            type="text"
            value={newMessage}
            onChange={e => setNewMessage(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); void sendMessage(); } }}
            placeholder="Écrire un message…"
            disabled={!taskId}
            className="flex-1 px-4 py-2.5 rounded-full border-2 border-gray-200 focus:border-[#6D28D9] focus:outline-none text-sm disabled:bg-gray-50"
          />

          <button
            onClick={() => void sendMessage()}
            disabled={(!newMessage.trim() && !pendingFile) || !taskId || sending || uploading}
            className="w-9 h-9 rounded-full bg-[#6D28D9] hover:bg-[#5B21B6] disabled:bg-gray-300 flex items-center justify-center transition-colors flex-shrink-0"
          >
            {sending || uploading
              ? <Loader size={16} className="text-white animate-spin" />
              : <Send size={16} className="text-white" />
            }
          </button>
        </div>
      </div>
    </div>
  );
}
