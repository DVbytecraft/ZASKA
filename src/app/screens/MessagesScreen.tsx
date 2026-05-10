import { useCallback, useEffect, useState } from 'react';
import { MessageSquare, RefreshCw, Search, Plus, ChevronRight } from 'lucide-react';
import { apiClient, taskService } from '@zaska/shared-services';
import type { Task } from '@zaska/shared-services';
import { Avatar } from '../components/Avatar';

// ── Types ──────────────────────────────────────────────────────────────────────

interface Conversation {
  /** The most relevant taskId for opening the chat */
  taskId: string;
  partnerId: string;
  partnerName: string;
  partnerAvatar?: string | null;
  /** Active task title or fallback */
  lastTaskTitle: string;
  /** Status of the most active task with this partner */
  status: Task['status'];
  /** How many tasks in total with this partner */
  taskCount: number;
  updatedAt?: string | null;
}

interface MessagesScreenProps {
  onOpenChat: (taskId: string) => void;
  onPostTask: () => void;
}

// ── Status badge ───────────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: Task['status'] }) {
  const map: Record<Task['status'], { label: string; cls: string }> = {
    ASSIGNED:          { label: 'En cours',    cls: 'bg-blue-50 text-blue-700' },
    PENDING_VALIDATION:{ label: 'À confirmer', cls: 'bg-amber-50 text-amber-700' },
    COMPLETED:         { label: 'Terminé',     cls: 'bg-green-50 text-green-700' },
    PAUSED:            { label: 'En pause',    cls: 'bg-gray-100 text-gray-500' },
    CANCELLED:         { label: 'Annulé',      cls: 'bg-red-50 text-red-400' },
    OPEN:              { label: 'Ouvert',      cls: 'bg-purple-50 text-purple-600' },
  };
  const b = map[status] ?? { label: status, cls: 'bg-gray-100 text-gray-500' };
  return (
    <span className={`shrink-0 text-[10px] font-bold px-2 py-0.5 rounded-lg ${b.cls}`}>
      {b.label}
    </span>
  );
}

// ── Task rank for "most important" conversation selection ─────────────────────

function taskRank(s: Task['status']): number {
  return s === 'ASSIGNED' ? 0 : s === 'PENDING_VALIDATION' ? 1 : s === 'OPEN' ? 2 : 3;
}

// ── Data loading ───────────────────────────────────────────────────────────────

async function loadConversations(myId: string): Promise<Conversation[]> {
  const [mine, assigned] = await Promise.all([
    taskService.listMyTasks(),
    taskService.listAssignedToMe(),
  ]);

  // Collect all tasks with a known other participant
  type Raw = { taskId: string; partnerId: string; title: string; status: Task['status']; updatedAt?: string | null };
  const raws: Raw[] = [
    ...mine
      .filter((t) => t.assignedTo && t.status !== 'CANCELLED')
      .map((t) => ({
        taskId: t.id,
        partnerId: t.assignedTo!,
        title: t.title || t.description.slice(0, 50),
        status: t.status,
        updatedAt: t.createdAt,
      })),
    ...assigned
      .filter((t) => t.status !== 'CANCELLED')
      .map((t) => ({
        taskId: t.id,
        partnerId: t.createdBy,
        title: t.title || t.description.slice(0, 50),
        status: t.status,
        updatedAt: t.createdAt,
      })),
  ];

  // Group by partnerId — keep ONE entry per person
  const byPartner = new Map<string, { best: Raw; count: number }>();
  for (const r of raws) {
    const existing = byPartner.get(r.partnerId);
    if (!existing) {
      byPartner.set(r.partnerId, { best: r, count: 1 });
    } else {
      existing.count++;
      // Replace with the more active/important task
      if (taskRank(r.status) < taskRank(existing.best.status)) {
        existing.best = r;
      }
    }
  }

  // Fetch partner profiles in parallel
  const entries = Array.from(byPartner.entries());
  const conversations: Conversation[] = await Promise.all(
    entries.map(async ([partnerId, { best, count }]) => {
      let partnerName = 'Utilisateur';
      let partnerAvatar: string | null = null;
      try {
        const p = await apiClient.get<{
          first_name?: string | null;
          last_name?: string | null;
          full_name?: string | null;
          avatar_url?: string | null;
        }>(`/users/${partnerId}`);
        partnerName =
          [p.first_name, p.last_name].filter(Boolean).join(' ') ||
          p.full_name ||
          'Utilisateur';
        partnerAvatar = p.avatar_url ?? null;
      } catch { /* keep defaults */ }

      return {
        taskId: best.taskId,
        partnerId,
        partnerName,
        partnerAvatar,
        lastTaskTitle: best.title,
        status: best.status,
        taskCount: count,
        updatedAt: best.updatedAt,
      };
    }),
  );

  // Sort: active first (ASSIGNED → PENDING_VALIDATION → OPEN → rest), then by date
  return conversations.sort((a, b) => {
    const rd = taskRank(a.status) - taskRank(b.status);
    if (rd !== 0) return rd;
    return (b.updatedAt ?? '').localeCompare(a.updatedAt ?? '');
  });
}

// ── Component ──────────────────────────────────────────────────────────────────

