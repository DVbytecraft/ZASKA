import { useEffect, useState } from 'react';
import { apiClient } from '@zaska/shared-services';
import { Card } from '../components/Card';
import { Avatar } from '../components/Avatar';
import {
  ChevronRight, CreditCard, Clock, Settings, HelpCircle, LogOut,
  Edit, ShieldCheck, ShieldAlert, ShieldOff, AlertCircle,
} from 'lucide-react';

interface ProfileScreenProps {
  onEditProfile?: () => void;
  onKyc?: () => void;
  onPaymentMethods?: () => void;
  onTaskHistory?: () => void;
  onSettings?: () => void;
  onSupport?: () => void;
  onLogout?: () => void;
}

type KycStatus = 'not_submitted' | 'pending' | 'approved' | 'rejected';

interface UserProfile {
  id: string;
  email: string;
  role: string;
  first_name: string | null;
  last_name: string | null;
  full_name: string | null;
  phone: string | null;
  avatar_url: string | null;
  country_code: string | null;
  is_verified: boolean;
}


function KycBadge({ status }: { status: KycStatus }) {
  if (status === 'approved') {
    return (
      <div className="flex items-center gap-1.5 bg-green-500/20 rounded-full px-3 py-1">
        <ShieldCheck size={14} className="text-green-300" />
        <span className="text-xs font-semibold text-green-200">Verified</span>
      </div>
    );
  }
  if (status === 'pending') {
    return (
      <div className="flex items-center gap-1.5 bg-amber-500/20 rounded-full px-3 py-1">
        <ShieldAlert size={14} className="text-amber-300" />
        <span className="text-xs font-semibold text-amber-200">Pending KYC</span>
      </div>
    );
  }
  return (
    <div className="flex items-center gap-1.5 bg-red-500/20 rounded-full px-3 py-1">
      <ShieldOff size={14} className="text-red-300" />
      <span className="text-xs font-semibold text-red-200">Verify ID</span>
    </div>
  );
}

export function ProfileScreen({
  onEditProfile,
  onKyc,
  onPaymentMethods,
  onTaskHistory,
  onSettings,
  onSupport,
  onLogout,
}: ProfileScreenProps = {}) {
  const [kycStatus, setKycStatus] = useState<KycStatus>('not_submitted');
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    if (!apiClient.getAccessToken()) return;

    Promise.all([
      apiClient.get<UserProfile>('/users/me'),
      apiClient.get<{ status: KycStatus }>('/kyc/status'),
    ])
      .then(([profileData, kycData]) => {
        setProfile(profileData);
        setKycStatus(kycData.status);
      })
      .catch((err) => {
        setLoadError(err instanceof Error ? err.message : 'Failed to load profile');
      });
  }, []);

  const displayName = profile
    ? `${profile.first_name ?? ''} ${profile.last_name ?? ''}`.trim() || profile.email
    : '…';
  const displayEmail = profile?.email ?? '';
  const avatarName = displayName !== '…' ? displayName : 'U';

  const menuItems = [
    { id: 1, title: 'Payment methods', icon: CreditCard, color: '#6D28D9', onClick: onPaymentMethods },
    { id: 2, title: 'Task history', icon: Clock, color: '#1E40AF', onClick: onTaskHistory },
    { id: 3, title: 'Settings', icon: Settings, color: '#64748B', onClick: onSettings },
    { id: 4, title: 'Help & support', icon: HelpCircle, color: '#22C55E', onClick: onSupport },
  ];

  return (
    <div className="h-full overflow-auto pb-24 bg-gray-50">
      <div className="px-6 pt-8 pb-6 bg-gradient-to-br from-[#6D28D9] to-[#5B21B6]">
        <div className="flex items-center gap-4 mb-4">
          <Avatar name={avatarName} size="xl" />
          <div className="flex-1 min-w-0">
            <h2 className="text-xl font-bold text-white">{displayName}</h2>
            <p className="text-white/75 text-sm truncate">{displayEmail}</p>
            <div className="mt-2">
              <KycBadge status={kycStatus} />
            </div>
          </div>
          {onEditProfile && (
            <button
              onClick={onEditProfile}
              className="w-9 h-9 rounded-full bg-white/15 hover:bg-white/25 backdrop-blur-sm flex items-center justify-center transition-colors border border-white/10 flex-shrink-0"
            >
              <Edit size={16} className="text-white" />
            </button>
          )}
        </div>

        {profile && (
          <div className="grid grid-cols-2 gap-3">
            <div className="bg-white/15 backdrop-blur-sm rounded-2xl p-4 border border-white/10">
              <p className="text-white/70 text-xs font-medium mb-1">Rôle</p>
              <p className="text-lg font-bold text-white capitalize">{profile.role}</p>
            </div>
            <div className="bg-white/15 backdrop-blur-sm rounded-2xl p-4 border border-white/10">
              <p className="text-white/70 text-xs font-medium mb-1">Pays</p>
              <p className="text-lg font-bold text-white">{profile.country_code ?? '—'}</p>
            </div>
          </div>
        )}
      </div>

      <div className="px-6 py-4">
        {kycStatus !== 'approved' && onKyc && (
          <Card
            onClick={onKyc}
            className="mb-4 border-amber-200 bg-amber-50 hover:shadow-lg transition-all"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-xl bg-amber-100 flex items-center justify-center">
                  <ShieldAlert size={18} className="text-amber-600" strokeWidth={2.5} />
                </div>
                <div>
                  <span className="font-medium text-amber-900 text-sm">
                    {kycStatus === 'pending' ? 'KYC under review' : 'Verify your identity'}
                  </span>
                  <p className="text-xs text-amber-600">
                    {kycStatus === 'pending' ? "We'll notify you when done" : 'Required to receive payments'}
                  </p>
                </div>
              </div>
              <ChevronRight size={18} className="text-amber-400" />
            </div>
          </Card>
        )}

        {loadError && (
          <div className="flex items-center gap-2 bg-red-50 border border-red-100 rounded-xl px-3 py-2 mb-4">
            <AlertCircle size={16} className="text-red-500 flex-shrink-0" />
            <p className="text-sm text-red-600">{loadError}</p>
          </div>
        )}
        <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3 px-1">Account</h3>
        <div className="space-y-2">
          {menuItems.map(item => {
            const Icon = item.icon;
            return (
              <Card key={item.id} onClick={item.onClick} className="hover:shadow-lg transition-all">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div
                      className="w-9 h-9 rounded-xl flex items-center justify-center"
                      style={{ backgroundColor: `${item.color}12` }}
                    >
                      <Icon size={18} style={{ color: item.color }} strokeWidth={2.5} />
                    </div>
                    <span className="font-medium text-gray-900">{item.title}</span>
                  </div>
                  <ChevronRight size={18} className="text-gray-400" />
                </div>
              </Card>
            );
          })}
        </div>

        <div className="mt-6">
          <Card onClick={onLogout} className="hover:shadow-lg transition-all border border-red-100">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-xl bg-red-50 flex items-center justify-center">
                  <LogOut size={18} className="text-red-600" strokeWidth={2.5} />
                </div>
                <span className="font-medium text-red-600">Sign out</span>
              </div>
              <ChevronRight size={18} className="text-red-300" />
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
