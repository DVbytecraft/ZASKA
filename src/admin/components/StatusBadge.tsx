interface StatusBadgeProps {
  status: string;
  size?: 'sm' | 'md';
}

const TASK_STATUS: Record<string, { bg: string; text: string; label: string }> = {
  OPEN:      { bg: 'bg-blue-100',   text: 'text-blue-700',   label: 'Ouvert' },
  ASSIGNED:  { bg: 'bg-purple-100', text: 'text-purple-700', label: 'Assigné' },
  COMPLETED: { bg: 'bg-green-100',  text: 'text-green-700',  label: 'Terminé' },
  CANCELLED: { bg: 'bg-red-100',    text: 'text-red-700',    label: 'Annulé' },
};

const TX_STATUS: Record<string, { bg: string; text: string; label: string }> = {
  completed: { bg: 'bg-green-100',  text: 'text-green-700',  label: 'Complété' },
  pending:   { bg: 'bg-amber-100',  text: 'text-amber-700',  label: 'En cours' },
  failed:    { bg: 'bg-red-100',    text: 'text-red-700',    label: 'Échoué' },
  cancelled: { bg: 'bg-gray-100',   text: 'text-gray-600',   label: 'Annulé' },
};

const DISPUTE_STATUS: Record<string, { bg: string; text: string; label: string }> = {
  open:         { bg: 'bg-red-100',    text: 'text-red-700',    label: 'Ouvert' },
  under_review: { bg: 'bg-amber-100',  text: 'text-amber-700',  label: 'En examen' },
  resolved:     { bg: 'bg-green-100',  text: 'text-green-700',  label: 'Résolu' },
  closed:       { bg: 'bg-gray-100',   text: 'text-gray-600',   label: 'Fermé' },
};

const TICKET_STATUS: Record<string, { bg: string; text: string; label: string }> = {
  open:        { bg: 'bg-red-100',    text: 'text-red-700',    label: 'Ouvert' },
  in_progress: { bg: 'bg-blue-100',   text: 'text-blue-700',   label: 'En cours' },
  resolved:    { bg: 'bg-green-100',  text: 'text-green-700',  label: 'Résolu' },
  escalated:   { bg: 'bg-orange-100', text: 'text-orange-700', label: 'Escaladé' },
  closed:      { bg: 'bg-gray-100',   text: 'text-gray-600',   label: 'Fermé' },
};

const PRIORITY: Record<string, { bg: string; text: string; label: string }> = {
  urgent: { bg: 'bg-red-100',    text: 'text-red-700',    label: '🔴 Urgent' },
  high:   { bg: 'bg-orange-100', text: 'text-orange-700', label: '🟠 Haute' },
  medium: { bg: 'bg-amber-100',  text: 'text-amber-700',  label: '🟡 Moyenne' },
  low:    { bg: 'bg-gray-100',   text: 'text-gray-600',   label: '⚪ Faible' },
};

const PROVIDER_STATUS: Record<string, { bg: string; text: string; dot: string; label: string }> = {
  operational: { bg: 'bg-green-50',  text: 'text-green-700',  dot: 'bg-green-500', label: 'Opérationnel' },
  degraded:    { bg: 'bg-amber-50',  text: 'text-amber-700',  dot: 'bg-amber-500', label: 'Dégradé' },
  down:        { bg: 'bg-red-50',    text: 'text-red-700',    dot: 'bg-red-500',   label: 'Hors service' },
};

export function TaskStatusBadge({ status, size = 'sm' }: StatusBadgeProps) {
  const s = TASK_STATUS[status] ?? { bg: 'bg-gray-100', text: 'text-gray-600', label: status };
  const cls = size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-3 py-1 text-sm';
  return (
    <span className={`inline-flex items-center rounded-full font-medium ${s.bg} ${s.text} ${cls}`}>
      {s.label}
    </span>
  );
}

export function TxStatusBadge({ status, size = 'sm' }: StatusBadgeProps) {
  const s = TX_STATUS[status] ?? { bg: 'bg-gray-100', text: 'text-gray-600', label: status };
  const cls = size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-3 py-1 text-sm';
  return (
    <span className={`inline-flex items-center rounded-full font-medium ${s.bg} ${s.text} ${cls}`}>
      {s.label}
    </span>
  );
}

export function DisputeStatusBadge({ status, size = 'sm' }: StatusBadgeProps) {
  const s = DISPUTE_STATUS[status] ?? { bg: 'bg-gray-100', text: 'text-gray-600', label: status };
  const cls = size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-3 py-1 text-sm';
  return (
    <span className={`inline-flex items-center rounded-full font-medium ${s.bg} ${s.text} ${cls}`}>
      {s.label}
    </span>
  );
}

export function TicketStatusBadge({ status, size = 'sm' }: StatusBadgeProps) {
  const s = TICKET_STATUS[status] ?? { bg: 'bg-gray-100', text: 'text-gray-600', label: status };
  const cls = size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-3 py-1 text-sm';
  return (
    <span className={`inline-flex items-center rounded-full font-medium ${s.bg} ${s.text} ${cls}`}>
      {s.label}
    </span>
  );
}

export function PriorityBadge({ status, size = 'sm' }: StatusBadgeProps) {
  const s = PRIORITY[status] ?? { bg: 'bg-gray-100', text: 'text-gray-600', label: status };
  const cls = size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-3 py-1 text-sm';
  return (
    <span className={`inline-flex items-center rounded-full font-medium ${s.bg} ${s.text} ${cls}`}>
      {s.label}
    </span>
  );
}

export function ProviderStatusBadge({ status }: { status: string }) {
  const s = PROVIDER_STATUS[status] ?? PROVIDER_STATUS.down;
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${s.bg} ${s.text}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${s.dot}`} />
      {s.label}
    </span>
  );
}
