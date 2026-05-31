import { useEffect, useRef, useCallback, useState } from 'react';

declare global {
  interface Window {
    turnstile?: {
      render: (
        element: string | HTMLElement,
        options: {
          sitekey: string;
          callback?: (token: string) => void;
          'error-callback'?: (code: string) => void;
          'expired-callback'?: () => void;
          theme?: 'light' | 'dark' | 'auto';
          language?: string;
          size?: 'normal' | 'compact';
          action?: string;
        },
      ) => string;
      remove: (widgetId: string) => void;
      reset: (widgetId: string) => void;
    };
    onTurnstileLoad?: () => void;
  }
}

const SCRIPT_ID = 'cf-turnstile-script';
const SITE_KEY = import.meta.env['VITE_TURNSTILE_SITE_KEY'] as string | undefined;

interface TurnstileWidgetProps {
  onVerify: (token: string) => void;
  onError?: (code?: string) => void;
  onExpire?: () => void;
  theme?: 'light' | 'dark' | 'auto';
  language?: string;
  action?: string;
  className?: string;
}

export function TurnstileWidget({
  onVerify,
  onError,
  onExpire,
  theme = 'auto',
  language = 'fr',
  action,
  className,
}: TurnstileWidgetProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const widgetIdRef = useRef<string | null>(null);
  const [loaded, setLoaded] = useState(false);

  const renderWidget = useCallback(() => {
    if (!containerRef.current || !window.turnstile || !SITE_KEY) return;

    // Remove previous widget if re-rendering
    if (widgetIdRef.current !== null) {
      try { window.turnstile.remove(widgetIdRef.current); } catch { /* ignore */ }
    }

    widgetIdRef.current = window.turnstile.render(containerRef.current, {
      sitekey: SITE_KEY,
      callback: onVerify,
      'error-callback': (code) => {
        console.warn('[Turnstile] error:', code);
        onError?.(code);
      },
      'expired-callback': () => {
        onExpire?.();
      },
      theme,
      language,
      size: 'normal',
      action,
    });
  }, [onVerify, onError, onExpire, theme, language, action]);

  useEffect(() => {
    // No site key = dev mode bypass: call onVerify with a placeholder token
    if (!SITE_KEY) {
      console.warn('[Turnstile] VITE_TURNSTILE_SITE_KEY not set — bypassing in dev mode');
      onVerify('dev-bypass-token');
      return;
    }

    if (window.turnstile) {
      setLoaded(true);
      return;
    }

    if (document.getElementById(SCRIPT_ID)) {
      // Script tag exists but not loaded yet — wait for callback
      window.onTurnstileLoad = () => setLoaded(true);
      return;
    }

    // Inject Cloudflare Turnstile script once
    window.onTurnstileLoad = () => setLoaded(true);
    const script = document.createElement('script');
    script.id = SCRIPT_ID;
    script.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js?onload=onTurnstileLoad&render=explicit';
    script.async = true;
    script.defer = true;
    document.head.appendChild(script);

    return () => {
      window.onTurnstileLoad = undefined;
    };
  }, [onVerify]);

  useEffect(() => {
    if (loaded) renderWidget();
  }, [loaded, renderWidget]);

  useEffect(() => {
    return () => {
      if (widgetIdRef.current !== null && window.turnstile) {
        try { window.turnstile.remove(widgetIdRef.current); } catch { /* ignore */ }
      }
    };
  }, []);

  if (!SITE_KEY) return null;

  return <div ref={containerRef} className={className} />;
}

/** Hook that integrates Turnstile into a form.
 *  Usage:
 *    const { token, TurnstileWidget } = useTurnstile();
 *    // Include TurnstileWidget in your form JSX
 *    // Pass token in the form body as `cf-turnstile-response`
 */
export function useTurnstile(action?: string) {
  const [token, setToken] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleVerify = useCallback((t: string) => {
    setToken(t);
    setError(null);
  }, []);

  const handleError = useCallback((code?: string) => {
    setToken(null);
    setError(code ?? 'turnstile_error');
  }, []);

  const handleExpire = useCallback(() => {
    setToken(null);
  }, []);

  const Widget = (
    <TurnstileWidget
      onVerify={handleVerify}
      onError={handleError}
      onExpire={handleExpire}
      action={action}
    />
  );

  return { token, error, isVerified: !!token, TurnstileWidget: Widget };
}
