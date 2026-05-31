import { useState } from 'react';
import { Eye, EyeOff, ArrowLeft } from 'lucide-react';
import { useAuth } from '../hooks/useAuth';
import { useTurnstile } from '../components/TurnstileWidget';
import { setAppLanguage } from '../../i18n';

interface LoginScreenProps {
  onBack: () => void;
  onLogin: () => void;
  onSignup: () => void;
  onForgotPassword: () => void;
}

export function LoginScreen({ onBack, onLogin, onSignup, onForgotPassword }: LoginScreenProps) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const { login, loading, error } = useAuth();
  const { token: turnstileToken, isVerified, TurnstileWidget } = useTurnstile('login');

  const handleContinue = async () => {
    try {
      const session = await login(email, password, turnstileToken ?? undefined);
      setAppLanguage(session?.country);
      onLogin();
    } catch {
      // error already set in useAuth
    }
  };

  const emailValid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
  const isValid = emailValid && password.length >= 8 && isVerified;

  return (
    <div className="h-full flex flex-col" style={{ fontFamily: "'Poppins', sans-serif" }}>
      {/* Hero gradient */}
      <div
        className="relative flex flex-col items-center justify-end pb-10 pt-14 px-6"
        style={{
          background: 'linear-gradient(160deg, #3B0764 0%, #6D28D9 60%, #7C3AED 100%)',
          minHeight: '42%',
        }}
      >
        <button
          onClick={onBack}
          className="absolute top-12 left-4 p-2 rounded-full hover:bg-white/10 transition-colors"
        >
          <ArrowLeft size={22} className="text-white/80" />
        </button>

        <div className="flex flex-col items-center">
          <div
            className="w-16 h-16 rounded-2xl flex items-center justify-center mb-3 shadow-lg"
            style={{ background: 'rgba(255,255,255,0.15)', backdropFilter: 'blur(8px)', border: '1px solid rgba(255,255,255,0.25)' }}
          >
            <span className="text-white font-extrabold text-2xl tracking-tight">Z</span>
          </div>
          <h1 className="text-white font-extrabold text-3xl tracking-tight">ZASKA</h1>
          <p className="text-white/70 text-sm font-medium mt-1">Services à la demande</p>
        </div>

        <svg
          className="absolute bottom-0 left-0 w-full"
          viewBox="0 0 390 40"
          preserveAspectRatio="none"
          style={{ display: 'block' }}
        >
          <path d="M0 40 Q97.5 0 195 20 Q292.5 40 390 10 L390 40 Z" fill="white" />
        </svg>
      </div>

      {/* Form section */}
      <div className="flex-1 bg-white flex flex-col px-6 pt-6 pb-4 overflow-auto">
        <div className="mb-7">
          <h2 className="text-2xl font-bold text-gray-900">Connexion</h2>
          <p className="text-sm text-gray-500 mt-1 font-medium">Entrez vos identifiants pour continuer</p>
        </div>

        <div className="space-y-4 mb-6">
          <div>
            <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">
              Email
            </label>
            <input
              type="email"
              placeholder="nom@exemple.com"
              value={email}
              onChange={(e) => setEmail(e.target.value.trim())}
              className={`w-full px-4 py-3.5 rounded-xl border-2 bg-gray-50 focus:bg-white focus:outline-none transition-all text-gray-900 font-medium placeholder:font-normal placeholder:text-gray-400 ${
                email && !emailValid ? 'border-red-300 focus:border-red-400' : 'border-gray-100 focus:border-[#6D28D9]'
              }`}
            />
            {email && !emailValid && (
              <p className="text-xs text-red-500 mt-1">Adresse email invalide</p>
            )}
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">
              Mot de passe
            </label>
            <div className="relative">
              <input
                type={showPassword ? 'text' : 'password'}
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-4 py-3.5 pr-12 rounded-xl border-2 border-gray-100 bg-gray-50 focus:bg-white focus:border-[#6D28D9] focus:outline-none transition-all text-gray-900 font-medium placeholder:font-normal placeholder:text-gray-400"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 p-1.5 text-gray-400 hover:text-gray-600 transition-colors"
              >
                {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </div>
            <div className="flex justify-end mt-1.5">
              <button onClick={onForgotPassword} className="text-xs font-semibold text-[#6D28D9]">
                Mot de passe oublié ?
              </button>
            </div>
          </div>
        </div>

        {error && (
          <p className="text-sm text-red-600 bg-red-50 rounded-xl px-3 py-2">{error}</p>
        )}

        <div className="flex justify-center mb-4">
          {TurnstileWidget}
        </div>

        <button
          onClick={handleContinue}
          disabled={!isValid || loading}
          className="w-full py-4 rounded-xl font-bold text-base text-white transition-all shadow-md active:scale-[0.98]"
          style={{
            background: isValid && !loading
              ? 'linear-gradient(135deg, #6D28D9 0%, #7C3AED 100%)'
              : '#D1D5DB',
            boxShadow: isValid && !loading ? '0 4px 20px rgba(109,40,217,0.35)' : 'none',
          }}
        >
          {loading ? 'Connexion en cours...' : 'Se connecter'}
        </button>

        <div className="flex-1" />

        <div className="text-center mt-6">
          <span className="text-sm text-gray-500">Pas encore de compte ? </span>
          <button onClick={onSignup} className="text-sm font-bold text-[#6D28D9]">
            S'inscrire
          </button>
        </div>

        <p className="text-center text-xs text-gray-400 mt-4 leading-relaxed">
          En continuant, vous acceptez nos{' '}
          <span className="text-[#6D28D9] font-medium">Conditions d'utilisation</span>{' '}
          et notre{' '}
          <span className="text-[#6D28D9] font-medium">Politique de confidentialité</span>
        </p>
      </div>
    </div>
  );
}
