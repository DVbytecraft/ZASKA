import { useState } from 'react';
import { ArrowLeft, Briefcase, User, Eye, EyeOff, Check, X, ChevronDown } from 'lucide-react';
import { useAuth } from '../hooks/useAuth';
import { useTurnstile } from '../components/TurnstileWidget';
import { SUPPORTED_COUNTRIES, type SupportedCountry } from '../config/countries';
import { setAppLanguage } from '../../i18n';
import { ZaskaLogo } from '../components/ZaskaLogo';

interface RegisterScreenProps {
  onBack: () => void;
  onRegistered: (phone: string, email?: string) => void;
}

function toNationalPhone(value: string, dialCode: string): string {
  const digits = value.replace(/\D/g, '');
  const callingCode = dialCode.replace(/\D/g, '');

  // Accept a pasted international number without duplicating the displayed prefix.
  return digits.startsWith(callingCode) ? digits.slice(callingCode.length) : digits;
}

export function RegisterScreen({ onBack, onRegistered }: RegisterScreenProps) {
  const [email, setEmail] = useState('');
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [phone, setPhone] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [role, setRole] = useState<'client' | 'tasker'>('client');
  const [selectedCountry, setSelectedCountry] = useState<SupportedCountry>(SUPPORTED_COUNTRIES[0]);
  const [showCountryPicker, setShowCountryPicker] = useState(false);
  const { register, loading, error } = useAuth();
  const { token: turnstileToken, isVerified, TurnstileWidget } = useTurnstile('register');

  const emailValid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
  const passwordRules = {
    length: password.length >= 8,
    upper: /[A-Z]/.test(password),
    digit: /\d/.test(password),
    special: /[!@#$%^&*]/.test(password),
  };
  const phoneE164 = `${selectedCountry.dialCode}${phone}`;
  const phoneValid = /^\+[1-9]\d{6,14}$/.test(phoneE164);
  const isValid =
    emailValid &&
    firstName.trim().length >= 2 &&
    lastName.trim().length >= 2 &&
    phoneValid &&
    Object.values(passwordRules).every(Boolean) &&
    isVerified;

  const handleRegister = async () => {
    try {
      await register({
        email: email.trim().toLowerCase() || undefined,
        firstName: firstName.trim(),
        lastName: lastName.trim(),
        phone: phoneE164,
        password,
        role,
        country: selectedCountry.code,
        cf_turnstile_response: turnstileToken ?? undefined,
      });
      onRegistered(phoneE164, email.trim().toLowerCase() || undefined);
    } catch {
      // error already set in useAuth
    }
  };

  return (
    <div className="h-full flex flex-col" style={{ fontFamily: "'Poppins', sans-serif" }}>
      {/* Country picker overlay */}
      {showCountryPicker && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-end">
          <div className="w-full bg-white rounded-t-3xl max-h-[70vh] flex flex-col">
            <div className="px-6 pt-5 pb-3 border-b border-gray-100">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold text-gray-900">Choisir votre pays</h3>
                <button onClick={() => setShowCountryPicker(false)} className="p-1 text-gray-400">
                  <X size={20} />
                </button>
              </div>
            </div>
            <div className="overflow-y-auto flex-1 px-4 py-2">
              {SUPPORTED_COUNTRIES.map((country) => (
                <button
                  key={country.code}
                  onClick={() => {
                    if (selectedCountry.code !== country.code) setPhone('');
                    setSelectedCountry(country);
                    setAppLanguage(country.code);
                    setShowCountryPicker(false);
                  }}
                  className={`w-full flex items-center gap-4 px-3 py-3.5 rounded-xl mb-1 transition-colors ${
                    selectedCountry.code === country.code
                      ? 'bg-purple-50 border border-[#6D28D9]'
                      : 'hover:bg-gray-50'
                  }`}
                >
                  <span className="text-3xl">{country.flag}</span>
                  <div className="flex-1 text-left">
                    <p className="font-semibold text-gray-900 text-sm">{country.name}</p>
                    <p className="text-xs text-gray-400">{country.dialCode} · {country.currency}</p>
                  </div>
                  {country.mobileMoneyEnabled && (
                    <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full font-medium">
                      Mobile Money
                    </span>
                  )}
                  {selectedCountry.code === country.code && (
                    <Check size={16} className="text-[#6D28D9]" />
                  )}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      <div
        className="relative flex flex-col items-center justify-end pb-10 pt-14 px-6"
        style={{
          background: 'linear-gradient(160deg, #3B0764 0%, #6D28D9 60%, #7C3AED 100%)',
          minHeight: '28%',
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
          <p className="text-white/70 text-sm font-medium mt-1">Créer un compte</p>
        </div>
        <svg className="absolute bottom-0 left-0 w-full" viewBox="0 0 390 40" preserveAspectRatio="none">
          <path d="M0 40 Q97.5 0 195 20 Q292.5 40 390 10 L390 40 Z" fill="white" />
        </svg>
      </div>

      <div className="flex-1 bg-white flex flex-col px-6 pt-5 pb-4 overflow-auto">
        <div className="mb-4">
          <h2 className="text-xl font-bold text-gray-900">Inscription</h2>
          <p className="text-xs text-gray-500 mt-0.5">Étape 1 sur 2 — Vos informations</p>
        </div>

        <div className="space-y-3 mb-4">
          {/* Pays */}
          <div>
            <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">
              Pays
            </label>
            <button
              onClick={() => setShowCountryPicker(true)}
              className="w-full px-4 py-3.5 rounded-xl border-2 border-gray-100 bg-gray-50 flex items-center gap-3 hover:border-[#6D28D9] transition-colors"
            >
              <span className="text-2xl">{selectedCountry.flag}</span>
              <div className="flex-1 text-left">
                <p className="font-semibold text-gray-900 text-sm">{selectedCountry.name}</p>
              </div>
              <span className="text-xs text-gray-400">{selectedCountry.currency}</span>
              <ChevronDown size={16} className="text-gray-400" />
            </button>
          </div>

          {/* Email */}
          <div>
            <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">
              Email
            </label>
            <input
              type="email"
              placeholder="vous@exemple.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className={`w-full px-4 py-3.5 rounded-xl border-2 bg-gray-50 focus:bg-white focus:outline-none transition-all text-gray-900 font-medium placeholder:font-normal placeholder:text-gray-400 ${
                email && !emailValid ? 'border-red-300 focus:border-red-400' : 'border-gray-100 focus:border-[#6D28D9]'
              }`}
            />
            {email && !emailValid && (
              <p className="text-xs text-red-500 mt-1">Adresse email invalide</p>
            )}
          </div>

          {/* Prénom / Nom */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">Prénom</label>
              <input
                type="text"
                placeholder="Jean"
                value={firstName}
                onChange={(e) => setFirstName(e.target.value)}
                className="w-full px-4 py-3.5 rounded-xl border-2 border-gray-100 bg-gray-50 focus:bg-white focus:border-[#6D28D9] focus:outline-none transition-all text-gray-900 font-medium placeholder:font-normal placeholder:text-gray-400"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">Nom</label>
              <input
                type="text"
                placeholder="Dupont"
                value={lastName}
                onChange={(e) => setLastName(e.target.value)}
                className="w-full px-4 py-3.5 rounded-xl border-2 border-gray-100 bg-gray-50 focus:bg-white focus:border-[#6D28D9] focus:outline-none transition-all text-gray-900 font-medium placeholder:font-normal placeholder:text-gray-400"
              />
            </div>
          </div>

          {/* Téléphone */}
          <div>
            <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">
              Téléphone
            </label>
            <div className="flex gap-2">
              <div className="flex items-center px-3 rounded-xl border-2 border-gray-100 bg-gray-50 text-sm text-gray-600 font-medium whitespace-nowrap">
                {selectedCountry.flag} {selectedCountry.dialCode}
              </div>
              <input
                type="tel"
                name="phone-national"
                inputMode="numeric"
                autoComplete="tel-national"
                pattern="[0-9]*"
                placeholder="90123456"
                value={phone}
                onChange={(e) => setPhone(toNationalPhone(e.target.value, selectedCountry.dialCode))}
                className={`flex-1 px-4 py-3.5 rounded-xl border-2 bg-gray-50 focus:bg-white focus:outline-none transition-all text-gray-900 font-medium placeholder:font-normal placeholder:text-gray-400 ${
                  phone && !phoneValid ? 'border-red-300 focus:border-red-400' : 'border-gray-100 focus:border-[#6D28D9]'
                }`}
              />
            </div>
            {phone && !phoneValid && (
              <p className="text-xs text-red-500 mt-1">Format: {selectedCountry.dialCode}XXXXXXXX</p>
            )}
          </div>

          {/* Mot de passe */}
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
            {password && (
              <div className="mt-2 grid grid-cols-2 gap-1">
                {[
                  { ok: passwordRules.length, label: '8 caractères min' },
                  { ok: passwordRules.upper, label: '1 majuscule' },
                  { ok: passwordRules.digit, label: '1 chiffre' },
                  { ok: passwordRules.special, label: '1 car. spécial' },
                ].map(({ ok, label }) => (
                  <div key={label} className="flex items-center gap-1">
                    {ok ? <Check size={12} className="text-green-500 shrink-0" /> : <X size={12} className="text-gray-300 shrink-0" />}
                    <span className={`text-xs ${ok ? 'text-green-600' : 'text-gray-400'}`}>{label}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Rôle */}
          <div>
            <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Je suis</label>
            <div className="grid grid-cols-2 gap-3">
              {(['client', 'tasker'] as const).map((r) => (
                <button
                  key={r}
                  onClick={() => setRole(r)}
                  className={`flex flex-col items-center gap-2 py-4 rounded-xl border-2 transition-all ${
                    role === r ? 'border-[#6D28D9] bg-purple-50' : 'border-gray-100 bg-gray-50'
                  }`}
                >
                  {r === 'client'
                    ? <User size={24} className={role === r ? 'text-[#6D28D9]' : 'text-gray-400'} />
                    : <Briefcase size={24} className={role === r ? 'text-[#6D28D9]' : 'text-gray-400'} />
                  }
                  <div>
                    <p className={`text-sm font-bold ${role === r ? 'text-[#6D28D9]' : 'text-gray-700'}`}>
                      {r === 'client' ? 'Client' : 'Tasker'}
                    </p>
                    <p className="text-xs text-gray-400">{r === 'client' ? 'Je cherche' : 'Je propose'}</p>
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>

        {error && <p className="text-sm text-red-600 bg-red-50 rounded-xl px-3 py-2 mb-3">{error}</p>}

        <div className="flex justify-center mb-3">
          {TurnstileWidget}
        </div>

        <button
          onClick={handleRegister}
          disabled={!isValid || loading}
          className="w-full py-4 rounded-xl font-bold text-base text-white transition-all shadow-md active:scale-[0.98]"
          style={{
            background: isValid && !loading ? 'linear-gradient(135deg, #6D28D9 0%, #7C3AED 100%)' : '#D1D5DB',
            boxShadow: isValid && !loading ? '0 4px 20px rgba(109,40,217,0.35)' : 'none',
          }}
        >
          {loading ? 'Création en cours...' : 'Créer mon compte'}
        </button>

        <div className="text-center mt-4">
          <span className="text-sm text-gray-500">Déjà un compte ? </span>
          <button onClick={onBack} className="text-sm font-bold text-[#6D28D9]">Se connecter</button>
        </div>
      </div>
    </div>
  );
}
