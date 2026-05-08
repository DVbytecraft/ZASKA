import { useEffect, useState, useMemo } from 'react';
import {
  Search, RefreshCw, AlertCircle, Filter, Eye,
  UserCheck, XCircle, Loader2
} from 'lucide-react';
import { DataTable } from '../components/DataTable';
import { ConfirmModal } from '../components/ConfirmModal';
import { SlidePanel } from '../components/SlidePanel';
import { TaskStatusBadge } from '../components/StatusBadge';
import { adminApi, type AdminTask } from '../adminApi';

interface PendingAction {
  type: 'forceAssign' | 'cancel';
  task: AdminTask;
}

function TaskDetailPanel({ task, onClose, onAction }: { task: AdminTask | null; onClose: () => void; onAction: () => void }) {
  const [assigning, setAssigning] = useState(false);
  const [taskerId, setTaskerId] = useState('');
  const [assignError, setAssignError] = useState('');
  const [cancelling, setCancelling] = useState(false);

  const handleForceAssign = async () => {
    if (!task || !taskerId.trim()) return;
    setAssigning(true);
    setAssignError('');
    try {
      await adminApi.forceAssignTask(task.id, taskerId.trim());
      onAction();
      onClose();
    } catch (e) {
      setAssignError(e instanceof Error ? e.message : 'Échec de l\'assignation');
    } finally {
      setAssigning(false);
    }
  };

  const handleCancel = async () => {
    if (!task) return;
    setCancelling(true);
    try {
      await adminApi.cancelTask(task.id, 'Annulé par l\'admin');
      onAction();
      onClose();
    } catch {}
    finally { setCancelling(false); }
  };

  return (
    <SlidePanel
      open={!!task}
      title={task?.title ?? 'Détail de la tâche'}
      subtitle={task ? `${task.price} ${task.currency} · ${task.status}` : undefined}
      onClose={onClose}
      footer={
        task && task.status !== 'COMPLETED' && task.status !== 'CANCELLED' ? (
          <div className="flex gap-3">
            <button
              onClick={handleCancel}
              disabled={cancelling}
              className="flex items-center gap-2 px-4 py-2.5 rounded-xl border border-red-200 text-red-600 text-sm font-semibold hover:bg-red-50 transition-colors"
            >
              {cancelling ? <Loader2 size={14} className="animate-spin" /> : <XCircle size={14} />}
              Annuler la tâche
            </button>
          </div>
        ) : null
      }
    >
      {task && (
        <div className="divide-y divide-gray-100">
          <div className="px-6 py-5 space-y-4">
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Description</p>
              <p className="text-sm text-gray-700">{task.description}</p>
            </div>
            <div className="grid grid-cols-2 gap-4">
              {[
                { label: 'Statut', value: <TaskStatusBadge status={task.status} size="md" /> },
                { label: 'Prix', value: `${Number(task.price).toLocaleString()} ${task.currency}` },
                { label: 'Créé par', value: task.created_by.slice(0, 12) + '…' },
                { label: 'Assigné à', value: task.assigned_to ? task.assigned_to.slice(0, 12) + '…' : '—' },
                { label: 'Date', value: new Date(task.created_at).toLocaleDateString('fr-FR') },
                { label: 'Localisation', value: task.latitude != null ? `${task.latitude.toFixed(3)}, ${task.longitude?.toFixed(3)}` : '—' },
              ].map(({ label, value }) => (
                <div key={label}>
                  <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide">{label}</p>
                  <div className="text-sm font-medium text-gray-900 mt-0.5">{value}</div>
                </div>
              ))}
            </div>
          </div>

          {task.status === 'OPEN' && (
            <div className="px-6 py-5">
              <h3 className="text-sm font-bold text-gray-900 mb-3 flex items-center gap-2">
                <UserCheck size={16} className="text-[#6D28D9]" />
                Assigner manuellement
              </h3>
              <div className="space-y-3">
                <div>
                  <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1.5">
                    ID du tasker
                  </label>
                  <input
                    type="text"
                    value={taskerId}
                    onChange={(e) => setTaskerId(e.target.value)}
                    placeholder="UUID du tasker..."
                    className="w-full px-3 py-2.5 border-2 border-gray-200 rounded-xl text-sm focus:border-[#6D28D9] focus:outline-none"
                  />
                </div>
                {assignError && <p className="text-xs text-red-600">{assignError}</p>}
                <button
                  onClick={handleForceAssign}
                  disabled={!taskerId.trim() || assigning}
                  className="w-full py-2.5 rounded-xl bg-[#6D28D9] text-white text-sm font-bold hover:bg-[#5B21B6] disabled:opacity-50 transition-colors flex items-center justify-center gap-2"
                >
                  {assigning ? <Loader2 size={14} className="animate-spin" /> : <UserCheck size={14} />}
                  Forcer l'assignation
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </SlidePanel>
  );
}

export function TasksPage() {
  const [tasks, setTasks] = useState<AdminTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [selectedTask, setSelectedTask] = useState<AdminTask | null>(null);
  const [pendingCancel, setPendingCancel] = useState<AdminTask | null>(null);
  const [cancelLoading, setCancelLoading] = useState(false);

  const load = () => {
    setLoading(true);
    setError(null);
    adminApi.getTasks()
      .then(setTasks)
      .catch((e) => setError(e instanceof Error ? e.message : 'Erreur'))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    return tasks.filter((t) => {
      const matchSearch = !q || t.title.toLowerCase().includes(q) || t.description.toLowerCase().includes(q) || t.id.toLowerCase().includes(q);
      const matchStatus = !statusFilter || t.status === statusFilter;
      return matchSearch && matchStatus;
    });
  }, [tasks, search, statusFilter]);

  const stats = useMemo(() => ({
    total: tasks.length,
    open: tasks.filter(t => t.status === 'OPEN').length,
    assigned: tasks.filter(t => t.status === 'ASSIGNED').length,
    completed: tasks.filter(t => t.status === 'COMPLETED').length,
    cancelled: tasks.filter(t => t.status === 'CANCELLED').length,
  }), [tasks]);

  const handleCancelConfirm = async (reason: string) => {
    if (!pendingCancel) return;
    setCancelLoading(true);
    try {
      await adminApi.cancelTask(pendingCancel.id, reason);
      setTasks(prev => prev.map(t => t.id === pendingCancel.id ? { ...t, status: 'CANCELLED' } : t));
      setPendingCancel(null);
    } catch {}
    finally { setCancelLoading(false); }
  };

  const STATUS_TABS = [
    { value: '', label: 'Toutes', count: stats.total },
    { value: 'OPEN', label: 'Ouvertes', count: stats.open },
    { value: 'ASSIGNED', label: 'Assignées', count: stats.assigned },
    { value: 'COMPLETED', label: 'Terminées', count: stats.completed },
    { value: 'CANCELLED', label: 'Annulées', count: stats.cancelled },
  ];

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Tâches</h2>
          <p className="text-sm text-gray-600">Supervision et gestion de toutes les tâches</p>
        </div>
        <button onClick={load} className="flex items-center gap-2 px-4 py-2 border border-gray-200 rounded-xl text-sm font-medium hover:bg-gray-50 transition-colors">
          <RefreshCw size={15} />
          Actualiser
        </button>
      </div>

      {/* Status tabs */}
      <div className="flex items-center gap-1 bg-gray-100 rounded-xl p-1">
        {STATUS_TABS.map((tab) => (
          <button
            key={tab.value}
            onClick={() => setStatusFilter(tab.value)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              statusFilter === tab.value
                ? 'bg-white text-gray-900 shadow-sm'
                : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            {tab.label}
            <span className={`px-1.5 py-0.5 rounded-full text-xs font-bold ${
              statusFilter === tab.value ? 'bg-[#6D28D9] text-white' : 'bg-gray-200 text-gray-600'
            }`}>
              {loading ? '—' : tab.count}
            </span>
          </button>
        ))}
      </div>

      {/* Search */}
      <div className="relative max-w-md">
        <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
        <input
          type="text"
          placeholder="Rechercher par titre, description, ID..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full pl-9 pr-4 py-2.5 border border-gray-200 rounded-xl text-sm bg-gray-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#6D28D9]/30 focus:border-[#6D28D9]"
        />
      </div>

      {loading ? (
        <div className="space-y-3">{[1,2,3,4,5].map(i => <div key={i} className="h-14 bg-gray-100 rounded-xl animate-pulse" />)}</div>
      ) : error ? (
        <div className="bg-red-50 border border-red-100 rounded-xl p-4 flex items-center gap-3">
          <AlertCircle size={18} className="text-red-500" />
          <p className="text-sm text-red-700">{error}</p>
          <button onClick={load} className="ml-auto text-sm font-semibold text-red-600 underline">Réessayer</button>
        </div>
      ) : (
        <DataTable
          columns={[
            {
              key: 'title', label: 'Tâche',
              render: (_, row) => {
                const t = row as AdminTask;
                return (
                  <div>
                    <p className="font-semibold text-gray-900 text-sm">{t.title}</p>
                    <p className="text-xs text-gray-400 truncate max-w-[240px]">{t.description}</p>
                  </div>
                );
              }
            },
            { key: 'status', label: 'Statut', render: (v) => <TaskStatusBadge status={v as string} /> },
            { key: 'price', label: 'Prix', render: (v, row) => `${Number(v).toLocaleString()} ${(row as AdminTask).currency}` },
            { key: 'created_at', label: 'Date', render: (v) => new Date(v as string).toLocaleDateString('fr-FR') },
            {
              key: 'id', label: 'Actions',
              render: (_, row) => {
                const t = row as AdminTask;
                return (
                  <div className="flex items-center gap-1.5">
                    <button
                      onClick={(e) => { e.stopPropagation(); setSelectedTask(t); }}
                      className="p-1.5 rounded-lg hover:bg-blue-50 text-blue-600 transition-colors"
                      title="Voir détails"
                    >
                      <Eye size={15} />
                    </button>
                    {t.status === 'OPEN' && (
                      <button
                        onClick={(e) => { e.stopPropagation(); setSelectedTask(t); }}
                        className="p-1.5 rounded-lg hover:bg-green-50 text-green-600 transition-colors"
                        title="Assigner"
                      >
                        <UserCheck size={15} />
                      </button>
                    )}
                    {t.status !== 'COMPLETED' && t.status !== 'CANCELLED' && (
                      <button
                        onClick={(e) => { e.stopPropagation(); setPendingCancel(t); }}
                        className="p-1.5 rounded-lg hover:bg-red-50 text-red-500 transition-colors"
                        title="Annuler"
                      >
                        <XCircle size={15} />
                      </button>
                    )}
                  </div>
                );
              }
            },
          ]}
          data={filtered}
          onRowClick={(row) => setSelectedTask(row as AdminTask)}
        />
      )}

      {filtered.length === 0 && !loading && !error && (
        <p className="text-center text-sm text-gray-400 py-8">Aucune tâche trouvée.</p>
      )}

      <TaskDetailPanel
        task={selectedTask}
        onClose={() => setSelectedTask(null)}
        onAction={load}
      />

      <ConfirmModal
        open={!!pendingCancel}
        title="Annuler la tâche"
        description={<span>Annuler la tâche <strong>«{pendingCancel?.title}»</strong> ?</span>}
        confirmLabel="Annuler la tâche"
        variant="danger"
        requireReason
        reasonLabel="Raison de l'annulation"
        loading={cancelLoading}
        onConfirm={handleCancelConfirm}
        onCancel={() => setPendingCancel(null)}
      />
    </div>
  );
}
