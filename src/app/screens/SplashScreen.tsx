import { useEffect } from 'react';
import { ZaskaLogo } from '../components/ZaskaLogo';

interface SplashScreenProps {
  onComplete: () => void;
}

export function SplashScreen({ onComplete }: SplashScreenProps) {
  useEffect(() => {
    const timer = setTimeout(onComplete, 2000);
    return () => clearTimeout(timer);
  }, [onComplete]);

  return (
    <div className="h-full bg-gradient-to-br from-[#6D28D9] via-[#5B21B6] to-[#4C1D95] flex flex-col items-center justify-center relative overflow-hidden">
      <div className="absolute inset-0 opacity-10">
        <div className="absolute top-20 left-10 w-72 h-72 bg-white rounded-full blur-3xl"></div>
        <div className="absolute bottom-20 right-10 w-96 h-96 bg-white rounded-full blur-3xl"></div>
      </div>

      <div className="relative z-10 text-center">
        <div className="flex flex-col items-center mb-4">
          <ZaskaLogo size={96} className="mb-4 drop-shadow-2xl" />
          <h1 className="text-4xl font-extrabold text-white tracking-tight">ZASKA</h1>
        </div>
        <p className="text-lg text-white/80 font-medium tracking-wide">Make it happen</p>
      </div>
    </div>
  );
}
