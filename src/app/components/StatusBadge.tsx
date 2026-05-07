interface StatusBadgeProps {
  status: 'posted' | 'applications' | 'in_progress' | 'completed' | 'paid';
}

export function StatusBadge({ status }: StatusBadgeProps) {
  const statusConfig = {
    posted: {
      label: 'Posted',
      color: 'bg-blue-50 text-blue-700 border-blue-100'
    },
    applications: {
      label: 'Applications received',
      color: 'bg-purple-50 text-purple-700 border-purple-100'
    },
    in_progress: {
      label: 'In progress',
      color: 'bg-amber-50 text-amber-700 border-amber-100'
    },
    completed: {
      label: 'Completed',
      color: 'bg-green-50 text-green-700 border-green-100'
    },
    paid: {
      label: 'Paid',
      color: 'bg-gray-50 text-gray-700 border-gray-100'
    }
  };

  const config = statusConfig[status];

  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold border ${config.color}`}>
      <div className="w-1.5 h-1.5 rounded-full bg-current"></div>
      {config.label}
    </span>
  );
}
