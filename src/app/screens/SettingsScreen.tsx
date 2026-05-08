import { ArrowLeft, Bell, Shield, Globe, HelpCircle, LogOut, ChevronRight } from 'lucide-react';
import { Card } from '../components/Card';

interface SettingsScreenProps {
  onBack: () => void;
  onSupport: () => void;
  onLogout: () => void;
}

export function SettingsScreen({ onBack, onSupport, onLogout }: SettingsScreenProps) {
  const settingsSections = [
    {
      title: 'Préférences',
      items: [
        { icon: Bell, label: 'Notifications', value: 'Activées', color: 'text-purple-600', bg: 'bg-purple-50' },
        { icon: Globe, label: 'Langue', value: 'Français', color: 'text-blue-600', bg: 'bg-blue-50' },
      ]
    },
    {
      title: 'Confidentialité & Sécurité',
      items: [
        { icon: Shield, label: 'Politique de confidentialité', color: 'text-green-600', bg: 'bg-green-50' },
        { icon: Shield, label: 'Conditions d\'utilisation', color: 'text-green-600', bg: 'bg-green-50' },
      ]
    },
    {
      title: 'Assistance',
      items: [
        { icon: HelpCircle, label: 'Aide & Support', color: 'text-orange-600', bg: 'bg-orange-50', onClick: onSupport },
      ]
    }
  ];

  return (
    <div className="h-full flex flex-col bg-gray-50">
      <div className="px-6 pt-8 pb-4 bg-white border-b border-gray-200">
        <div className="flex items-center gap-3">
          <button onClick={onBack} className="p-2 -ml-2 hover:bg-gray-100 rounded-full transition-colors">
            <ArrowLeft size={24} className="text-gray-700" />
          </button>
          <h2 className="text-2xl font-bold text-gray-900">Paramètres</h2>
        </div>
      </div>

      <div className="flex-1 overflow-auto p-6">
        {settingsSections.map((section, idx) => (
          <div key={idx} className="mb-6">
            <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3 px-1">
              {section.title}
            </h3>
            <div className="space-y-2">
              {section.items.map((item, itemIdx) => (
                <Card key={itemIdx} onClick={item.onClick} className="hover:shadow-md transition-all">
                  <div className="flex items-center gap-4">
                    <div className={`w-10 h-10 rounded-xl ${item.bg} flex items-center justify-center`}>
                      <item.icon size={20} className={item.color} />
                    </div>
                    <div className="flex-1">
                      <h4 className="font-medium text-gray-900">{item.label}</h4>
                      {item.value && <p className="text-sm text-gray-500">{item.value}</p>}
                    </div>
                    <ChevronRight size={20} className="text-gray-400" />
                  </div>
                </Card>
              ))}
            </div>
          </div>
        ))}

        <button
          onClick={onLogout}
          className="w-full mt-8 p-4 bg-white rounded-xl border border-red-200 hover:bg-red-50 transition-colors flex items-center justify-center gap-3"
        >
          <LogOut size={20} className="text-red-600" />
          <span className="font-semibold text-red-600">Se déconnecter</span>
        </button>
      </div>
    </div>
  );
}
