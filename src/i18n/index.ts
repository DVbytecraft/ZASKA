import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import fr from "./fr.json";
import en from "./en.json";

// ── Supported languages ────────────────────────────────────────────────────
const SUPPORTED: ReadonlySet<string> = new Set(["fr", "en"]);
const FALLBACK = "fr";

// Country code → language (for logged-in users)
const COUNTRY_LANGUAGE: Record<string, string> = {
  // Francophone West Africa + Europe
  TG: "fr", CI: "fr", SN: "fr", BJ: "fr",
  BF: "fr", ML: "fr", NE: "fr", CM: "fr",
  FR: "fr", BE: "fr",
  // Anglophone Africa + North America
  GH: "en", NG: "en", KE: "en", US: "en",
};

const LANGUAGE_STORAGE_KEY = "zaska_language";

// ── Helpers ────────────────────────────────────────────────────────────────

export function getLangForCountry(countryCode: string | null | undefined): string {
  if (!countryCode) return FALLBACK;
  return COUNTRY_LANGUAGE[countryCode.toUpperCase()] ?? FALLBACK;
}

/**
 * Read the browser's preferred language (navigator.language / navigator.languages)
 * and map it to a supported language code.
 * Returns the fallback if the browser locale cannot be resolved.
 */
function getBrowserLang(): string {
  try {
    const candidates =
      typeof navigator !== "undefined"
        ? [navigator.language, ...(navigator.languages ?? [])]
        : [];

    for (const tag of candidates) {
      if (!tag) continue;
      // Primary subtag only: "fr-FR" → "fr", "en-GB" → "en"
      const primary = tag.split("-")[0].toLowerCase();
      if (SUPPORTED.has(primary)) return primary;
    }
  } catch {
    // navigator unavailable in test / SSR environments
  }
  return FALLBACK;
}

/**
 * Determine the language to use on first load (before any login):
 *   1. Manual preference saved by the user (localStorage)   — highest priority
 *   2. Browser locale (navigator.language)
 *   3. French fallback
 */
function getInitialLang(): string {
  try {
    const stored = localStorage.getItem(LANGUAGE_STORAGE_KEY);
    if (stored && SUPPORTED.has(stored)) return stored;
  } catch {
    // localStorage unavailable
  }
  return getBrowserLang();
}

// ── Public API ─────────────────────────────────────────────────────────────

/**
 * Explicit user language switch (e.g. from a settings screen).
 * Persisted to localStorage so it survives reloads and takes priority
 * over both browser locale and country-based detection.
 */
export function setUserLanguage(lang: string): void {
  const safe = SUPPORTED.has(lang) ? lang : FALLBACK;
  try {
    localStorage.setItem(LANGUAGE_STORAGE_KEY, safe);
  } catch {
    // localStorage unavailable — still applies for this session
  }
  void i18n.changeLanguage(safe);
}

/**
 * Called after login/OTP to align the language with the user's registered country.
 *
 * Priority:
 *   1. Manual preference (localStorage)  — user chose explicitly, respect it
 *   2. country_code from the account     — authoritative once logged in
 *   3. French fallback
 */
export function setAppLanguage(countryCode: string | null | undefined): void {
  let lang: string;
  try {
    const stored = localStorage.getItem(LANGUAGE_STORAGE_KEY);
    lang = stored && SUPPORTED.has(stored) ? stored : getLangForCountry(countryCode);
  } catch {
    lang = getLangForCountry(countryCode);
  }
  if (i18n.language !== lang) {
    void i18n.changeLanguage(lang);
  }
}

// ── Initialisation ─────────────────────────────────────────────────────────

i18n
  .use(initReactI18next)
  .init({
    resources: {
      fr: { translation: fr },
      en: { translation: en },
    },
    lng: getInitialLang(),   // browser locale (or manual pref) before any login
    fallbackLng: FALLBACK,
    interpolation: {
      escapeValue: false,    // React already escapes
    },
    react: { useSuspense: false },
  });

export default i18n;
