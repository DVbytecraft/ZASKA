import { useState } from 'react';
import { Button } from '../components/Button';
import { Camera, Loader2 } from 'lucide-react';
import { userService } from '@zaska/shared-services';

interface ProfileSetupScreenProps {
  onBack: () => void;
  onContinue: () => void;
}

export function ProfileSetupScreen({ onBack, onContinue }: ProfileSetupScreenProps) {
  const [name, setName] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleContinue = async () => {
    setLoading(true);
    setError(null);
    try {
      await userService.updateProfile({ full_name: name.trim() });
      onContinue();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erreur lors de la sauvegarde');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="h-full flex flex-col bg-white">
      <div className="px-6 pt-8 pb-6">
        <h2 className="text-2xl font-bold text-gray-900">Complétez votre profil</h2>
        <p className="text-sm text-gray-500 mt-1">Dernière étape avant de commencer</p>
      </div>

      <div className="flex-1 overflow-auto px-6">
        <div className="flex justify-center mb-8">
          <div className="relative">
            <div className="w-24 h-24 rounded-full bg-gray-100 flex items-center justify-center">
              <Camera size={32} className="text-gray-400" />
            </div>
            <button className="absolute bottom-0 right-0 w-8 h-8 bg-[#6D28D9] rounded-full flex items-center justify-center">
              <Camera size={16} className="text-white" />
            </button>
          </div>
        </div>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Nom complet</label>
            <input
              type="text"
              placeholder="Prénom Nom"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full px-4 py-3.5 rounded-xl border-2 border-gray-200 focus:border-[#6D28D9] focus:outline-none"
            />
          </div>
        </div>

        {error && (
          <p className="text-sm text-red-600 bg-red-50 rounded-xl px-3 py-2 mt-4">{error}</p>
        )}
      </div>

      <div className="px-6 py-4 border-t border-gray-100">
        <Button fullWidth onClick={handleContinue} disabled={!name.trim() || loading}>
          {loading ? (
            <span className="flex items-center justify-center gap-2">
              <Loader2 size={16} className="animate-spin" /> Sauvegarde...
            </span>
          ) : 'Commencer'}
        </Button>
      </div>
    </div>
  );
}
