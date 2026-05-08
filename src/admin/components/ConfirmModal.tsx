import { useState, ReactNode } from 'react';
import { AlertTriangle, X, Loader2 } from 'lucide-react';

interface ConfirmModalProps {
  open: boolean;
  title: string;
  description: ReactNode;
  confirmLabel?: string;
  variant?: 'danger' | 'warning' | 'info';
  requireReason?: boolean;
  reasonLabel?: string;
  loading?: boolean;
  onConfirm: (reason: string) => void;
  onCancel: () => void;
}

export function ConfirmModal({
  open, title, description, confirmLabel = 'Confirmer',
  variant = 'danger', requireReason = false, reasonLabel = 'Raison',
  loading, onConfirm, onCancel,
}: ConfirmModalProps) {
  const [reason, setReason] = useState('');
  if (!open) return null;

  const colorMap = {
    danger:  { icon: 'text-red-600 bg-red-100',  btn: 'bg-red-600 hover:bg-red-700', border: 'border-red-200' },
    warning: { icon: 'text-amber-600 bg-amber-100', btn: 'bg-amber-500 hover:bg-amber-600', border: 'border-amber-200' },
    info:    { icon: 'text-blue-600 bg-blue-100',  btn: 'bg-blue-600 hover:bg-blue-700', border: 'border-blue-200' },
  }[variant];

  const canConfirm = !requireReason || reason.trim().length >= 3;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md border border-gray-200">
        <div className="flex items-start justify-between p-6 pb-4">
          <div className="flex items-start gap-4">
            <div className={`w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 ${colorMap.icon}`}>
              <AlertTriangle size={20} strokeWidth={2.5} />
            </div>
            <div>
              <h3 className="text-base font-bold text-gray-900">{title}</h3>
              <div className="text-sm text-gray-600 mt-1">{description}</div>
            </div>
          </div>
          <button onClick={onCancel} className="p-1.5 hover:bg-gray-100 rounded-lg text-gray-400 hover:text-gray-600 transition-colors">
            <X size={16} />
          </button>
        </div>

        {requireReason && (
          <div className="px-6 pb-4">
            <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">
              {reasonLabel} <span className="text-red-500">*</span>
            </label>
            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Expliquez la raison de cette action..."
              rows={3}
              className="w-full px-3 py-2.5 rounded-xl border-2 border-gray-200 focus:border-[#6D28D9] focus:outline-none text-sm resize-none"
            />
          </div>
        )}

        <div className="px-6 pb-6 flex gap-3 justify-end">
          <button
            onClick={onCancel}
            disabled={loading}
            className="px-4 py-2.5 rounded-xl border border-gray-200 text-sm font-semibold text-gray-700 hover:bg-gray-50 transition-colors"
          >
            Annuler
          </button>
          <button
            onClick={() => onConfirm(reason)}
            disabled={!canConfirm || loading}
            className={`px-5 py-2.5 rounded-xl text-sm font-bold text-white transition-colors flex items-center gap-2 ${colorMap.btn} disabled:opacity-50 disabled:cursor-not-allowed`}
          >
            {loading && <Loader2 size={14} className="animate-spin" />}
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