export function MessagesScreen({ onOpenChat, onPostTask }: MessagesScreenProps) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const myId = apiClient.getUserId() ?? '';

  const load = useCallback(async () => {
    if (!myId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await loadConversations(myId);
      setConversations(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erreur de chargement');
    } finally {
      setLoading(false);
    }
  }, [myId]);

  useEffect(() => { void load(); }, [load]);

  const filtered = search.trim()
    ? conversations.filter(
        (c) =>
          c.partnerName.toLowerCase().includes(search.toLowerCase()) ||
          c.lastTaskTitle.toLowerCase().includes(search.toLowerCase()),
      )
    : conversations;

  // ── Skeleton ─────────────────────────────────────────────────────────────
  if (loading && conversations.length === 0) {
    return (
      <div className="h-full flex flex-col bg-gray-50">
        <Header loading={loading} onRefresh={load} />
        <div className="px-4 pt-2 space-y-2">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="bg-white rounded-2xl p-4 flex items-center gap-3 animate-pulse">
              <div className="w-12 h-12 rounded-full bg-gray-200 shrink-0" />
              <div className="flex-1 space-y-2 min-w-0">
                <div className="h-3.5 bg-gray-200 rounded-lg w-2/5" />
                <div className="h-2.5 bg-gray-100 rounded-lg w-3/5" />
              </div>
              <div className="w-14 h-5 bg-gray-100 rounded-lg shrink-0" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col bg-gray-50">
      <Header loading={loading} onRefresh={load} search={search} onSearch={setSearch} />

      <div className="flex-1 overflow-auto">
        {error ? (
          <div className="flex flex-col items-center justify-center px-6 py-16 gap-4 text-center">
            <p className="text-sm text-red-500">{error}</p>
            <button
              onClick={() => void load()}
              className="px-6 py-2.5 bg-[#6D28D9] text-white rounded-xl text-sm font-semibold"
            >
              Réessayer
            </button>
          </div>
        ) : filtered.length === 0 ? (
          <EmptyState hasSearch={!!search.trim()} search={search} onPostTask={onPostTask} />
        ) : (
          <ul className="px-4 py-3 space-y-2">
            {filtered.map((conv) => (
              <li key={conv.partnerId}>
                <button
                  onClick={() => onOpenChat(conv.taskId)}
                  className="w-full bg-white rounded-2xl px-4 py-3.5 flex items-center gap-3 active:scale-[0.99] transition-all border border-gray-100 hover:border-[#6D28D9]/20 hover:shadow-sm text-left"
                >
                  {/* Avatar */}
                  <Avatar
                    name={conv.partnerName}
                    src={conv.partnerAvatar ?? undefined}
                    size="md"
                  />

                  {/* Info */}
                  <div className="flex-1 min-w-0">
                    <p className="font-semibold text-gray-900 text-sm truncate leading-tight">
                      {conv.partnerName}
                    </p>
                    <p className="text-xs text-gray-400 truncate mt-0.5 leading-tight">
                      {conv.lastTaskTitle}
                    </p>
                  </div>

                  {/* Right side */}
                  <div className="shrink-0 flex flex-col items-end gap-1">
                    <StatusBadge status={conv.status} />
                    {conv.taskCount > 1 && (
                      <span className="text-[10px] text-gray-400">
                        {conv.taskCount} tâches
                      </span>
                    )}
                  </div>

                  <ChevronRight size={15} className="text-gray-300 shrink-0" />
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

// ── Sub-components ─────────────────────────────────────────────────────────────

function Header({
  loading,
  onRefresh,
  search = '',
  onSearch,
}: {
  loading: boolean;
  onRefresh: () => void;
  search?: string;
  onSearch?: (v: string) => void;
}) {
  return (
    <div className="bg-white border-b border-gray-100 px-4 pt-10 pb-3 space-y-3">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Messages</h1>
        <button
          onClick={onRefresh}
          disabled={loading}
          className="w-9 h-9 rounded-full bg-gray-100 hover:bg-gray-200 flex items-center justify-center transition-colors disabled:opacity-40"
          aria-label="Rafraîchir"
        >
          <RefreshCw size={15} className={`text-gray-500 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {onSearch && (
        <div className="relative">
          <Search size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            type="search"
            value={search}
            onChange={(e) => onSearch(e.target.value)}
            placeholder="Rechercher…"
            className="w-full pl-9 pr-4 py-2.5 rounded-xl bg-gray-100 text-sm placeholder:text-gray-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#6D28D9]/30 transition-all"
          />
        </div>
      )}
    </div>
  );
}

function EmptyState({
  hasSearch,
  search,
  onPostTask,
}: {
  hasSearch: boolean;
  search: string;
  onPostTask: () => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center px-8 py-20 text-center h-full">
      <div className="w-20 h-20 rounded-full bg-purple-50 flex items-center justify-center mb-5">
        <MessageSquare size={34} className="text-[#6D28D9]" strokeWidth={1.5} />
      </div>
      {hasSearch ? (
        <>
          <h3 className="text-lg font-bold text-gray-900 mb-2">Aucun résultat</h3>
          <p className="text-sm text-gray-400">Aucune conversation ne correspond à « {search} »</p>
        </>
      ) : (
        <>
          <h3 className="text-lg font-bold text-gray-900 mb-2">Aucune conversation</h3>
          <p className="text-sm text-gray-400 mb-8 leading-relaxed max-w-xs">
            Vos conversations apparaissent ici dès qu'une tâche est acceptée par un prestataire.
          </p>
          <button
            onClick={onPostTask}
            className="flex items-center gap-2 px-6 py-3 bg-[#6D28D9] text-white rounded-2xl font-semibold text-sm shadow-lg hover:bg-[#5B21B6] active:scale-95 transition-all"
          >
            <Plus size={18} />
            Poster une tâche
          </button>
        </>
      )}
    </div>
  );
}
