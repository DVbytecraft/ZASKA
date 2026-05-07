import { LucideIcon } from 'lucide-react';

interface KPICardProps {
  label: string;
  value: string | number;
  change?: string;
  icon: LucideIcon;
  trend?: 'up' | 'down';
}

export function KPICard({ label, value, change, icon: Icon, trend }: KPICardProps) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-6">
      <div className="flex items-center justify-between mb-4">
        <span className="text-sm font-medium text-gray-600">{label}</span>
        <div className="w-10 h-10 rounded-lg bg-[#6D28D9]/10 flex items-center justify-center">
          <Icon size={20} className="text-[#6D28D9]" strokeWidth={2} />
        </div>
      </div>

      <div className="flex items-baseline gap-2">
        <span className="text-3xl font-bold text-gray-900">{value}</span>
        {change && (
          <span className={`text-sm font-medium ${
            trend === 'up' ? 'text-green-600' : trend === 'down' ? 'text-red-600' : 'text-gray-600'
          }`}>
            {change}
          </span>
        )}
      </div>
    </div>
  );
}
