import { Home, Briefcase, Wallet, User } from 'lucide-react';

interface BottomNavProps {
  activeTab: string;
  onTabChange: (tab: string) => void;
}

export function BottomNav({ activeTab, onTabChange }: BottomNavProps) {
  const tabs = [
    { id: 'home', label: 'Home', icon: Home },
    { id: 'tasks', label: 'Tasks', icon: Briefcase },
    { id: 'wallet', label: 'Wallet', icon: Wallet },
    { id: 'profile', label: 'Profile', icon: User }
  ];

  return (
    <div className="fixed bottom-0 left-0 right-0 bg-white/95 backdrop-blur-lg border-t border-gray-200 px-2 pt-2 pb-safe shadow-2xl shadow-black/5">
      <div className="flex justify-around items-center max-w-md mx-auto">
        {tabs.map(tab => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => onTabChange(tab.id)}
              className={`flex flex-col items-center gap-1 px-5 py-2.5 rounded-xl transition-all ${
                isActive ? 'text-[#6D28D9] bg-[#6D28D9]/8' : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              <Icon size={22} strokeWidth={isActive ? 2.5 : 2} />
              <span className={`text-xs ${isActive ? 'font-semibold' : 'font-medium'}`}>
                {tab.label}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
