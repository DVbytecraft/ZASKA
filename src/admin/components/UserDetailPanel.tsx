import { useEffect, useState } from 'react';
import {
  Phone, Mail, MapPin, ShieldCheck, ShieldAlert, ShieldOff,
  Wallet, Clock, AlertTriangle, Loader2, RefreshCw
} from 'lucide-react';
import { SlidePanel } from './SlidePanel';
import { TxStatusBadge } from './StatusBadge';
import { adminApi, type AdminUserDetail } from '../adminApi';

interface UserDetailPanelProps {
  userId: string | null;
  onClose: () => void;
  onAction?: () => void;
}

function KycIcon({ status }: { status?: string }) {
  if (status === 'approved') return <ShieldCheck size={14} className="text-green-600" />;
  if (status === 'pending') return <ShieldAlert size={14} className="text-amber-600" />;
  return <ShieldOff size={14} className="text-gray-400" />;
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between py-2.5 border-b border-gray-100 last:border-0">
      <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">{label}</span>
      <span className="text-sm font-medium text-gray-900">{value}</span>
    </div>
  );
}

export function UserDetailPanel({ userId, onClose, onAction }: UserDetailPanelProps) {
  const [detail, setDetail] = useState<AdminUserDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!userId) { setDetail(null); return; }
    setLoading(true);
    setError(null);
    adminApi.getUserDetail(userId)
      .then(setDetail)
      .catch((e) => setError(e instanceof Error ? e.message : 'Erreur'))
      .finally(() => setLoading(false));
  }, [userId]);

  const displayName = detail
    ? ((detail.full_name ?? `${detail.first_name ?? ''} ${detail.last_name ?? ''}`.trim()) || (detail.email ?? '—'))
    : '—';

  const txTypeLabel: Record<string, string> = {
    deposit: '+ Dépôt', withdrawal: '- Retrait', transfer: '⇄ Transfert',
    escrow: '🔒 Escrow', release: '✓ Libération', refund: '↩ Remboursement',
    adjustment: '⚙ Ajustement',
  };

  return (
    <SlidePanel
      open={!!userId}
      title={displayName}
      subtitle={detail?.role ? `Rôle : ${detail.role}` : undefined}
      onClose={onClose}
    >
      {loading ? (
        <div className="flex items-center justify-center h-48">
          <Loader2 size={28} className="animate-spin text-[#6D28D9]" />
        </div>
      ) : error ? (
        <div className="p-6">
          <div className="flex items-center gap-3 bg-red-50 border border-red-100 rounded-xl p-4">
            <AlertTriangle size={18} className="text-red-500 flex-shrink-0" />
            <div className="flex-1">
              <p className="text-sm text-red-700">{error}</p>
            </div>
            <button onClick={() => userId && adminApi.getUserDetail(userId).then(setDetail).catch(() => {})} className="text-red-600">
              <RefreshCw size={14} />
            </button>
          </div>
        </div>
      ) : detail ? (
        <div className="divide-y divide-gray-100">
          {/* Identity */}
          <div className="px-6 py-5">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-[#6D28D9] to-[#7C3AED] flex items-center justify-center text-white text-xl font-bold flex-shrink-0">
                {displayName[0]?.toUpperCase() ?? '?'}
              </div>
              <div>
                <p className="font-bold text-gray-900 text-base">{displayName}</p>
                <div className="flex items-center gap-2 mt-1">
                  <KycIcon status={detail.kyc_status} />
                  <span className="text-xs text-gray-500">
                    {detail.kyc_status === 'approved' ? 'KYC Vérifié' :
                     detail.kyc_status === 'pending' ? 'KYC en attente' : 'KYC non soumis'}
                  </span>
                </div>
              </div>
            </div>

            <div className="space-y-2 text-sm">
              {detail.phone && (
                <div className="flex items-center gap-2 text-gray-700">
                  <Phone size={14} className="text-gray-400" />
                  <span className="font-medium">{detail.phone}</span>
                </div>
              )}
              {detail.email && (
                <div className="flex items-center gap-2 text-gray-700">
                  <Mail size={14} className="text-gray-400" />
                  <span>{detail.email}</span>
                </div>
              )}
              {detail.country_code && (
                <div className="flex items-center gap-2 text-gray-700">
                  <MapPin size={14} className="text-gray-400" />
                  <span>{detail.country_code}</span>
                </div>
              )}
            </div>

            <div className="mt-3 pt-3 border-t border-gray-100">
              <InfoRow label="Statut" value={detail.is_verified ? '✅ Vérifié' : '⏳ Non vérifié'} />
              <InfoRow label="Suspendu" value={detail.is_suspended ? '🚫 Oui' : 'Non'} />
              <InfoRow label="Verrouillé" value={detail.is_locked ? '🔒 Oui' : 'Non'} />
              <InfoRow label="Membre depuis" value={new Date(detail.created_at).toLocaleDateString('fr-FR')} />
            </div>
          </div>

          {/* Wallet */}
          {detail.wallet && (
            <div className="px-6 py-5">
              <div className="flex items-center gap-2 mb-3">
                <Wallet size={16} className="text-[#6D28D9]" />
                <h3 className="text-sm font-bold text-gray-900 uppercase tracking-wide">Portefeuille</h3>
              </div>
              <div className="bg-gradient-to-br from-[#6D28D9] to-[#7C3AED] rounded-2xl p-4 text-white">
                <p className="text-white/70 text-xs mb-1">Solde disponible</p>
                <p className="text-2xl font-extrabold">
                  {Number(detail.wallet.balance).toLocaleString()} {detail.wallet.currency}
                </p>
                {detail.wallet.locked_balance && Number(detail.wallet.locked_balance) > 0 && (
                  <p className="text-white/60 text-xs mt-1">
                    🔒 {Number(detail.wallet.locked_balance).toLocaleString()} {detail.wallet.currency} en escrow
                  </p>
                )}
              </div>
            </div>
          )}

          {/* Recent transactions */}
          {detail.recent_transactions && detail.recent_transactions.length > 0 && (
            <div className="px-6 py-5">
              <div className="flex items-center gap-2 mb-3">
                <Clock size={16} className="text-gray-500" />
                <h3 className="text-sm font-bold text-gray-900 uppercase tracking-wide">Transactions récentes</h3>
              </div>
              <div className="space-y-2">
                {detail.recent_transactions.slice(0, 5).map((tx) => (
                  <div key={tx.id} className="flex items-center justify-between py-2 border-b border-gray-50 last:border-0">
                    <div>
                      <p className="text-xs font-medium text-gray-800">
                        {txTypeLabel[tx.type] ?? tx.type}
                      </p>
                      <p className="text-xs text-gray-400">{new Date(tx.created_at).toLocaleDateString('fr-FR')}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-bold text-gray-900">
                        {Number(tx.amount).toLocaleString()} {tx.currency}
                      </span>
                      <TxStatusBadge status={tx.status} />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Active tasks */}
          {detail.active_tasks && detail.active_tasks.length > 0 && (
            <div className="px-6 py-5">
              <h3 className="text-sm font-bold text-gray-900 uppercase tracking-wide mb-3">Tâches actives</h3>
              <div className="space-y-2">
                {detail.active_tasks.map((task) => (
                  <div key={task.id} className="flex items-center justify-between py-2">
                    <p className="text-sm text-gray-800 truncate flex-1 mr-3">{task.title}</p>
                    <span className="text-xs font-medium text-[#6D28D9] whitespace-nowrap">
                      {Number(task.price).toLocaleString()} {task.currency}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      ) : null}
    </SlidePanel>
  );
}
