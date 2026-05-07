import { useState, useRef } from 'react';
import { ArrowLeft, Eye, EyeOff, Check, X } from 'lucide-react';
import { Button } from '../components/Button';
import { apiClient } from '@zaska/shared-services';

interface ResetPasswordScreenProps {
  phone: string;
  onBack: () => void;
  onSuccess: () => void;
}

export function ResetPasswordScreen({ phone, onBack, onSuccess }: ResetPasswordScreenProps) {
  const [otp, setOtp] = useState(['', '', '', '', '', '']);
  const [newPassword, setNewPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputs = useRef<(HTMLInputElement | null)[]>([]);

  const passwordRules = {
    length: newPassword.length >= 8,
    upper: /[A-Z]/.test(newPassword),
    digit: /\d/.test(newPassword),
  };
  const otpFull = otp.every(d => d !== '');
  const passwordValid = Object.values(passwordRules).every(Boolean);
  const canSubmit = otpFull && passwordValid;

  const handleOtpChange = (index: number, value: string) => {
    if (!/^\d*$/.test(value)) return;
    const next = [...otp];
    next[index] = value.slice(-1);
    setOtp(next);
    if (value && index < 5) inputs.current[index + 1]?.focus();
  };

  const handleKeyDown = (index: number, e: React.KeyboardEvent) => {
    if (e.key === 'Backspace' && !otp[index] && index > 0) {
      inputs.current[index - 1]?.focus();
    }
  };

  const handleSubmit = async () => {
    setLoading(true);
    setError(null);
    try {
      await apiClient.post('/auth/reset-password', {
        phone,
        code: otp.join(''),
        new_password: newPassword,
      });
      onSuccess();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Code invalide ou expiré');
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

      <div className="flex-1 overflow-auto px-6">
        <div className="mb-6">
          <h2 className="text-2xl font-bold text-gray-900 mb-1">Nouveau mot de passe</h2>
          <p className="text-gray-500 text-sm">Code envoyé au <span className="font-semibold text-gray-900">{phone}</span></p>
        </div>

        {/* OTP */}
        <div className="mb-6">
          <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">
            Code de vérification
          </label>
          <div className="flex gap-2 justify-start">
            {otp.map((digit, index) => (
              <input
                key={index}
                ref={el => { inputs.current[index] = el; }}
                type="text"
                inputMode="numeric"
                maxLength={1}
                value={digit}
                onChange={(e) => handleOtpChange(index, e.target.value)}
                onKeyDown={(e) => handleKeyDown(index, e)}
                className={`w-12 h-14 text-center text-2xl font-bold border-2 rounded-xl focus:outline-none transition-colors ${
                  digit ? 'border-[#6D28D9] bg-purple-50' : 'border-gray-200'
                } focus:border-[#6D28D9]`}
              />
            ))}
          </div>
        </div>

        {/* New password */}
        <div className="mb-6">
          <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">
            Nouveau mot de passe
          </label>
          <div className="relative">
            <input
              type={showPassword ? 'text' : 'password'}
              placeholder="••••••••"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
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
          {newPassword && (
            <div className="mt-2 grid grid-cols-3 gap-1">
              {[
                { ok: passwordRules.length, label: '8 car. min' },
                { ok: passwordRules.upper,  label: '1 majuscule' },
                { ok: passwordRules.digit,  label: '1 chiffre' },
              ].map(({ ok, label }) => (
                <div key={label} className="flex items-center gap-1">
                  {ok
                    ? <Check size={12} className="text-green-500 shrink-0" />
                    : <X size={12} className="text-gray-300 shrink-0" />}
                  <span className={`text-xs ${ok ? 'text-green-600' : 'text-gray-400'}`}>{label}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {error && (
          <p className="text-sm text-red-600 bg-red-50 rounded-xl px-3 py-2 mb-4">{error}</p>
        )}

        <Button fullWidth onClick={handleSubmit} disabled={!canSubmit || loading}>
          {loading ? 'Réinitialisation...' : 'Réinitialiser le mot de passe'}
        </Button>
      </div>
    </div>
  );
}
