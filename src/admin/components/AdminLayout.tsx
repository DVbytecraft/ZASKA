import { ReactNode, useEffect, useState } from 'react';
import { ZaskaLogo } from '../../app/components/ZaskaLogo';
import { apiClient } from '@zaska/shared-services';
import {
  LayoutDashboard,
  Briefcase,
  Users,
  UserCheck,
  DollarSign,
  ReceiptText,
  Wallet,
  AlertTriangle,
  BarChart2,
  Globe,
  Headphones,
  Settings,
  Search,
  Bell,
  ChevronRight,
  LogOut,
  ShieldCheck,
  ClipboardList,
  ShieldAlert,
  HeartHandshake,
  Menu,
  X,
  UserCog,
} from 'lucide-react';

interface AdminLayoutProps {
  children: ReactNode;
  activePage: string;
  onNavigate: (page: string) => void;
}

const navigation = [
  { id: 'dashboard',  label: 'Dashboard',      icon: LayoutDashboard },
  { id: 'analytics',  label: 'Analytics',       icon: BarChart2 },
  { id: 'accounting', label: 'Comptabilité',    icon: ReceiptText },
  { id: 'tasks',      label: 'Tâches',           icon: Briefcase },
  { id: 'users',      label: 'Utilisateurs',     icon: Users },
  { id: 'taskers',    label: 'Taskers',           icon: UserCheck },
  { id: 'payments',   label: 'Paiements',         icon: DollarSign },
  { id: 'wallet',     label: 'Portefeuille',      icon: Wallet },
  { id: 'disputes',   label: 'Litiges',           icon: AlertTriangle },
  { id: 'callcenter', label: 'Call Center',       icon: Headphones },
  { id: 'countries',  label: 'Pays & Tarifs',     icon: Globe },
  { id: 'social',     label: 'Fonds sociaux',     icon: HeartHandshake },
  { id: 'kyc',        label: 'KYC',               icon: ShieldCheck },
  { id: 'auditlog',   label: 'Journal d\'audit',  icon: ClipboardList },
  { id: 'fraud',      label: 'Fraude',            icon: ShieldAlert },
  { id: 'staff',      label: 'Équipe',            icon: UserCog },
];

const bottomNav = [
  { id: 'settings', label: 'Paramètres', icon: Settings },
];

function useAdminProfile() {
  const BASE_URL = (typeof import.meta !== 'undefined' && (import.meta as any).env?.VITE_API_URL)
    ? (import.meta as any).env.VITE_API_URL as string
    : 'http://localhost:6969/api';
  const [email, setEmail] = useState('');
  const [initials, setInitials] = useState('?');
  useEffect(() => {
    const token = apiClient.getAccessToken();
    if (!token) return;
    fetch(`${BASE_URL}/users/me`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.json())
      .then((j) => {
        const d = j?.data;
        if (!d) return;
        setEmail(d.email ?? '');
        const fn = d.first_name ?? '';
        const ln = d.last_name ?? '';
        const full = d.full_name ?? '';
        const name = fn || full;
        setInitials((name[0] ?? (ln[0] ?? '?')).toUpperCase());
      })
      .catch(() => {});
  }, []);
  return { email, initials };
}

