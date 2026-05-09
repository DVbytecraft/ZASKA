import React, { useEffect, useState, useCallback } from 'react';
import { Card } from '../components/Card';
import { Button } from '../components/Button';
import { Avatar } from '../components/Avatar';
import {
  CheckCircle2, Activity, Clock, AlertCircle, RefreshCw, Users,
  Briefcase, Send, XCircle, ChevronRight, Pause, Play, Trash2, MessageSquare,
} from 'lucide-react';
import { taskService, apiClient } from '@zaska/shared-services';
import type { Task, TaskApplication } from '@zaska/shared-services';
import { useTranslation } from 'react-i18next';
import type { TFunction } from 'i18next';
import { PriceDisplay } from '../components/PriceDisplay';

interface TasksTabScreenProps {
  onTaskClick: (taskId: string) => void;
  onViewApplicants?: (taskId: string) => void;
  onPostTask?: () => void;
  onChatOpen?: (taskId: string) => void;
}

type RootTab = 'client' | 'missions' | 'messages';

// ── Status helpers ────────────────────────────────────────────────────────────
function taskStatusLabel(status: Task['status'], t: TFunction) {
  if (status === 'COMPLETED') return t('tasks.statusCompleted');
  if (status === 'ASSIGNED') return t('tasks.statusAssigned');
  if (status === 'PENDING_VALIDATION') return t('tasks.statusValidation');
  if (status === 'PAUSED') return t('tasks.statusPaused');
  return t('tasks.statusOpen');
}

function taskStatusClass(status: Task['status']) {
  if (status === 'COMPLETED') return 'bg-green-50 text-green-700';
  if (status === 'ASSIGNED') return 'bg-blue-50 text-blue-700';
  if (status === 'PENDING_VALIDATION') return 'bg-amber-50 text-amber-700';
  if (status === 'PAUSED') return 'bg-gray-100 text-gray-500';
  return 'bg-purple-50 text-purple-700';
}

function appStatusLabel(status: TaskApplication['status'], t: TFunction) {
  if (status === 'accepted') return t('tasks.appAccepted');
  if (status === 'rejected') return t('tasks.appRejected');
  return t('tasks.appPending');
}

function appStatusClass(status: TaskApplication['status']) {
  if (status === 'accepted') return 'bg-green-50 text-green-700';
  if (status === 'rejected') return 'bg-red-50 text-red-700';
  return 'bg-amber-50 text-amber-700';
}

function appStatusIcon(status: TaskApplication['status']) {
  if (status === 'accepted') return <CheckCircle2 size={16} className="text-green-600" />;
  if (status === 'rejected') return <XCircle size={16} className="text-red-500" />;
  return <Clock size={16} className="text-amber-500" />;
}

// ── Skeleton ──────────────────────────────────────────────────────────────────
function Skeletons() {
  return (
    <div className="space-y-3">
      {[1, 2, 3].map((i) => <div key={i} className="h-24 bg-gray-200 rounded-2xl animate-pulse" />)}
    </div>
  );
}

// ── Empty state ───────────────────────────────────────────────────────────────
function Empty({ icon, message, cta, onCta }: { icon: React.ReactNode; message: string; cta?: string; onCta?: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center h-48 gap-3">
      <div className="text-gray-200">{icon}</div>
      <p className="text-sm text-gray-400 text-center">{message}</p>
      {cta && onCta && (
        <button onClick={onCta} className="text-sm font-semibold text-[#6D28D9] hover:underline">{cta}</button>
      )}
    </div>
  );
}

// ── Error state ───────────────────────────────────────────────────────────────
function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  const { t } = useTranslation();
  return (
    <div className="flex flex-col items-center justify-center h-48 gap-3">
      <AlertCircle size={40} className="text-red-400" />
      <p className="text-sm text-red-600 text-center">{message}</p>
      <button onClick={onRetry} className="flex items-center gap-2 text-sm font-medium text-[#6D28D9] hover:underline">
        <RefreshCw size={16} /> {t('common.retry')}
      </button>
    </div>
  );
}

