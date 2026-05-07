import { useState } from 'react';
import { ArrowLeft } from 'lucide-react';
import { Button } from '../components/Button';
import { apiClient } from '@zaska/shared-services';

interface ForgotPasswordScreenProps {
  onBack: () => void;
  onCodeSent: (phone: string) => void;
}

export function ForgotPasswordScreen({ onBack, onCodeSent }: ForgotPasswordScreenProps) {
  const [phone, setPhone] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const phoneValid = /^\+[1-9]\d{6,14}$/.test(phone);

  const handleSubmit = async () => {
    setLoading(true);
    setError(null);
    try {
      await apiClient.post('/auth/forgot-password', { phone: phone.trim() });
      onCodeSent(phone.trim());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erreur lors de l\'envoi du code');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="h-full flex flex-col bg-white">
      <div className="px-6 pt-8 pb-6">
        <button onClick={onBack} className="p-2 -ml-2 hover:bg-gray-100 rounded-full transition-colors">
          <ArrowLeft size={24} className="text-gray-700" />
        </button>
      </div>

      <div className="flex-1 flex flex-col justify-center px-6">
        <div className="mb-8">
          <h2 className="text-2xl font-bold text-gray-900 mb-2">Mot de passe oublié</h2>
          <p className="text-gray-500 text-sm">
            Entrez votre numéro de téléphone. Nous vous enverrons un code pour réinitialiser votre mot de passe.
          </p>
        </div>

        <div className="space-y-4 mb-6">
          <div>
            <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">
              Téléphone
            </label>
            <input
              type="tel"
              placeholder="+221701234567"
              value={phone}
              onChange={(e) => setPhone(e.target.value.trim())}
              className={`w-full px-4 py-3.5 rounded-xl border-2 bg-gray-50 focus:bg-white focus:outline-none transition-all text-gray-900 font-medium placeholder:font-normal placeholder:text-gray-400 ${
                phone && !phoneValid ? 'border-red-300 focus:border-red-400' : 'border-gray-100 focus:border-[#6D28D9]'
              }`}
            />
            {phone && !phoneValid && (
              <p className="text-xs text-red-500 mt-1">Format : +221XXXXXXXXX</p>
            )}
          </div>
        </div>

        {error && (
          <p className="text-sm text-red-600 bg-red-50 rounded-xl px-3 py-2 mb-4">{error}</p>
        )}

        <Button fullWidth onClick={handleSubmit} disabled={!phoneValid || loading}>
          {loading ? 'Envoi...' : 'Envoyer le code'}
        </Button>
      </div>
    </div>
  );
}