export function AdminLayout({ children, activePage, onNavigate }: AdminLayoutProps) {
  const { email, initials } = useAdminProfile();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const handleNavigate = (page: string) => {
    onNavigate(page);
    setSidebarOpen(false);
  };

  return (
    <div className="h-screen flex bg-[#F5F5FA]" style={{ fontFamily: "'Poppins', sans-serif" }}>
      {/* Mobile backdrop */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <div
        className={`fixed inset-y-0 left-0 z-40 w-60 flex flex-col shadow-xl flex-shrink-0 transform transition-transform duration-200 ease-in-out lg:static lg:translate-x-0 ${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
        style={{
          background: 'linear-gradient(180deg, #2E1065 0%, #4C1D95 40%, #5B21B6 100%)',
        }}
      >
        {/* Brand */}
        <div className="px-5 py-6 border-b border-white/10">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <ZaskaLogo size={36} />
              <div>
                <p className="text-white font-extrabold text-lg leading-tight tracking-tight">ZASKA</p>
                <p className="text-purple-300 text-xs font-medium leading-tight">Admin Panel</p>
              </div>
            </div>
            <button
              className="p-1.5 rounded-lg hover:bg-white/10 transition-colors text-purple-300 hover:text-white lg:hidden"
              onClick={() => setSidebarOpen(false)}
            >
              <X size={18} />
            </button>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
          {navigation.map(item => {
            const Icon = item.icon;
            const isActive = activePage === item.id;
            return (
              <button
                key={item.id}
                onClick={() => handleNavigate(item.id)}
                className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all group"
                style={{
                  background: isActive ? 'rgba(255,255,255,0.15)' : 'transparent',
                  color: isActive ? '#ffffff' : 'rgba(196,181,253,0.85)',
                }}
              >
                <Icon
                  size={18}
                  strokeWidth={isActive ? 2.5 : 1.8}
                  className="flex-shrink-0 transition-all"
                  style={{ color: isActive ? '#E9D5FF' : 'rgba(196,181,253,0.7)' }}
                />
                <span className="flex-1 text-left">{item.label}</span>
                {isActive && <ChevronRight size={14} className="text-purple-300 opacity-70" />}
              </button>
            );
          })}
        </nav>

        {/* Bottom nav */}
        <div className="px-3 pb-3 space-y-0.5">
          {bottomNav.map(item => {
            const Icon = item.icon;
            const isActive = activePage === item.id;
            return (
              <button
                key={item.id}
                onClick={() => handleNavigate(item.id)}
                className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all"
                style={{
                  background: isActive ? 'rgba(255,255,255,0.15)' : 'transparent',
                  color: isActive ? '#ffffff' : 'rgba(196,181,253,0.85)',
                }}
              >
                <Icon size={18} strokeWidth={1.8} style={{ color: 'rgba(196,181,253,0.7)' }} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </div>

        {/* User footer */}
        <div className="px-4 py-4 border-t border-white/10">
          <div className="flex items-center gap-3">
            <div
              className="w-9 h-9 rounded-xl flex items-center justify-center text-white font-bold text-sm flex-shrink-0"
              style={{ background: 'linear-gradient(135deg, #7C3AED 0%, #4F46E5 100%)' }}
            >
              {initials}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-white text-xs font-semibold truncate">Admin</p>
              <p className="text-purple-300 text-xs truncate">{email || '—'}</p>
            </div>
            <button className="p-1.5 rounded-lg hover:bg-white/10 transition-colors text-purple-300 hover:text-white">
              <LogOut size={15} />
            </button>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden min-w-0">
        {/* Top Bar */}
        <div className="h-14 bg-white border-b border-gray-200/80 flex items-center justify-between px-3 sm:px-6 shadow-sm flex-shrink-0">
          <div className="flex items-center gap-2 flex-1 min-w-0">
            <button
              className="p-2 hover:bg-gray-100 rounded-lg transition-colors text-gray-600 flex-shrink-0 lg:hidden"
              onClick={() => setSidebarOpen(true)}
            >
              <Menu size={20} />
            </button>
            <div className="flex-1 max-w-md min-w-0 hidden sm:block">
              <div className="relative">
                <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                <input
                  type="text"
                  placeholder="Rechercher tâches, utilisateurs..."
                  className="w-full pl-9 pr-4 py-2 border border-gray-200 rounded-lg text-sm bg-gray-50 focus:bg-white focus:outline-none focus:ring-2 focus:border-transparent transition-all placeholder:text-gray-400"
                  style={{ '--tw-ring-color': '#6D28D9' } as React.CSSProperties}
                />
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2 sm:gap-3 ml-2 sm:ml-4 flex-shrink-0">
            <button className="relative p-2 hover:bg-gray-100 rounded-lg transition-colors sm:hidden">
              <Search size={18} className="text-gray-600" />
            </button>
            <button className="relative p-2 hover:bg-gray-100 rounded-lg transition-colors">
              <Bell size={18} className="text-gray-600" />
              <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-red-500 rounded-full border border-white" />
            </button>
            <div
              className="w-8 h-8 rounded-lg flex items-center justify-center text-white font-bold text-xs"
              style={{ background: 'linear-gradient(135deg, #6D28D9 0%, #7C3AED 100%)' }}
            >
              {initials}
            </div>
          </div>
        </div>

        {/* Page Content */}
        <div className="flex-1 overflow-auto">
          {children}
        </div>
      </div>
    </div>
  );
}
