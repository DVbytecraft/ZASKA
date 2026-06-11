import { useTranslation } from 'react-i18next';
import { ArrowLeft, Bell, Shield, Globe, HelpCircle, LogOut, ChevronRight, PiggyBank } from 'lucide-react';
import { Card } from '../components/Card';
import { setUserLanguage } from '../../i18n';

interface SettingsScreenProps {
  onBack: () => void;
  onSupport: () => void;
  onLogout: () => void;
  onSocialProtection?: () => void;
}

const LANGUAGES = [
  { code: 'fr', label: 'Français' },
  { code: 'en', label: 'English' },
];

export function SettingsScreen({ onBack, onSupport, onLogout, onSocialProtection }: SettingsScreenProps) {
  const { t, i18n } = useTranslation();

  const currentLanguage = LANGUAGES.find((l) => l.code === i18n.language) ?? LANGUAGES[0];

  const toggleLanguage = () => {
    const next = LANGUAGES.find((l) => l.code !== currentLanguage.code) ?? LANGUAGES[0];
    setUserLanguage(next.code);
  };

  const settingsSections = [
    {
      title: t('settings.preferences'),
      items: [
        { icon: Bell, label: t('settings.notifications'), value: t('settings.enabled'), color: 'text-purple-600', bg: 'bg-purple-50' },
        { icon: Globe, label: t('settings.language'), value: currentLanguage.label, color: 'text-blue-600', bg: 'bg-blue-50', onClick: toggleLanguage },
      ]
    },
    {
      title: t('settings.privacySecurity'),
      items: [
        { icon: Shield, label: t('settings.privacyPolicy'), color: 'text-green-600', bg: 'bg-green-50' },
        { icon: Shield, label: t('settings.terms'), color: 'text-green-600', bg: 'bg-green-50' },
        ...(onSocialProtection
          ? [{ icon: PiggyBank, label: t('settings.myContributions'), color: 'text-purple-600', bg: 'bg-purple-50', onClick: onSocialProtection }]
          : []),
      ]
    },
    {
      title: t('settings.assistance'),
      items: [
        { icon: HelpCircle, label: t('settings.helpSupport'), color: 'text-orange-600', bg: 'bg-orange-50', onClick: onSupport },
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
          <h2 className="text-2xl font-bold text-gray-900">{t('settings.title')}</h2>
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
          <span className="font-semibold text-red-600">{t('settings.logout')}</span>
        </button>
      </div>
    </div>
  );
}
