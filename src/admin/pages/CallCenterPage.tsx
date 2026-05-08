import { useEffect, useState, useCallback } from 'react';
import {
  Search, Phone, Headphones, Clock, AlertTriangle, RefreshCw,
  MessageSquare, Lock, Unlock, RotateCcw, Send, ChevronRight,
  PlusCircle, Loader2, CheckCircle, ArrowUp, User, Wallet,
  CreditCard, Briefcase, Bell, X
} from 'lucide-react';
import { adminApi, type AdminSupportTicket, type AdminUserDetail, type AdminTransaction } from '../adminApi';
import { TicketStatusBadge, PriorityBadge } from '../components/StatusBadge';
import { ConfirmModal } from '../components/ConfirmModal';

// ─── Ticket Queue (Left Panel) ────────────────────────────────────────────────

function TicketQueue({
  tickets,
  selectedId,
  onSelect,
  loading,
}: {
  tickets: AdminSupportTicket[];
  selectedId: string | null;
  onSelect: (t: AdminSupportTicket) => void;
  loading: boolean;
}) {
  const sorted = [...tickets].sort((a, b) => (b.wait_minutes ?? 0) - (a.wait_minutes ?? 0));

  return (
    <div className="w-80 flex-shrink-0 flex flex-col border-r border-gray-200 bg-white overflow-hidden">
      <div className="px-4 py-3 border-b border-gray-100">
        <p className="text-xs font-bold text-gray-500 uppercase tracking-wide">
          File d'attente
        </p>
        <p className="text-sm font-semibold text-gray-900 mt-0.5">
          {loading ? '—' : `${tickets.length} ticket${tickets.length !== 1 ? 's' : ''}`}
        </p>
      </div>

      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="p-4 space-y-3">
            {[1, 2, 3, 4].map(i => (
              <div key={i} className="h-20 bg-gray-100 rounded-xl animate-pulse" />
            ))}
          </div>
        ) : sorted.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 px-4 text-center">
            <CheckCircle size={28} className="text-green-400 mb-2" />
            <p className="text-sm font-semibold text-gray-600">Aucun ticket en attente</p>
          </div>
        ) : (
          sorted.map((ticket) => {
            const isSelected = ticket.id === selectedId;
            const isUrgent = ticket.priority === 'urgent' || (ticket.wait_minutes ?? 0) > 30;
            return (
              <button
                key={ticket.id}
                onClick={() => onSelect(ticket)}
                className={`w-full text-left px-4 py-3 border-b border-gray-50 transition-all ${
                  isSelected
                    ? 'bg-purple-50 border-l-4 border-l-[#6D28D9]'
                    : 'hover:bg-gray-50 border-l-4 border-l-transparent'
                }`}
              >
                <div className="flex items-start justify-between gap-2 mb-1">
                  <p className="text-sm font-semibold text-gray-900 truncate flex-1">
                    {ticket.user_name}
                  </p>
                  <PriorityBadge status={ticket.priority} />
                </div>
                <p className="text-xs text-gray-500 truncate mb-2">{ticket.subject}</p>
                <div className="flex items-center justify-between">
                  <TicketStatusBadge status={ticket.status} />
                  {(ticket.wait_minutes ?? 0) > 0 && (
                    <span className={`flex items-center gap-1 text-xs font-medium ${
                      isUrgent ? 'text-red-600' : 'text-gray-400'
                    }`}>
                      <Clock size={11} />
                      {ticket.wait_minutes}m
                    </span>
                  )}
                </div>
              </button>
            );
          })
        )}
      </div>
    </div>
  );
}

// ─── User Profile (Center Panel) ─────────────────────────────────────────────