// ── Client tab ────────────────────────────────────────────────────────────────
function ClientTab({
  onTaskClick,
  onViewApplicants,
  onPostTask,
}: Pick<TasksTabScreenProps, 'onTaskClick' | 'onViewApplicants' | 'onPostTask'>) {
  const { t } = useTranslation();
  const [filter, setFilter] = useState<'all' | 'active' | 'completed'>('all');
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionTaskId, setActionTaskId] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    taskService.listMyTasks()
      .then(setTasks)
      .catch((err) => setError(err instanceof Error ? err.message : 'Erreur de chargement'))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  const handlePause = async (e: React.MouseEvent, taskId: string) => {
    e.stopPropagation();
    setActionTaskId(taskId);
    try { await taskService.pauseTask(taskId); load(); } catch { /* ignore */ }
    finally { setActionTaskId(null); }
  };

  const handleReactivate = async (e: React.MouseEvent, taskId: string) => {
    e.stopPropagation();
    setActionTaskId(taskId);
    try { await taskService.reactivateTask(taskId); load(); } catch { /* ignore */ }
    finally { setActionTaskId(null); }
  };

  const handleDelete = async (taskId: string) => {
    setActionTaskId(taskId);
    try { await taskService.deleteTask(taskId); load(); } catch { /* ignore */ }
    finally { setActionTaskId(null); setConfirmDelete(null); }
  };

  const filtered = tasks.filter((t) => {
    if (filter === 'active') return !['COMPLETED'].includes(t.status);
    if (filter === 'completed') return t.status === 'COMPLETED';
    return true;
  });

  const statusIcon = (status: Task['status']) => {
    if (status === 'COMPLETED') return <CheckCircle2 size={20} className="text-green-600" />;
    if (status === 'ASSIGNED') return <Activity size={20} className="text-blue-600" />;
    if (status === 'PENDING_VALIDATION') return <Clock size={20} className="text-amber-500" />;
    if (status === 'PAUSED') return <Pause size={20} className="text-gray-400" />;
    return <Clock size={20} className="text-purple-600" />;
  };

  const statusIconBg = (status: Task['status']) => {
    if (status === 'COMPLETED') return 'bg-green-50';
    if (status === 'ASSIGNED') return 'bg-blue-50';
    if (status === 'PENDING_VALIDATION') return 'bg-amber-50';
    if (status === 'PAUSED') return 'bg-gray-100';
    return 'bg-purple-50';
  };

  return (
    <div className="px-6 py-4">
      {/* Delete confirm modal */}
      {confirmDelete && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-end justify-center pb-8 px-6">
          <div className="bg-white rounded-2xl w-full max-w-sm p-6 shadow-2xl">
            <h3 className="font-bold text-gray-900 text-lg mb-2">{t('tasks.deleteConfirm')}</h3>
            <p className="text-sm text-gray-500 mb-5">{t('tasks.deleteWarning')}</p>
            <div className="flex gap-3">
              <button
                onClick={() => setConfirmDelete(null)}
                className="flex-1 py-3 border-2 border-gray-200 rounded-xl text-sm font-semibold text-gray-700 hover:bg-gray-50"
              >
                {t('common.cancel')}
              </button>
              <button
                onClick={() => handleDelete(confirmDelete)}
                disabled={actionTaskId === confirmDelete}
                className="flex-1 py-3 bg-red-600 text-white rounded-xl text-sm font-semibold hover:bg-red-700 disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {actionTaskId === confirmDelete
                  ? <RefreshCw size={14} className="animate-spin" />
                  : <><Trash2 size={14} /> {t('tasks.delete')}</>}
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="flex items-center justify-between mb-4">
        <div className="flex gap-2">
          {(['all', 'active', 'completed'] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
                filter === f ? 'bg-[#6D28D9] text-white' : 'bg-white text-gray-600 border border-gray-200'
              }`}
            >
              {f === 'all' ? t('common.all') : f === 'active' ? t('common.active') : t('common.completed')}
            </button>
          ))}
        </div>
        <button onClick={load} className="w-8 h-8 rounded-full bg-gray-100 hover:bg-gray-200 flex items-center justify-center transition-colors">
          <RefreshCw size={14} className="text-gray-500" />
        </button>
      </div>

      {loading ? <Skeletons /> : error ? (
        <ErrorState message={error} onRetry={load} />
      ) : filtered.length === 0 ? (
        <Empty
          icon={<Clock size={40} />}
          message={t('tasks.noTasks')}
          cta={t('tasks.publish')}
          onCta={onPostTask}
        />
      ) : (
        <div className="space-y-3">
          {filtered.map((task) => (
            <Card key={task.id} onClick={() => onTaskClick(task.id)} className="hover:shadow-lg transition-all cursor-pointer">
              <div className="flex items-start justify-between mb-2">
                <div className="flex items-center gap-3">
                  <div className={`w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 ${statusIconBg(task.status)}`}>
                    {statusIcon(task.status)}
                  </div>
                  <div className="min-w-0">
                    <p className="font-medium text-gray-900 truncate max-w-[150px]">
                      {task.title || task.description.slice(0, 40)}
                    </p>
                    <PriceDisplay amount={Number(task.price)} currency={task.currency} compact className="text-xs text-gray-500" />
                  </div>
                </div>
                <span className={`text-xs font-semibold px-2.5 py-1 rounded-lg flex-shrink-0 ${taskStatusClass(task.status)}`}>
                  {taskStatusLabel(task.status, t)}
                </span>
              </div>

              {/* View applicants — OPEN only */}
              {task.status === 'OPEN' && onViewApplicants && (
                <button
                  onClick={(e) => { e.stopPropagation(); onViewApplicants(task.id); }}
                  className="w-full mt-2 flex items-center justify-center gap-2 px-4 py-2 bg-[#6D28D9] text-white rounded-lg font-medium text-sm hover:bg-[#5B21B6] transition-colors"
                >
                  <Users size={15} /> {t('tasks.viewApplicants')}
                </button>
              )}

              {/* Actions — only for OPEN or PAUSED tasks */}
              {(task.status === 'OPEN' || task.status === 'PAUSED') && (
                <div className="flex gap-2 mt-2 pt-2 border-t border-gray-100">
                  {task.status === 'OPEN' ? (
                    <button
                      onClick={(e) => handlePause(e, task.id)}
                      disabled={actionTaskId === task.id}
                      className="flex-1 flex items-center justify-center gap-1.5 py-2 rounded-lg text-xs font-semibold text-gray-600 bg-gray-100 hover:bg-gray-200 disabled:opacity-50 transition-colors"
                    >
                      {actionTaskId === task.id
                        ? <RefreshCw size={12} className="animate-spin" />
                        : <><Pause size={12} /> {t('tasks.pause')}</>}
                    </button>
                  ) : (
                    <button
                      onClick={(e) => handleReactivate(e, task.id)}
                      disabled={actionTaskId === task.id}
                      className="flex-1 flex items-center justify-center gap-1.5 py-2 rounded-lg text-xs font-semibold text-green-700 bg-green-50 hover:bg-green-100 disabled:opacity-50 transition-colors"
                    >
                      {actionTaskId === task.id
                        ? <RefreshCw size={12} className="animate-spin" />
                        : <><Play size={12} /> {t('tasks.republish')}</>}
                    </button>
                  )}
                  <button
                    onClick={(e) => { e.stopPropagation(); setConfirmDelete(task.id); }}
                    disabled={actionTaskId === task.id}
                    className="flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg text-xs font-semibold text-red-600 bg-red-50 hover:bg-red-100 disabled:opacity-50 transition-colors"
                  >
                    <Trash2 size={12} /> {t('tasks.delete')}
                  </button>
                </div>
              )}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Missions tab ──────────────────────────────────────────────────────────────
function MissionsTab({ onTaskClick }: { onTaskClick: (taskId: string) => void }) {
  const { t } = useTranslation();
  const [assignedTasks, setAssignedTasks] = useState<Task[]>([]);
  const [applications, setApplications] = useState<TaskApplication[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    Promise.all([
      taskService.listAssignedToMe(),
      taskService.getMyApplications(),
    ])
      .then(([tasks, apps]) => {
        setAssignedTasks(tasks);
        setApplications(apps);
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Erreur de chargement'))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  if (loading) return <div className="px-6 py-4"><Skeletons /></div>;
  if (error) return <div className="px-6 py-4"><ErrorState message={error} onRetry={load} /></div>;

  const pendingApps = applications.filter(a => a.status === 'pending');
  const decidedApps = applications.filter(a => a.status !== 'pending');

  const isEmpty = assignedTasks.length === 0 && applications.length === 0;

  return (
    <div className="px-6 py-4 space-y-4">
      <div className="flex justify-end">
        <button onClick={load} className="w-8 h-8 rounded-full bg-gray-100 hover:bg-gray-200 flex items-center justify-center transition-colors">
          <RefreshCw size={14} className="text-gray-500" />
        </button>
      </div>

      {isEmpty && (
        <Empty
          icon={<Briefcase size={40} />}
          message={t('tasks.noMissions')}
        />
      )}

      {/* Active missions */}
      {assignedTasks.length > 0 && (
        <section>
          <div className="flex items-center gap-2 mb-3">
            <span className="w-2 h-2 rounded-full bg-blue-500" />
            <p className="text-xs font-bold text-gray-500 uppercase tracking-wider">
              {t('tasks.missionsInProgress', { count: assignedTasks.length })}
            </p>
          </div>
          <div className="space-y-3">
            {assignedTasks.map((task) => (
              <Card key={task.id} onClick={() => onTaskClick(task.id)} className="hover:shadow-lg cursor-pointer border-l-4 border-blue-400">
                <div className="flex items-center justify-between">
                  <div className="min-w-0 flex-1">
                    <p className="font-semibold text-gray-900 truncate">
                      {task.title || task.description.slice(0, 50)}
                    </p>
                    <div className="flex items-baseline gap-1 text-xs text-gray-500 mt-0.5">
                      <PriceDisplay amount={Number(task.price)} currency={task.currency} compact />
                      {task.address && <span>· {task.address}</span>}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 ml-2 flex-shrink-0">
                    <span className="text-xs font-semibold px-2 py-1 rounded-lg bg-blue-50 text-blue-700">
                      {t('tasks.statusAssigned')}
                    </span>
                    <ChevronRight size={16} className="text-gray-400" />
                  </div>
                </div>
              </Card>
            ))}
          </div>
        </section>
      )}

      {/* Pending applications */}
      {pendingApps.length > 0 && (
        <section>
          <div className="flex items-center gap-2 mb-3">
            <span className="w-2 h-2 rounded-full bg-amber-400" />
            <p className="text-xs font-bold text-gray-500 uppercase tracking-wider">
              {t('tasks.pendingApps', { count: pendingApps.length })}
            </p>
          </div>
          <div className="space-y-3">
            {pendingApps.map((app) => (
              <Card key={app.id} className="border-l-4 border-amber-300">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2 min-w-0">
                    {appStatusIcon(app.status)}
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-gray-800 truncate">Tâche #{app.taskId.slice(0, 8)}</p>
                      {app.proposedPrice != null && (
                        <p className="text-xs text-gray-500">
                          {t('tasks.proposedPrice')} : {Number(app.proposedPrice).toLocaleString()} {app.currency}
                        </p>
                      )}
                      {app.message && (
                        <p className="text-xs text-gray-400 mt-0.5 line-clamp-1">{app.message}</p>
                      )}
                    </div>
                  </div>
                  <span className={`text-xs font-semibold px-2 py-1 rounded-lg flex-shrink-0 ${appStatusClass(app.status)}`}>
                    {appStatusLabel(app.status, t)}
                  </span>
                </div>
              </Card>
            ))}
          </div>
        </section>
      )}

      {/* Decided applications (accepted/rejected) */}
      {decidedApps.length > 0 && (
        <section>
          <div className="flex items-center gap-2 mb-3">
            <span className="w-2 h-2 rounded-full bg-gray-400" />
            <p className="text-xs font-bold text-gray-500 uppercase tracking-wider">
              {t('tasks.appHistory', { count: decidedApps.length })}
            </p>
          </div>
          <div className="space-y-2">
            {decidedApps.map((app) => (
              <div
                key={app.id}
                onClick={() => app.status === 'accepted' ? onTaskClick(app.taskId) : undefined}
                className={`flex items-center justify-between px-4 py-3 rounded-xl border ${
                  app.status === 'accepted' ? 'bg-green-50 border-green-100 cursor-pointer hover:shadow-md' : 'bg-gray-50 border-gray-100'
                }`}
              >
                <div className="flex items-center gap-2 min-w-0">
                  {appStatusIcon(app.status)}
                  <span className="text-sm font-medium text-gray-700 truncate">
                    Tâche #{app.taskId.slice(0, 8)}
                  </span>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  <span className={`text-xs font-semibold px-2 py-1 rounded-lg ${appStatusClass(app.status)}`}>
                    {appStatusLabel(app.status, t)}
                  </span>
                  {app.status === 'accepted' && <ChevronRight size={14} className="text-green-600" />}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

// ── Messages tab ──────────────────────────────────────────────────────────────
interface ConversationEntry {
  taskId: string;
  title: string;
  status: Task['status'];
  partnerId: string;
  partnerName: string;
  partnerSrc?: string | null;
  updatedAt?: string | null;
}

function MessagesTab({ onChatOpen }: { onChatOpen?: (taskId: string) => void }) {
  const { t } = useTranslation();
  const [conversations, setConversations] = useState<ConversationEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const myId = apiClient.getUserId() ?? '';

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [mine, assigned] = await Promise.all([
        taskService.listMyTasks(),
        taskService.listAssignedToMe(),
      ]);

      // Tasks I created that have an assigned tasker
      const fromMine = mine
        .filter(t => t.assignedTo && !['OPEN', 'CANCELLED'].includes(t.status))
        .map(t => ({ taskId: t.id, title: t.title || t.description.slice(0, 40), status: t.status, partnerId: t.assignedTo!, partnerName: '', updatedAt: t.createdAt }));

      // Tasks assigned to me (I'm the tasker)
      const fromAssigned = assigned.map(t => ({
        taskId: t.id,
        title: t.title || t.description.slice(0, 40),
        status: t.status,
        partnerId: t.createdBy,
        partnerName: '',
        updatedAt: t.createdAt,
      }));

      // Deduplicate by taskId
      const seen = new Set<string>();
      const all: ConversationEntry[] = [];
      for (const c of [...fromMine, ...fromAssigned]) {
        if (!seen.has(c.taskId)) { seen.add(c.taskId); all.push(c); }
      }

      // Fetch partner names
      const enriched = await Promise.all(all.map(async (c) => {
        try {
          const profile = await apiClient.get<{ first_name?: string | null; last_name?: string | null; full_name?: string | null; avatar_url?: string | null }>(`/users/${c.partnerId}`);
          const name = [profile.first_name, profile.last_name].filter(Boolean).join(' ') || profile.full_name || 'Utilisateur';
          return { ...c, partnerName: name, partnerSrc: profile.avatar_url };
        } catch {
          return { ...c, partnerName: 'Utilisateur' };
        }
      }));

      setConversations(enriched);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erreur de chargement');
    } finally {
      setLoading(false);
    }
  }, [myId]);

  useEffect(() => { void load(); }, [load]);

  if (loading) return <div className="px-6 py-4"><Skeletons /></div>;
  if (error) return <div className="px-6 py-4"><ErrorState message={error} onRetry={load} /></div>;
  if (conversations.length === 0) return (
    <div className="px-6 py-4">
      <Empty icon={<MessageSquare size={40} />} message={t('tasks.noMessages')} />
    </div>
  );

  return (
    <div className="px-6 py-4 space-y-3">
      <div className="flex justify-end">
        <button onClick={load} className="w-8 h-8 rounded-full bg-gray-100 hover:bg-gray-200 flex items-center justify-center transition-colors">
          <RefreshCw size={14} className="text-gray-500" />
        </button>
      </div>
      {conversations.map(conv => (
        <Card
          key={conv.taskId}
          onClick={() => onChatOpen?.(conv.taskId)}
          className="hover:shadow-lg cursor-pointer transition-all"
        >
          <div className="flex items-center gap-3">
            <Avatar name={conv.partnerName || 'U'} src={conv.partnerSrc ?? undefined} size="md" />
            <div className="flex-1 min-w-0">
              <p className="font-semibold text-gray-900 truncate">{conv.partnerName}</p>
              <p className="text-xs text-gray-400 truncate">{conv.title}</p>
            </div>
            <div className="flex flex-col items-end gap-1 flex-shrink-0">
              <span className={`text-xs font-semibold px-2 py-0.5 rounded-lg ${
                conv.status === 'ASSIGNED' ? 'bg-blue-50 text-blue-700' :
                conv.status === 'PENDING_VALIDATION' ? 'bg-amber-50 text-amber-700' :
                conv.status === 'COMPLETED' ? 'bg-green-50 text-green-700' : 'bg-gray-100 text-gray-500'
              }`}>
                {conv.status === 'ASSIGNED' ? t('tasks.statusAssigned') :
                 conv.status === 'PENDING_VALIDATION' ? t('tasks.statusValidation') :
                 conv.status === 'COMPLETED' ? t('tasks.statusCompleted') : conv.status}
              </span>
              <ChevronRight size={16} className="text-gray-400" />
            </div>
          </div>
        </Card>
      ))}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────
export function TasksTabScreen({ onTaskClick, onViewApplicants, onPostTask, onChatOpen }: TasksTabScreenProps) {
  const { t } = useTranslation();
  const [rootTab, setRootTab] = useState<RootTab>('client');

  return (
    <div className="h-full overflow-auto pb-24 bg-gray-50">
      {/* Header */}
      <div className="px-6 pt-8 pb-4 bg-gradient-to-br from-[#6D28D9] to-[#5B21B6]">
        <div className="flex items-center justify-between mb-4">
          <h1 className="text-2xl font-bold text-white">{t('tasks.myTasks')}</h1>
          {onPostTask && (
            <Button size="sm" onClick={onPostTask}>
              <Send size={14} className="mr-1" /> {t('tasks.publish')}
            </Button>
          )}
        </div>

        {/* Tab switcher */}
        <div className="flex bg-white/15 rounded-xl p-1 gap-1">
          <button
            onClick={() => setRootTab('client')}
            className={`flex-1 flex items-center justify-center gap-1.5 py-2.5 rounded-lg text-xs font-semibold transition-all ${
              rootTab === 'client' ? 'bg-white text-[#6D28D9] shadow-sm' : 'text-white/80 hover:text-white'
            }`}
          >
            <Users size={14} />
            {t('tasks.client')}
          </button>
          <button
            onClick={() => setRootTab('missions')}
            className={`flex-1 flex items-center justify-center gap-1.5 py-2.5 rounded-lg text-xs font-semibold transition-all ${
              rootTab === 'missions' ? 'bg-white text-[#6D28D9] shadow-sm' : 'text-white/80 hover:text-white'
            }`}
          >
            <Briefcase size={14} />
            {t('tasks.missions')}
          </button>
          <button
            onClick={() => setRootTab('messages')}
            className={`flex-1 flex items-center justify-center gap-1.5 py-2.5 rounded-lg text-xs font-semibold transition-all ${
              rootTab === 'messages' ? 'bg-white text-[#6D28D9] shadow-sm' : 'text-white/80 hover:text-white'
            }`}
          >
            <MessageSquare size={14} />
            {t('tasks.messages')}
          </button>
        </div>
      </div>

      {rootTab === 'client' && (
        <ClientTab onTaskClick={onTaskClick} onViewApplicants={onViewApplicants} onPostTask={onPostTask} />
      )}
      {rootTab === 'missions' && (
        <MissionsTab onTaskClick={onTaskClick} />
      )}
      {rootTab === 'messages' && (
        <MessagesTab onChatOpen={onChatOpen} />
      )}
    </div>
  );
}
