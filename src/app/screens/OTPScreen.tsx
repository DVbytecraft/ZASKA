import { useState, useRef } from 'react';
import { Button } from '../components/Button';
import { ArrowLeft } from 'lucide-react';
import { useAuth } from '../hooks/useAuth';
import { authService } from '@zaska/shared-services';

interface OTPScreenProps {
  phone: string;
  onBack: () => void;
  onVerify: () => void;
}

export function OTPScreen({ phone, onBack, onVerify }: OTPScreenProps) {
  const [otp, setOtp] = useState(['', '', '', '', '', '']);
  const [resendLoading, setResendLoading] = useState(false);
  const [resendSent, setResendSent] = useState(false);
  const inputs = useRef<(HTMLInputElement | null)[]>([]);
  const { verifyOtp, loading, error } = useAuth();

  const handleChange = (index: number, value: string) => {
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

  const handleVerify = async () => {
    try {
      await verifyOtp(phone, otp.join(''));
      onVerify();
    } catch {
      // error already set in useAuth
    }
  };

  const handleResend = async () => {
    setResendLoading(true);
    setResendSent(false);
    try {
      await authService.resendOtp(phone);
      setResendSent(true);
    } catch {
      // ignore — user can retry
    } finally {
      setResendLoading(false);
    }
  };

  const isFull = otp.every(d => d !== '');

  return (
    <div className="h-full flex flex-col bg-white">
      <div className="px-6 pt-8 pb-6">
        <button onClick={onBack} className="p-2 -ml-2 hover:bg-gray-100 rounded-full transition-colors">
          <ArrowLeft size={24} className="text-gray-700" />
        </button>
      </div>

      <div className="flex-1 flex flex-col justify-center px-6">
        <div className="text-center mb-8">
          <h2 className="text-2xl font-bold text-gray-900 mb-2">Vérifiez votre téléphone</h2>
          <p className="text-gray-500 text-sm">Code envoyé au</p>
          <p className="text-gray-900 font-semibold text-sm mt-0.5">{phone}</p>
        </div>

        <div className="flex gap-2 justify-center mb-6">
          {otp.map((digit, index) => (
            <input
              key={index}
              ref={el => { inputs.current[index] = el; }}
              type="text"
              inputMode="numeric"
              maxLength={1}
              value={digit}
              onChange={(e) => handleChange(index, e.target.value)}
              onKeyDown={(e) => handleKeyDown(index, e)}
              className={`w-12 h-14 text-center text-2xl font-bold border-2 rounded-xl focus:outline-none transition-colors ${
                digit ? 'border-[#6D28D9] bg-purple-50' : 'border-gray-200'
              } focus:border-[#6D28D9]`}
            />
          ))}
        </div>

        {error && (
          <p className="text-sm text-red-600 text-center mb-4">{error}</p>
        )}

        <Button fullWidth onClick={handleVerify} disabled={!isFull || loading}>
          {loading ? 'Vérification...' : 'Vérifier mon numéro'}
        </Button>

        <div className="text-center mt-6">
          {resendSent ? (
            <p className="text-xs text-green-600 font-medium">Code renvoyé !</p>
          ) : (
            <>
              <p className="text-xs text-gray-400">Vous n'avez pas reçu le code ?</p>
              <button
                onClick={handleResend}
                disabled={resendLoading}
                className="text-[#6D28D9] font-semibold text-sm mt-1 disabled:opacity-50"
              >
                {resendLoading ? 'Envoi...' : 'Renvoyer le code'}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