function UserProfile({
  detail,
  loading,
  ticket,
}: {
  detail: AdminUserDetail | null;
  loading: boolean;
  ticket: AdminSupportTicket | null;
}) {
  if (!ticket && !loading) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-center p-10 bg-gray-50">
        <div className="w-16 h-16 bg-white rounded-2xl shadow-sm flex items-center justify-center mb-4">
          <Headphones size={28} className="text-[#6D28D9]" />
        </div>
        <p className="text-base font-semibold text-gray-700">Sélectionnez un ticket</p>
        <p className="text-sm text-gray-400 mt-1">Le profil utilisateur et les actions apparaîtront ici.</p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex-1 overflow-y-auto bg-gray-50 p-6 space-y-4">
        {[1, 2, 3].map(i => (
          <div key={i} className="h-32 bg-white rounded-xl animate-pulse" />
        ))}
      </div>
    );
  }

  const u = detail;

  return (
    <div className="flex-1 overflow-y-auto bg-gray-50">
      {/* Ticket header */}
      {ticket && (
        <div className="bg-white border-b border-gray-200 px-6 py-4">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <TicketStatusBadge status={ticket.status} />
                <PriorityBadge priority={ticket.priority} />
                <span className="text-xs text-gray-400">#{ticket.id.slice(0, 8)}</span>
              </div>
              <p className="text-base font-bold text-gray-900">{ticket.subject}</p>
              <p className="text-sm text-gray-600 mt-1">{ticket.description}</p>
            </div>
          </div>
        </div>
      )}

      <div className="p-6 space-y-5">
        {/* Identity card */}
        {u && (
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-100 flex items-center gap-2">
              <User size={15} className="text-[#6D28D9]" />
              <h3 className="text-sm font-bold text-gray-900">Identité</h3>
            </div>
            <div className="px-5 py-4">
              <div className="flex items-center gap-4 mb-4">
                <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-[#6D28D9] to-[#7C3AED] flex items-center justify-center text-white font-bold text-lg flex-shrink-0">
                  {(u.full_name ?? u.first_name ?? u.phone ?? '?')[0].toUpperCase()}
                </div>
                <div>
                  <p className="font-bold text-gray-900">
                    {(u.full_name ?? `${u.first_name ?? ''} ${u.last_name ?? ''}`.trim()) || '—'}
                  </p>
                  <p className="text-sm text-gray-500">{u.phone ?? u.email ?? '—'}</p>
                </div>
              </div>
              <div className="grid grid-cols-3 gap-3 text-xs">
                {[
                  { label: 'Rôle', value: u.role },
                  { label: 'Pays', value: u.country_code ?? '—' },
                  { label: 'KYC', value: u.kyc_status ?? 'n/a' },
                  { label: 'Vérifié', value: u.is_verified ? 'Oui' : 'Non' },
                  { label: 'Suspendu', value: u.is_suspended ? 'Oui' : 'Non' },
                  { label: 'Verrouillé', value: u.is_locked ? 'Oui' : 'Non' },
                ].map(({ label, value }) => (
                  <div key={label}>
                    <p className="text-gray-400 font-semibold uppercase tracking-wide">{label}</p>
                    <p className="text-gray-900 font-semibold mt-0.5">{value}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Wallet */}
        {u?.wallet && (
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-100 flex items-center gap-2">
              <Wallet size={15} className="text-[#6D28D9]" />
              <h3 className="text-sm font-bold text-gray-900">Portefeuille</h3>
            </div>
            <div className="px-5 py-4 flex items-center gap-6">
              <div>
                <p className="text-xs text-gray-400 font-semibold uppercase tracking-wide">Solde</p>
                <p className="text-2xl font-extrabold text-gray-900 mt-0.5">
                  {Number(u.wallet.balance).toLocaleString()} <span className="text-sm font-semibold text-gray-500">{u.wallet.currency}</span>
                </p>
              </div>
              {u.wallet.locked_balance && Number(u.wallet.locked_balance) > 0 && (
                <div>
                  <p className="text-xs text-gray-400 font-semibold uppercase tracking-wide">Bloqué</p>
                  <p className="text-lg font-bold text-amber-600 mt-0.5">
                    {Number(u.wallet.locked_balance).toLocaleString()} {u.wallet.currency}
                  </p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Recent transactions */}
        {u?.recent_transactions && u.recent_transactions.length > 0 && (
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-100 flex items-center gap-2">
              <CreditCard size={15} className="text-[#6D28D9]" />
              <h3 className="text-sm font-bold text-gray-900">Transactions récentes</h3>
            </div>
            <div className="divide-y divide-gray-50">
              {u.recent_transactions.slice(0, 5).map((tx: AdminTransaction) => (
                <div key={tx.id} className="px-5 py-3 flex items-center justify-between">
                  <div>
                    <p className="text-sm font-semibold text-gray-900 capitalize">{tx.type}</p>
                    <p className="text-xs text-gray-400">{new Date(tx.created_at).toLocaleDateString('fr-FR')}</p>
                  </div>
                  <div className="text-right">
                    <p className={`text-sm font-bold ${tx.status === 'failed' ? 'text-red-600' : tx.type === 'withdrawal' ? 'text-gray-900' : 'text-green-600'}`}>
                      {tx.type === 'withdrawal' ? '-' : '+'}{Number(tx.amount).toLocaleString()} {tx.currency}
                    </p>
                    <p className={`text-xs font-medium ${
                      tx.status === 'failed' ? 'text-red-500' :
                      tx.status === 'pending' ? 'text-amber-500' : 'text-gray-400'
                    }`}>{tx.status}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Active tasks */}
        {u?.active_tasks && u.active_tasks.length > 0 && (
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-100 flex items-center gap-2">
              <Briefcase size={15} className="text-[#6D28D9]" />
              <h3 className="text-sm font-bold text-gray-900">Tâches actives</h3>
            </div>
            <div className="divide-y divide-gray-50">
              {u.active_tasks.map(t => (
                <div key={t.id} className="px-5 py-3 flex items-center justify-between">
                  <div>
                    <p className="text-sm font-semibold text-gray-900">{t.title}</p>
                    <p className="text-xs text-gray-400">{t.status}</p>
                  </div>
                  <p className="text-sm font-bold text-gray-700">{Number(t.price).toLocaleString()} {t.currency}</p>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Actions Panel (Right Panel) ──────────────────────────────────────────────

type ActionModal =
  | { type: 'refund' }
  | { type: 'lock' }
  | { type: 'unlock' }
  | { type: 'notify' }
  | { type: 'escalate' }
  | { type: 'resolve' }
  | { type: 'createTicket' };

function ActionsPanel({
  ticket,
  detail,
  onTicketUpdated,
}: {
  ticket: AdminSupportTicket | null;
  detail: AdminUserDetail | null;
  onTicketUpdated: () => void;
}) {
  const [notes, setNotes] = useState('');
  const [savingNotes, setSavingNotes] = useState(false);
  const [notesSaved, setNotesSaved] = useState(false);
  const [activeModal, setActiveModal] = useState<ActionModal | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [actionError, setActionError] = useState('');

  // Refund form state
  const [refundAmount, setRefundAmount] = useState('');
  const [refundCurrency, setRefundCurrency] = useState('XOF');
  const [notifyMessage, setNotifyMessage] = useState('');
  const [notifyChannel, setNotifyChannel] = useState<'sms' | 'push'>('sms');

  // New ticket form state
  const [newTicketCategory, setNewTicketCategory] = useState('payment');
  const [newTicketSubject, setNewTicketSubject] = useState('');
  const [newTicketDesc, setNewTicketDesc] = useState('');

  const handleSaveNotes = async () => {
    if (!ticket || !notes.trim()) return;
    setSavingNotes(true);
    try {
      await adminApi.updateTicket(ticket.id, { notes });
      setNotesSaved(true);
      setTimeout(() => setNotesSaved(false), 2000);
    } catch {}
    finally { setSavingNotes(false); }
  };

  const handleAction = async () => {
    if (!activeModal || !detail) return;
    setActionLoading(true);
    setActionError('');
    try {
      switch (activeModal.type) {
        case 'refund':
          if (!refundAmount) { setActionError('Montant requis'); setActionLoading(false); return; }
          await adminApi.triggerRefund(detail.id, refundAmount, refundCurrency, notes || 'Remboursement agent', ticket?.id);
          break;
        case 'lock':
          await adminApi.lockAccount(detail.id, notes || 'Verrouillé par agent');
          break;
        case 'unlock':
          await adminApi.unlockAccount(detail.id);
          break;
        case 'notify':
          if (!notifyMessage) { setActionError('Message requis'); setActionLoading(false); return; }
          await adminApi.sendNotification(detail.id, notifyMessage, notifyChannel);
          break;
        case 'escalate':
          if (ticket) await adminApi.escalateTicket(ticket.id);
          break;
        case 'resolve':
          if (ticket) await adminApi.resolveTicket(ticket.id, notes || 'Résolu par agent');
          break;
        case 'createTicket':
          if (!newTicketSubject) { setActionError('Sujet requis'); setActionLoading(false); return; }
          await adminApi.createSupportTicket({
            user_id: detail.id,
            category: newTicketCategory,
            priority: 'medium',
            subject: newTicketSubject,
            description: newTicketDesc,
          });
          break;
      }
      setActiveModal(null);
      setRefundAmount('');
      setNotifyMessage('');
      setNewTicketSubject('');
      setNewTicketDesc('');
      onTicketUpdated();
    } catch (e) {
      setActionError(e instanceof Error ? e.message : 'Échec de l\'action');
    } finally {
      setActionLoading(false);
    }
  };

  if (!ticket || !detail) {
    return (
      <div className="w-72 flex-shrink-0 bg-white border-l border-gray-200 flex items-center justify-center">
        <p className="text-sm text-gray-300 text-center px-4">Sélectionnez un ticket pour voir les actions</p>
      </div>
    );
  }

  return (
    <div className="w-72 flex-shrink-0 bg-white border-l border-gray-200 overflow-y-auto">
      <div className="px-4 py-3 border-b border-gray-100">
        <p className="text-xs font-bold text-gray-500 uppercase tracking-wide">Actions rapides</p>
      </div>

      {/* Quick action buttons */}
      <div className="px-4 py-4 space-y-2">
        {[
          {
            icon: RotateCcw, label: 'Déclencher un remboursement',
            color: 'text-amber-700 bg-amber-50 hover:bg-amber-100 border-amber-200',
            action: () => { setActionError(''); setActiveModal({ type: 'refund' }); },
          },
          {
            icon: detail.is_locked ? Unlock : Lock,
            label: detail.is_locked ? 'Déverrouiller le compte' : 'Verrouiller le compte',
            color: detail.is_locked
              ? 'text-green-700 bg-green-50 hover:bg-green-100 border-green-200'
              : 'text-orange-700 bg-orange-50 hover:bg-orange-100 border-orange-200',
            action: () => { setActionError(''); setActiveModal({ type: detail.is_locked ? 'unlock' : 'lock' }); },
          },
          {
            icon: Bell, label: 'Notifier l\'utilisateur',
            color: 'text-blue-700 bg-blue-50 hover:bg-blue-100 border-blue-200',
            action: () => { setActionError(''); setActiveModal({ type: 'notify' }); },
          },
          {
            icon: ArrowUp, label: 'Escalader le ticket',
            color: 'text-red-700 bg-red-50 hover:bg-red-100 border-red-200',
            action: () => { setActionError(''); setActiveModal({ type: 'escalate' }); },
            hide: ticket.status === 'escalated' || ticket.status === 'resolved' || ticket.status === 'closed',
          },
          {
            icon: CheckCircle, label: 'Marquer comme résolu',
            color: 'text-green-700 bg-green-50 hover:bg-green-100 border-green-200',
            action: () => { setActionError(''); setActiveModal({ type: 'resolve' }); },
            hide: ticket.status === 'resolved' || ticket.status === 'closed',
          },
          {
            icon: PlusCircle, label: 'Créer un ticket',
            color: 'text-purple-700 bg-purple-50 hover:bg-purple-100 border-purple-200',
            action: () => { setActionError(''); setActiveModal({ type: 'createTicket' }); },
          },
        ].filter(a => !a.hide).map(({ icon: Icon, label, color, action }) => (
          <button
            key={label}
            onClick={action}
            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl border text-sm font-semibold transition-colors ${color}`}
          >
            <Icon size={15} className="flex-shrink-0" />
            {label}
            <ChevronRight size={14} className="ml-auto opacity-50" />
          </button>
        ))}
      </div>

      {/* Notes */}
      <div className="px-4 pb-4 border-t border-gray-100 pt-4">
        <label className="block text-xs font-bold text-gray-500 uppercase tracking-wide mb-1.5">
          Notes de ticket
        </label>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder={ticket.notes ?? 'Ajouter une note interne...'}
          rows={4}
          className="w-full px-3 py-2.5 border-2 border-gray-200 rounded-xl text-sm resize-none focus:border-[#6D28D9] focus:outline-none transition-colors"
        />
        <button
          onClick={handleSaveNotes}
          disabled={!notes.trim() || savingNotes}
          className="mt-2 w-full py-2 rounded-xl bg-gray-900 text-white text-sm font-bold hover:bg-gray-800 disabled:opacity-40 transition-colors flex items-center justify-center gap-2"
        >
          {savingNotes ? <Loader2 size={13} className="animate-spin" /> : <Send size={13} />}
          {notesSaved ? 'Sauvegardé !' : 'Sauvegarder'}
        </button>
      </div>

      {/* Action modal overlay */}
      {activeModal && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4" onClick={() => setActiveModal(null)}>
          <div
            className="bg-white rounded-2xl shadow-2xl w-full max-w-sm p-6"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-base font-bold text-gray-900">
                {activeModal.type === 'refund' && 'Déclencher un remboursement'}
                {activeModal.type === 'lock' && 'Verrouiller le compte'}
                {activeModal.type === 'unlock' && 'Déverrouiller le compte'}
                {activeModal.type === 'notify' && 'Notifier l\'utilisateur'}
                {activeModal.type === 'escalate' && 'Escalader le ticket'}
                {activeModal.type === 'resolve' && 'Résoudre le ticket'}
                {activeModal.type === 'createTicket' && 'Créer un ticket'}
              </h3>
              <button onClick={() => setActiveModal(null)} className="p-1 hover:bg-gray-100 rounded-lg">
                <X size={16} className="text-gray-500" />
              </button>
            </div>

            <div className="space-y-3">
              {activeModal.type === 'refund' && (
                <>
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="block text-xs font-semibold text-gray-500 uppercase mb-1">Montant</label>
                      <input
                        type="number"
                        value={refundAmount}
                        onChange={(e) => setRefundAmount(e.target.value)}
                        placeholder="ex: 5000"
                        className="w-full px-3 py-2 border-2 border-gray-200 rounded-xl text-sm focus:border-[#6D28D9] focus:outline-none"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-gray-500 uppercase mb-1">Devise</label>
                      <select
                        value={refundCurrency}
                        onChange={(e) => setRefundCurrency(e.target.value)}
                        className="w-full px-3 py-2 border-2 border-gray-200 rounded-xl text-sm focus:border-[#6D28D9] focus:outline-none"
                      >
                        <option value="XOF">XOF</option>
                        <option value="USD">USD</option>
                        <option value="EUR">EUR</option>
                        <option value="GHS">GHS</option>
                        <option value="NGN">NGN</option>
                      </select>
                    </div>
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-gray-500 uppercase mb-1">Raison</label>
                    <textarea
                      value={notes}
                      onChange={(e) => setNotes(e.target.value)}
                      placeholder="Justification du remboursement..."
                      rows={3}
                      className="w-full px-3 py-2 border-2 border-gray-200 rounded-xl text-sm resize-none focus:border-[#6D28D9] focus:outline-none"
                    />
                  </div>
                </>
              )}

              {activeModal.type === 'notify' && (
                <>
                  <div className="flex gap-2">
                    {(['sms', 'push'] as const).map((ch) => (
                      <button
                        key={ch}
                        onClick={() => setNotifyChannel(ch)}
                        className={`flex-1 py-2 rounded-xl text-sm font-semibold border-2 transition-colors ${
                          notifyChannel === ch ? 'border-[#6D28D9] bg-purple-50 text-[#6D28D9]' : 'border-gray-200 text-gray-600'
                        }`}
                      >
                        {ch.toUpperCase()}
                      </button>
                    ))}
                  </div>
                  <textarea
                    value={notifyMessage}
                    onChange={(e) => setNotifyMessage(e.target.value)}
                    placeholder="Message à envoyer..."
                    rows={4}
                    className="w-full px-3 py-2 border-2 border-gray-200 rounded-xl text-sm resize-none focus:border-[#6D28D9] focus:outline-none"
                  />
                </>
              )}

              {activeModal.type === 'createTicket' && (
                <>
                  <div>
                    <label className="block text-xs font-semibold text-gray-500 uppercase mb-1">Catégorie</label>
                    <select
                      value={newTicketCategory}
                      onChange={(e) => setNewTicketCategory(e.target.value)}
                      className="w-full px-3 py-2 border-2 border-gray-200 rounded-xl text-sm focus:border-[#6D28D9] focus:outline-none"
                    >
                      <option value="payment">Paiement</option>
                      <option value="task">Tâche</option>
                      <option value="account">Compte</option>
                      <option value="technical">Technique</option>
                      <option value="other">Autre</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-gray-500 uppercase mb-1">Sujet</label>
                    <input
                      type="text"
                      value={newTicketSubject}
                      onChange={(e) => setNewTicketSubject(e.target.value)}
                      placeholder="Sujet du ticket..."
                      className="w-full px-3 py-2 border-2 border-gray-200 rounded-xl text-sm focus:border-[#6D28D9] focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-gray-500 uppercase mb-1">Description</label>
                    <textarea
                      value={newTicketDesc}
                      onChange={(e) => setNewTicketDesc(e.target.value)}
                      placeholder="Détails..."
                      rows={3}
                      className="w-full px-3 py-2 border-2 border-gray-200 rounded-xl text-sm resize-none focus:border-[#6D28D9] focus:outline-none"
                    />
                  </div>
                </>
              )}

              {(activeModal.type === 'lock' || activeModal.type === 'resolve' || activeModal.type === 'escalate') && (
                <div>
                  <label className="block text-xs font-semibold text-gray-500 uppercase mb-1">
                    {activeModal.type === 'lock' ? 'Raison du verrouillage' : 'Note'}
                  </label>
                  <textarea
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    placeholder={activeModal.type === 'escalate' ? 'Optionnel...' : 'Justification...'}
                    rows={3}
                    className="w-full px-3 py-2 border-2 border-gray-200 rounded-xl text-sm resize-none focus:border-[#6D28D9] focus:outline-none"
                  />
                </div>
              )}

              {activeModal.type === 'unlock' && (
                <p className="text-sm text-gray-600">
                  Voulez-vous vraiment déverrouiller le compte de <strong>{detail.full_name ?? detail.phone}</strong> ?
                </p>
              )}

              {actionError && (
                <p className="text-xs text-red-600 bg-red-50 px-3 py-2 rounded-xl">{actionError}</p>
              )}

              <button
                onClick={handleAction}
                disabled={actionLoading}
                className="w-full py-3 rounded-xl bg-[#6D28D9] text-white text-sm font-bold hover:bg-[#5B21B6] disabled:opacity-50 transition-colors flex items-center justify-center gap-2"
              >
                {actionLoading ? <Loader2 size={14} className="animate-spin" /> : null}
                Confirmer
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Main Page ─────────────────────────────────────────────────────────────────

export function CallCenterPage() {
  const [tickets, setTickets] = useState<AdminSupportTicket[]>([]);
  const [ticketsLoading, setTicketsLoading] = useState(true);
  const [selectedTicket, setSelectedTicket] = useState<AdminSupportTicket | null>(null);
  const [userDetail, setUserDetail] = useState<AdminUserDetail | null>(null);
  const [userLoading, setUserLoading] = useState(false);

  // Phone lookup
  const [phoneQuery, setPhoneQuery] = useState('');
  const [lookupLoading, setLookupLoading] = useState(false);
  const [lookupError, setLookupError] = useState('');

  const loadTickets = useCallback(() => {
    setTicketsLoading(true);
    adminApi.getSupportTickets()
      .then(setTickets)
      .catch(() => setTickets([]))
      .finally(() => setTicketsLoading(false));
  }, []);

  useEffect(() => { loadTickets(); }, [loadTickets]);

  const handleSelectTicket = useCallback(async (ticket: AdminSupportTicket) => {
    setSelectedTicket(ticket);
    setUserDetail(null);
    setUserLoading(true);
    try {
      const detail = await adminApi.getUserDetail(ticket.user_id);
      setUserDetail(detail);
    } catch {
      setUserDetail({ id: ticket.user_id, phone: ticket.user_phone ?? null, full_name: ticket.user_name, email: null, first_name: null, last_name: null, role: 'user', is_verified: false, country_code: null, created_at: '' });
    } finally {
      setUserLoading(false);
    }
  }, []);

  const handlePhoneLookup = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!phoneQuery.trim()) return;
    setLookupLoading(true);
    setLookupError('');
    try {
      const result = await adminApi.lookupByPhone(phoneQuery.trim());
      setUserDetail(result);
      setSelectedTicket(null);
    } catch (err) {
      setLookupError(err instanceof Error ? err.message : 'Utilisateur introuvable');
    } finally {
      setLookupLoading(false);
    }
  };

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Top bar: header + phone lookup */}
      <div className="bg-white border-b border-gray-200 px-6 py-4 flex-shrink-0">
        <div className="flex items-center justify-between gap-6">
          <div>
            <h2 className="text-xl font-bold text-gray-900">Call Center</h2>
            <p className="text-xs text-gray-500">Outil opérationnel de support en temps réel</p>
          </div>

          <form onSubmit={handlePhoneLookup} className="flex items-center gap-2 flex-1 max-w-lg">
            <div className="relative flex-1">
              <Phone size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                type="text"
                value={phoneQuery}
                onChange={(e) => setPhoneQuery(e.target.value)}
                placeholder="Rechercher par numéro de téléphone... (+225...)"
                className="w-full pl-9 pr-4 py-2.5 border-2 border-gray-200 rounded-xl text-sm focus:border-[#6D28D9] focus:outline-none transition-colors"
              />
            </div>
            <button
              type="submit"
              disabled={lookupLoading || !phoneQuery.trim()}
              className="px-4 py-2.5 rounded-xl bg-[#6D28D9] text-white text-sm font-bold hover:bg-[#5B21B6] disabled:opacity-50 transition-colors flex items-center gap-2 whitespace-nowrap"
            >
              {lookupLoading ? <Loader2 size={14} className="animate-spin" /> : <Search size={14} />}
              Rechercher
            </button>
            <button
              type="button"
              onClick={loadTickets}
              className="p-2.5 rounded-xl border border-gray-200 hover:bg-gray-50 transition-colors"
              title="Actualiser"
            >
              <RefreshCw size={15} className="text-gray-500" />
            </button>
          </form>
        </div>

        {lookupError && (
          <div className="mt-3 flex items-center gap-2 bg-red-50 border border-red-200 rounded-xl px-4 py-2">
            <AlertTriangle size={14} className="text-red-500 flex-shrink-0" />
            <p className="text-xs text-red-700 font-medium">{lookupError}</p>
          </div>
        )}
      </div>

      {/* 3-panel layout */}
      <div className="flex-1 flex overflow-hidden">
        <TicketQueue
          tickets={tickets}
          selectedId={selectedTicket?.id ?? null}
          onSelect={handleSelectTicket}
          loading={ticketsLoading}
        />
        <UserProfile
          detail={userDetail}
          loading={userLoading}
          ticket={selectedTicket}
        />
        <ActionsPanel
          ticket={selectedTicket}
          detail={userDetail}
          onTicketUpdated={loadTickets}
        />
      </div>
    </div>
  );
}
