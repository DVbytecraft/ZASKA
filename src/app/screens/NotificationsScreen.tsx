import { useEffect, useState } from 'react';
import { ArrowLeft, Bell, CheckCircle2, Info, AlertTriangle, RefreshCw, ChevronRight } from 'lucide-react';
import { Card } from '../components/Card';
import { apiClient } from '@zaska/shared-services';
import { useTranslation } from 'react-i18next';

interface Notification {
  id: string;
  type: 'info' | 'success' | 'warning';
  title: string;
  body: string;
  read: boolean;
  task_id?: string | null;
  created_at: string;
}

interface NotificationsScreenProps {
  onBack: () => void;
  onTaskDetail?: (taskId: string) => void;
  onTaskChat?: (taskId: string) => void;
  onViewApplicants?: (taskId: string) => void;
}

function NotifIcon({ type }: { type: Notification['type'] }) {
  if (type === 'success') return <CheckCircle2 size={20} className="text-green-600" />;
  if (type === 'warning') return <AlertTriangle size={20} className="text-amber-600" />;
  return <Info size={20} className="text-blue-600" />;
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  } catch {
    return iso;
  }
}

export function NotificationsScreen({ onBack, onTaskDetail, onTaskChat, onViewApplicants }: NotificationsScreenProps) {
  const { t } = useTranslation();
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    setLoading(true);
    setError(null);
    apiClient.get<Notification[]>('/notifications')
      .then(setNotifications)
      .catch((err) => {
        const msg = err instanceof Error ? err.message : '';
        if (msg.includes('404') || msg.includes('failed: 404')) {
          setNotifications([]);
        } else {
          setError(t('notifications.errorLoad'));
        }
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const handleNotifClick = (n: Notification) => {
    if (!n.task_id) return;
    apiClient.patch(`/notifications/${n.id}/read`, {}).catch(() => {});
    setNotifications(prev => prev.map(x => x.id === n.id ? { ...x, read: true } : x));
    // Route based on notification type
    if (n.title.startsWith('Message de') && onTaskChat) {
      onTaskChat(n.task_id);
    } else if (n.title === 'Nouvelle candidature' && onViewApplicants) {
      onViewApplicants(n.task_id);
    } else if (onTaskDetail) {
      onTaskDetail(n.task_id);
    }
  };

  return (
    <div className="h-full flex flex-col bg-gray-50">
      <div className="px-6 pt-8 pb-4 bg-white border-b border-gray-200">
        <div className="flex items-center gap-3">
          <button onClick={onBack} className="p-2 -ml-2 hover:bg-gray-100 rounded-full transition-colors" aria-label="Retour">
            <ArrowLeft size={24} className="text-gray-700" />
          </button>
          <h2 className="text-2xl font-bold text-gray-900">{t('notifications.title')}</h2>
        </div>
      </div>

      <div className="flex-1 overflow-auto p-6">
        {loading ? (
          <div className="space-y-3">
            {[1, 2, 3].map((i) => <div key={i} className="h-16 bg-gray-200 rounded-2xl animate-pulse" />)}
          </div>
        ) : error ? (
          <div className="flex flex-col items-center justify-center h-48 gap-3">
            <AlertTriangle size={40} className="text-red-400" />
            <p className="text-sm text-red-600">{error}</p>
            <button onClick={load} className="flex items-center gap-2 text-sm font-medium text-[#6D28D9] hover:underline">
              <RefreshCw size={16} /> {t('common.retry')}
            </button>
          </div>
        ) : notifications.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full pb-12 text-center">
            <Bell size={48} className="text-gray-300 mb-4" />
            <p className="text-lg font-semibold text-gray-700">{t('notifications.none')}</p>
            <p className="text-sm text-gray-500 mt-2">{t('notifications.noneSubtitle')}</p>
          </div>
        ) : (
          <div className="space-y-3">
            {notifications.map((n) => {
              const clickable = !!(n.task_id && (onTaskDetail || onTaskChat || onViewApplicants));
              return (
                <Card
                  key={n.id}
                  className={`transition-all ${n.read ? 'opacity-70' : ''} ${clickable ? 'cursor-pointer hover:shadow-md active:scale-[0.99]' : ''}`}
                  onClick={clickable ? () => handleNotifClick(n) : undefined}
                >
                  <div className="flex items-start gap-3">
                    <div className={`w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0 ${
                      n.type === 'success' ? 'bg-green-50' : n.type === 'warning' ? 'bg-amber-50' : 'bg-blue-50'
                    }`}>
                      <NotifIcon type={n.type} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-semibold text-gray-900 text-sm">{n.title}</p>
                      <p className="text-sm text-gray-600 mt-0.5">{n.body}</p>
                      <p className="text-xs text-gray-400 mt-1">{formatDate(n.created_at)}</p>
                    </div>
                    <div className="flex items-center gap-1 flex-shrink-0">
                      {!n.read && <div className="w-2 h-2 bg-[#6D28D9] rounded-full" />}
                      {clickable && <ChevronRight size={16} className="text-gray-400" />}
                    </div>
                  </div>
                </Card>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
