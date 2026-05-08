import { Home, Briefcase, Wallet, User, Compass } from 'lucide-react';

interface BottomNavProps {
  activeTab: string;
  onTabChange: (tab: string) => void;
}

export function BottomNav({ activeTab, onTabChange }: BottomNavProps) {
  const tabs = [
    { id: 'home',    label: 'Accueil',  icon: Home },
    { id: 'explore', label: 'Explorer', icon: Compass },
    { id: 'tasks',   label: 'Tâches',   icon: Briefcase },
    { id: 'wallet',  label: 'Wallet',    icon: Wallet },
    { id: 'profile', label: 'Profil',   icon: User },
  ];

  return (
    <div className="fixed bottom-0 left-0 right-0 bg-white/95 backdrop-blur-lg border-t border-gray-200 px-1 pt-2 pb-safe shadow-2xl shadow-black/5">
      <div className="flex justify-around items-center max-w-md mx-auto">
        {tabs.map(tab => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => onTabChange(tab.id)}
              className={`flex flex-col items-center gap-1 px-3 py-2 rounded-xl transition-all ${
                isActive ? 'text-[#6D28D9] bg-[#6D28D9]/8' : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              <Icon size={21} strokeWidth={isActive ? 2.5 : 2} />
              <span className={`text-[10px] leading-tight ${isActive ? 'font-semibold' : 'font-medium'}`}>
                {tab.label}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
