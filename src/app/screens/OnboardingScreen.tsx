import { useState } from 'react';
import { Button } from '../components/Button';
import { CheckCircle2, Zap, Shield } from 'lucide-react';

interface OnboardingScreenProps {
  onComplete: () => void;
}

export function OnboardingScreen({ onComplete }: OnboardingScreenProps) {
  const [step, setStep] = useState(0);

  const screens = [
    {
      title: 'Publiez n\'importe quelle tâche',
      description: 'Trouvez de l\'aide en quelques minutes',
      icon: CheckCircle2,
      gradient: 'from-violet-600 to-purple-600'
    },
    {
      title: 'Mise en relation instantanée',
      description: 'Connectez-vous avec des prestataires vérifiés',
      icon: Zap,
      gradient: 'from-blue-600 to-indigo-600'
    },
    {
      title: 'Paiement sécurisé',
      description: 'Sûr et protégé',
      icon: Shield,
      gradient: 'from-green-600 to-emerald-600'
    }
  ];

  const current = screens[step];
  const Icon = current.icon;

  return (
    <div className="h-full bg-white flex flex-col">
      <div className="flex-1 flex flex-col items-center justify-center px-8 text-center">
        <div className={`w-28 h-28 rounded-3xl bg-gradient-to-br ${current.gradient} flex items-center justify-center mb-8 shadow-2xl`}>
          <Icon size={56} className="text-white" strokeWidth={2.5} />
        </div>

        <h2 className="text-3xl font-bold text-gray-900 mb-3">{current.title}</h2>
        <p className="text-gray-500 text-lg">{current.description}</p>
      </div>

      <div className="px-8 pb-12">
        <div className="flex justify-center gap-2 mb-8">
          {screens.map((_, index) => (
            <div
              key={index}
              className={`h-1.5 rounded-full transition-all duration-300 ${
                index === step ? 'w-8 bg-[#6D28D9]' : 'w-1.5 bg-gray-300'
              }`}
            />
          ))}
        </div>

        <Button
          fullWidth
          onClick={() => step < screens.length - 1 ? setStep(step + 1) : onComplete()}
        >
          {step < screens.length - 1 ? 'Continuer' : 'Commencer'}
        </Button>

        {step < screens.length - 1 && (
          <button
            onClick={onComplete}
            className="w-full text-gray-500 font-medium py-2"
          >
            Passer
          </button>
        )}
      </div>
    </div>
  );
}
