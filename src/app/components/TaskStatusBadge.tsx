import { Clock, CheckCircle2, Activity, XCircle, Users, Zap, AlertCircle } from 'lucide-react';

type TaskStatus =
  | 'posted'
  | 'accepted'
  | 'in_progress'
  | 'completed'
  | 'cancelled'
  | 'expired'
  | 'fast_matching'
  | 'awaiting_payment';

interface TaskStatusBadgeProps {
  status: TaskStatus;
  size?: 'sm' | 'md' | 'lg';
}

export function TaskStatusBadge({ status, size = 'md' }: TaskStatusBadgeProps) {
  const config = {
    posted: {
      icon: Clock,
      label: 'Posted',
      color: 'text-gray-700',
      bg: 'bg-gray-100',
      border: 'border-gray-200'
    },
    accepted: {
      icon: Users,
      label: 'Accepted',
      color: 'text-blue-700',
      bg: 'bg-blue-50',
      border: 'border-blue-200'
    },
    in_progress: {
      icon: Activity,
      label: 'In Progress',
      color: 'text-blue-700',
      bg: 'bg-blue-50',
      border: 'border-blue-200'
    },
    completed: {
      icon: CheckCircle2,
      label: 'Completed',
      color: 'text-green-700',
      bg: 'bg-green-50',
      border: 'border-green-200'
    },
    cancelled: {
      icon: XCircle,
      label: 'Cancelled',
      color: 'text-red-700',
      bg: 'bg-red-50',
      border: 'border-red-200'
    },
    expired: {
      icon: AlertCircle,
      label: 'Expired',
      color: 'text-orange-700',
      bg: 'bg-orange-50',
      border: 'border-orange-200'
    },
    fast_matching: {
      icon: Zap,
      label: 'Fast Matching',
      color: 'text-amber-700',
      bg: 'bg-amber-50',
      border: 'border-amber-200'
    },
    awaiting_payment: {
      icon: Clock,
      label: 'Awaiting Payment',
      color: 'text-purple-700',
      bg: 'bg-purple-50',
      border: 'border-purple-200'
    }
  };

  const { icon: Icon, label, color, bg, border } = config[status];

  const sizeClasses = {
    sm: 'text-xs px-2 py-1',
    md: 'text-sm px-2.5 py-1',
    lg: 'text-sm px-3 py-1.5'
  };

  const iconSizes = {
    sm: 12,
    md: 14,
    lg: 16
  };

  return (
    <div className={`inline-flex items-center gap-1.5 ${bg} ${color} ${sizeClasses[size]} rounded-lg border ${border} font-semibold`}>
      <Icon size={iconSizes[size]} />
      <span>{label}</span>
    </div>
  );
}
