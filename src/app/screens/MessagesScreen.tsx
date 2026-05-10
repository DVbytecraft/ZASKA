import { useCallback, useEffect, useState } from 'react';
import { MessageSquare, RefreshCw, Search, Plus } from 'lucide-react';
import { apiClient, taskService } from '@zaska/shared-services';
import type { Task } from '@zaska/shared-services';
import { Avatar } from '../components/Avatar';
import { useTranslation } from 'react-i18next';

interface Conversation {
  taskId: string;
  taskTitle: string;
  taskStatus: Task['status'];
  partnerId: string;
  partnerName: string;
  partnerAvatar?: string | null;
  updatedAt?: string | null;
}

interface MessagesScreenProps {
  onOpenChat: (taskId: string) => void;
  onPostTask: () => void;
}

function statusBadge(status: Task['status']) {
  const map: Record<string, { label: string; cls: string }> = {
    ASSIGNED:          { label: 'En cours',    cls: 'bg-blue-50 text-blue-700' },
    PENDING_VALIDATION:{ label: 'À confirmer', cls: 'bg-amber-50 text-amber-700' },
    COMPLETED:         { label: 'Terminé',     cls: 'bg-green-50 text-green-700' },
    PAUSED:            { label: 'En pause',    cls: 'bg-gray-100 text-gray-500' },
    CANCELLED:         { label: 'Annulé',      cls: 'bg-red-50 text-red-500' },
    OPEN:              { label: 'Ouvert',      cls: 'bg-purple-50 text-purple-600' },
  };
  const b = map[status] ?? { label: status, cls: 'bg-gray-100 text-gray-500' };
  return (
    <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-lg ${b.cls}`}>
      {b.label}
    </span>
  );
}

export function MessagesScreen({ onOpenChat, onPostTask }: MessagesScreenProps) {
  const { t } = useTranslation();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const myId = apiClient.getUserId() ?? '';

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [mine, assigned] = await Promise.all([
        taskService.listMyTasks(),
        taskService.listAssignedToMe(),
      ]);

      // Conversations I created: need an assigned tasker
      const fromMine: Conversation[] = mine
        .filter((t) => t.assignedTo && t.status !== 'CANCELLED')
        .map((t) => ({
          taskId: t.id,
          taskTitle: t.title || t.description.slice(0, 50),
          taskStatus: t.status,
          partnerId: t.assignedTo!,
          partnerName: '',
          updatedAt: t.createdAt,
        }));

      // Conversations where I'm the tasker
      const fromAssigned: Conversation[] = assigned.map((t) => ({
        taskId: t.id,
        taskTitle: t.title || t.description.slice(0, 50),
        taskStatus: t.status,
        partnerId: t.createdBy,
        partnerName: '',
        updatedAt: t.createdAt,
      }));

      // Deduplicate by taskId
      const seen = new Set<string>();
      const all: Conversation[] = [];
      for (const c of [...fromMine, ...fromAssigned]) {
        if (!seen.has(c.taskId)) {
          seen.add(c.taskId);
          all.push(c);
        }
      }

      // Enrich with partner names/avatars
      const enriched = await Promise.all(
        all.map(async (c) => {
          try {
            const p = await apiClient.get<{
              first_name?: string | null;
              last_name?: string | null;
              full_name?: string | null;
              avatar_url?: string | null;
            }>(`/users/${c.partnerId}`);
            const name =
              [p.first_name, p.last_name].filter(Boolean).join(' ') ||
              p.full_name ||
              'Utilisateur';
            return { ...c, partnerName: name, partnerAvatar: p.avatar_url };
          } catch {
            return { ...c, partnerName: 'Utilisateur' };
          }
        }),
      );

      // Sort: active first, then by updatedAt desc
      enriched.sort((a, b) => {
        const rank = (s: Task['status']) =>
          s === 'ASSIGNED' ? 0 : s === 'PENDING_VALIDATION' ? 1 : 2;
        if (rank(a.taskStatus) !== rank(b.taskStatus)) return rank(a.taskStatus) - rank(b.taskStatus);
        return (b.updatedAt ?? '').localeCompare(a.updatedAt ?? '');
      });

      setConversations(enriched);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erreur de chargement');
    } finally {
      setLoading(false);
    }
  }, [myId]);

  useEffect(() => {
    void load();
  }, [load]);

  const filtered = search.trim()
    ? conversations.filter(
        (c) =>
          c.partnerName.toLowerCase().includes(search.toLowerCase()) ||
          c.taskTitle.toLowerCase().includes(search.toLowerCase()),
      )
    : conversations;

  return (
    <div className="h-full flex flex-col bg-gray-50">
      {/* Header */}
      <div className="px-6 pt-10 pb-4 bg-white border-b border-gray-100">
        <div className="flex items-center justify-between mb-4">
          <h1 className="text-2xl font-bold text-gray-900">{t('nav.messages')}</h1>
          <button
            onClick={load}
            disabled={loading}
            className="w-9 h-9 rounded-full bg-gray-100 hover:bg-gray-200 flex items-center justify-center transition-colors disabled:opacity-40"
            aria-label="Rafraîchir"
          >
            <RefreshCw size={15} className={`text-gray-500 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>

        {/* Search */}
        <div className="relative">
          <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Rechercher une conversation…"
            className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-gray-100 border border-transparent focus:bg-white focus:border-[#6D28D9] focus:outline-none text-sm transition-all"
          />
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto">
        {loading && conversations.length === 0 ? (
          // Skeleton
          <div className="px-6 py-4 space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="bg-white rounded-2xl p-4 flex items-center gap-3 animate-pulse">
                <div className="w-12 h-12 rounded-full bg-gray-200 flex-shrink-0" />
                <div className="flex-1 space-y-2">
                  <div className="h-3 bg-gray-200 rounded w-2/3" />
                  <div className="h-2 bg-gray-100 rounded w-1/2" />
                </div>
              </div>
            ))}
          </div>
        ) : error ? (
          <div className="px-6 py-12 flex flex-col items-center gap-3 text-center">
            <p className="text-sm text-red-500">{error}</p>
            <button
              onClick={load}
              className="px-6 py-2 bg-[#6D28D9] text-white rounded-xl text-sm font-semibold"
            >
              Réessayer
            </button>
          </div>
        ) : filtered.length === 0 ? (
          // Empty state
          <div className="flex flex-col items-center justify-center px-8 py-16 text-center h-full">
            <div className="w-20 h-20 rounded-full bg-purple-50 flex items-center justify-center mb-5">
              <MessageSquare size={36} className="text-[#6D28D9]" strokeWidth={1.5} />
            </div>
            {search ? (
              <>
                <h3 className="text-lg font-bold text-gray-900 mb-2">Aucun résultat</h3>
                <p className="text-sm text-gray-400">
                  Aucune conversation ne correspond à "{search}"
                </p>
              </>
            ) : (
              <>
                <h3 className="text-lg font-bold text-gray-900 mb-2">Aucune conversation</h3>
                <p className="text-sm text-gray-400 mb-6 leading-relaxed">
                  Les conversations apparaissent ici dès qu'une tâche est acceptée par un prestataire.
                </p>
                <button
                  onClick={onPostTask}
                  className="flex items-center gap-2 px-6 py-3 bg-[#6D28D9] text-white rounded-2xl font-semibold text-sm shadow-md hover:bg-[#5B21B6] transition-colors"
                >
                  <Plus size={18} />
                  Poster une tâche
                </button>
              </>
            )}
          </div>
        ) : (
          <div className="px-4 py-4 space-y-2">
            {filtered.map((conv) => (
              <button
                key={conv.taskId}
                onClick={() => onOpenChat(conv.taskId)}
                className="w-full bg-white rounded-2xl px-4 py-3.5 flex items-center gap-3 hover:shadow-md active:scale-[0.99] transition-all text-left border border-gray-100"
              >
                {/* Avatar */}
                <div className="flex-shrink-0">
                  <Avatar
                    name={conv.partnerName || 'U'}
                    src={conv.partnerAvatar ?? undefined}
                    size="md"
                  />
                </div>

                {/* Info */}
                <div className="flex-1 min-w-0">
                  <p className="font-semibold text-gray-900 text-sm truncate">{conv.partnerName}</p>
                  <p className="text-xs text-gray-400 truncate mt-0.5">{conv.taskTitle}</p>
                </div>

                {/* Status */}
                <div className="flex-shrink-0">{statusBadge(conv.taskStatus)}</div>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
