import { Shield, Lock } from 'lucide-react';

interface EscrowBadgeProps {
  amount: string;
  status: 'held' | 'released';
}

export function EscrowBadge({ amount, status }: EscrowBadgeProps) {
  return (
    <div className={`inline-flex items-center gap-2 px-4 py-2.5 rounded-xl border-2 ${
      status === 'held'
        ? 'bg-blue-50 border-blue-200'
        : 'bg-green-50 border-green-200'
    }`}>
      {status === 'held' ? (
        <Lock size={18} className="text-blue-600" />
      ) : (
        <Shield size={18} className="text-green-600" />
      )}
      <div>
        <p className={`text-xs font-medium ${
          status === 'held' ? 'text-blue-700' : 'text-green-700'
        }`}>
          {status === 'held' ? 'Held in escrow' : 'Released from escrow'}
        </p>
        <p className={`text-sm font-bold ${
          status === 'held' ? 'text-blue-900' : 'text-green-900'
        }`}>
          {amount}
        </p>
      </div>
    </div>
  );
}
