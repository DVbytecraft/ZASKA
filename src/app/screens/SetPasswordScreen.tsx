import { useState } from 'react';
import { Eye, EyeOff, ArrowLeft, CheckCircle2 } from 'lucide-react';
import { ZaskaLogo } from '../components/ZaskaLogo';
import { useAuth } from '../hooks/useAuth';

interface SetPasswordScreenProps {
  email: string;
  onBack: () => void;
  onComplete: () => void;
}

export function SetPasswordScreen({ email, onBack, onComplete }: SetPasswordScreenProps) {
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const { setPassword: doSetPassword, login, loading, error } = useAuth();

  const rules = [
    { label: '8 caractères minimum', ok: password.length >= 8 },
    { label: 'Une majuscule', ok: /[A-Z]/.test(password) },
    { label: 'Un chiffre', ok: /\d/.test(password) },
  ];
  const allRules = rules.every(r => r.ok);
  const matches = password === confirm && confirm.length > 0;
  const isValid = allRules && matches;

  const handleSubmit = async () => {
    try {
      await doSetPassword(email, password);
      // Auto-login pour obtenir le token avant ProfileSetupScreen
      await login(email, password);
      onComplete();
    } catch {
      // error already set in useAuth
    }
  };

  return (
    <div className="h-full flex flex-col" style={{ fontFamily: "'Poppins', sans-serif" }}>
      {/* Header */}
      <div
        className="relative flex flex-col items-center justify-end pb-10 pt-14 px-6"
        style={{
          background: 'linear-gradient(160deg, #3B0764 0%, #6D28D9 60%, #7C3AED 100%)',
          minHeight: '35%',
        }}
      >
        <button
          onClick={onBack}
          className="absolute top-12 left-4 p-2 rounded-full hover:bg-white/10 transition-colors"
        >
          <ArrowLeft size={22} className="text-white/80" />
        </button>

        <div className="flex flex-col items-center">
          <ZaskaLogo size={64} className="mb-3 drop-shadow-lg" />
          <h1 className="text-white font-extrabold text-3xl tracking-tight">ZASKA</h1>
          <p className="text-white/70 text-sm font-medium mt-1">Choisissez votre mot de passe</p>
        </div>

        <svg className="absolute bottom-0 left-0 w-full" viewBox="0 0 390 40" preserveAspectRatio="none">
          <path d="M0 40 Q97.5 0 195 20 Q292.5 40 390 10 L390 40 Z" fill="white" />
        </svg>
      </div>

      {/* Form */}
      <div className="flex-1 bg-white flex flex-col px-6 pt-6 pb-4 overflow-auto">
        <div className="mb-6">
          <h2 className="text-2xl font-bold text-gray-900">Mot de passe</h2>
          <p className="text-sm text-gray-500 mt-1">Étape 3 sur 3 — Sécurisez votre compte</p>
        </div>

        <div className="space-y-4 mb-4">
          {/* Password */}
          <div>
            <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">
              Nouveau mot de passe
            </label>
            <div className="relative">
              <input
                type={showPassword ? 'text' : 'password'}
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-4 py-3.5 pr-12 rounded-xl border-2 border-gray-100 bg-gray-50 focus:bg-white focus:border-[#6D28D9] focus:outline-none transition-all text-gray-900 font-medium"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 p-1.5 text-gray-400"
              >
                {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </div>
          </div>

          {/* Confirm */}
          <div>
            <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">
              Confirmer le mot de passe
            </label>
            <div className="relative">
              <input
                type={showConfirm ? 'text' : 'password'}
                placeholder="••••••••"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                className={`w-full px-4 py-3.5 pr-12 rounded-xl border-2 bg-gray-50 focus:bg-white focus:outline-none transition-all text-gray-900 font-medium ${
                  confirm && !matches ? 'border-red-300 focus:border-red-400' : 'border-gray-100 focus:border-[#6D28D9]'
                }`}
              />
              <button
                type="button"
                onClick={() => setShowConfirm(!showConfirm)}
                className="absolute right-3 top-1/2 -translate-y-1/2 p-1.5 text-gray-400"
              >
                {showConfirm ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </div>
            {confirm && !matches && (
              <p className="text-xs text-red-500 mt-1">Les mots de passe ne correspondent pas</p>
            )}
          </div>
        </div>

        {/* Rules */}
        <div className="space-y-1.5 mb-6">
          {rules.map(r => (
            <div key={r.label} className="flex items-center gap-2">
              <CheckCircle2 size={14} className={r.ok ? 'text-green-500' : 'text-gray-300'} />
              <span className={`text-xs ${r.ok ? 'text-green-600' : 'text-gray-400'}`}>{r.label}</span>
            </div>
          ))}
        </div>

        {error && (
          <p className="text-sm text-red-600 bg-red-50 rounded-xl px-3 py-2 mb-4">{error}</p>
        )}

        <button
          onClick={handleSubmit}
          disabled={!isValid || loading}
          className="w-full py-4 rounded-xl font-bold text-base text-white transition-all shadow-md active:scale-[0.98]"
          style={{
            background: isValid && !loading
              ? 'linear-gradient(135deg, #6D28D9 0%, #7C3AED 100%)'
              : '#D1D5DB',
            boxShadow: isValid && !loading ? '0 4px 20px rgba(109,40,217,0.35)' : 'none',
          }}
        >
          {loading ? 'Création en cours...' : 'Créer mon mot de passe'}
        </button>
      </div>
    </div>
  );
}
