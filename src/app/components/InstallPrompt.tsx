import { useEffect, useState } from 'react';
import { Download, X, Smartphone } from 'lucide-react';

interface BeforeInstallPromptEvent extends Event {
  prompt(): Promise<void>;
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>;
}

export function InstallPrompt() {
  const [deferredPrompt, setDeferredPrompt] = useState<BeforeInstallPromptEvent | null>(null);
  const [show, setShow] = useState(false);
  const [isIos, setIsIos] = useState(false);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    const alreadyDismissed = sessionStorage.getItem('pwa-install-dismissed');
    if (alreadyDismissed) return;

    // iOS detection
    const ua = navigator.userAgent;
    const ios = /iphone|ipad|ipod/i.test(ua) && !(window as unknown as Record<string, unknown>).MSStream;
    const standalone = (navigator as unknown as Record<string, unknown>).standalone === true
      || window.matchMedia('(display-mode: standalone)').matches;

    if (ios && !standalone) {
      setIsIos(true);
      setTimeout(() => setShow(true), 3000);
      return;
    }

    const handler = (e: Event) => {
      e.preventDefault();
      setDeferredPrompt(e as BeforeInstallPromptEvent);
      setTimeout(() => setShow(true), 3000);
    };
    window.addEventListener('beforeinstallprompt', handler);
    return () => window.removeEventListener('beforeinstallprompt', handler);
  }, []);

  const dismiss = () => {
    setShow(false);
    setDismissed(true);
    sessionStorage.setItem('pwa-install-dismissed', '1');
  };

  const install = async () => {
    if (!deferredPrompt) return;
    await deferredPrompt.prompt();
    const { outcome } = await deferredPrompt.userChoice;
    if (outcome === 'accepted') {
      setShow(false);
      setDeferredPrompt(null);
    }
  };

  if (!show || dismissed) return null;

  if (isIos) {
    return (
      <div className="fixed bottom-20 left-4 right-4 z-50 animate-in slide-in-from-bottom-4">
        <div className="bg-white rounded-2xl shadow-2xl border border-gray-100 p-4">
          <button onClick={dismiss} className="absolute top-3 right-3 p-1 rounded-full hover:bg-gray-100">
            <X size={16} className="text-gray-400" />
          </button>
          <div className="flex items-start gap-3">
            <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-[#6D28D9] to-[#5B21B6] flex items-center justify-center flex-shrink-0">
              <Smartphone size={22} className="text-white" />
            </div>
            <div className="flex-1 pr-6">
              <p className="font-bold text-gray-900 text-sm">Installer Zaska</p>
              <p className="text-xs text-gray-500 mt-0.5 leading-relaxed">
                Appuyez sur <strong>Partager</strong> puis <strong>"Sur l'écran d'accueil"</strong> pour installer l'app.
              </p>
            </div>
          </div>
          <div className="mt-3 flex items-center justify-center gap-1">
            {[0, 1, 2].map((i) => (
              <div key={i} className={`h-1.5 rounded-full bg-gray-200 ${i === 1 ? 'w-4' : 'w-1.5'}`} />
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed bottom-20 left-4 right-4 z-50 animate-in slide-in-from-bottom-4">
      <div className="bg-gradient-to-r from-[#6D28D9] to-[#5B21B6] rounded-2xl shadow-2xl p-4">
        <button onClick={dismiss} className="absolute top-3 right-3 p-1 rounded-full bg-white/10 hover:bg-white/20">
          <X size={16} className="text-white" />
        </button>
        <div className="flex items-center gap-3 pr-6">
          <div className="w-11 h-11 rounded-xl bg-white/15 flex items-center justify-center flex-shrink-0">
            <Download size={20} className="text-white" />
          </div>
          <div className="flex-1">
            <p className="font-bold text-white text-sm">Installer Zaska</p>
            <p className="text-xs text-white/75 mt-0.5">Accès rapide depuis votre écran d'accueil</p>
          </div>
        </div>
        <button
          onClick={install}
          className="w-full mt-3 py-2.5 bg-white text-[#6D28D9] rounded-xl font-bold text-sm hover:bg-white/90 transition-colors"
        >
          Installer l'application
        </button>
      </div>
    </div>
  );
}
