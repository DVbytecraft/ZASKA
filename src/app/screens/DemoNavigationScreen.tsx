import { Card } from '../components/Card';
import {
  Home,
  Briefcase,
  Wallet,
  User,
  Users,
  MessageCircle,
  CheckCircle,
  Shield,
  Headphones,
  ArrowRight
} from 'lucide-react';

interface DemoNavigationScreenProps {
  onNavigate: (screen: string) => void;
}

export function DemoNavigationScreen({ onNavigate }: DemoNavigationScreenProps) {
  const sections = [
    {
      title: 'Main App',
      screens: [
        { id: 'home', name: 'Home', icon: Home, color: 'purple' },
        { id: 'taskModeSelection', name: 'Choose Mode', icon: Briefcase, color: 'amber' },
        { id: 'applicants', name: 'View Applicants', icon: Users, color: 'green' },
        { id: 'taskDetail', name: 'Task Details', icon: CheckCircle, color: 'blue' }
      ]
    },
    {
      title: 'Communication',
      screens: [
        { id: 'taskChat', name: 'Chat with Tasker', icon: MessageCircle, color: 'blue' },
        { id: 'confirmCompletion', name: 'Confirm Completion', icon: CheckCircle, color: 'green' }
      ]
    },
    {
      title: 'Tasker Side',
      screens: [
        { id: 'taskerFastMode', name: 'Browse Tasks (Fast/Choose)', icon: Briefcase, color: 'indigo' },
        { id: 'taskerApply', name: 'Apply to Task', icon: Users, color: 'purple' }
      ]
    },
    {
      title: 'User Account',
      screens: [
        { id: 'wallet', name: 'Wallet', icon: Wallet, color: 'green' },
        { id: 'profile', name: 'Profile', icon: User, color: 'gray' }
      ]
    },
    {
      title: 'Admin & Support',
      screens: [
        { id: 'admin', name: 'Admin Dashboard (Mobile)', icon: Shield, color: 'red' },
        { id: 'adminDashboard', name: 'Admin Dashboard (Desktop)', icon: Shield, color: 'purple' },
        { id: 'callCenter', name: 'Call Center', icon: Headphones, color: 'orange' }
      ]
    }
  ];

  const colors = {
    purple: 'from-purple-500 to-purple-600',
    blue: 'from-blue-500 to-blue-600',
    green: 'from-green-500 to-green-600',
    amber: 'from-amber-500 to-amber-600',
    indigo: 'from-indigo-500 to-indigo-600',
    gray: 'from-gray-500 to-gray-600',
    red: 'from-red-500 to-red-600',
    orange: 'from-orange-500 to-orange-600'
  };

  return (
    <div className="h-full overflow-auto pb-24 bg-gray-50">
      <div className="px-6 pt-8 pb-6 bg-gradient-to-br from-[#6D28D9] to-[#5B21B6]">
        <h1 className="text-2xl font-bold text-white mb-1">Demo Navigation</h1>
        <p className="text-white/75 text-sm">Explore all ZASKA screens</p>
      </div>

      <div className="px-6 py-4 space-y-6">
        {sections.map(section => (
          <div key={section.title}>
            <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3 px-1">
              {section.title}
            </h3>
            <div className="space-y-2">
              {section.screens.map(screen => {
                const Icon = screen.icon;
                return (
                  <Card
                    key={screen.id}
                    onClick={() => onNavigate(screen.id)}
                    className="hover:shadow-lg transition-all cursor-pointer"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${
                          colors[screen.color as keyof typeof colors]
                        } flex items-center justify-center shadow-md`}>
                          <Icon size={20} className="text-white" strokeWidth={2.5} />
                        </div>
                        <span className="font-semibold text-gray-900">{screen.name}</span>
                      </div>
                      <ArrowRight size={20} className="text-gray-400" />
                    </div>
                  </Card>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
