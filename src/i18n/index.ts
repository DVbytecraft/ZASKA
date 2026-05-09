import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import fr from "./fr.json";
import en from "./en.json";

// Country code → ISO 639-1 language code mapping
const COUNTRY_LANGUAGE: Record<string, string> = {
  // Francophone West Africa + Europe
  TG: "fr", CI: "fr", SN: "fr", BJ: "fr",
  BF: "fr", ML: "fr", NE: "fr", CM: "fr",
  FR: "fr", BE: "fr",
  // Anglophone Africa + North America
  GH: "en", NG: "en", KE: "en", US: "en",
};

export function getLangForCountry(countryCode: string | null | undefined): string {
  if (!countryCode) return "fr";
  return COUNTRY_LANGUAGE[countryCode.toUpperCase()] ?? "fr";
}

/** Call after login to switch language based on user's country. */
export function setAppLanguage(countryCode: string | null | undefined): void {
  const lang = getLangForCountry(countryCode);
  if (i18n.language !== lang) {
    void i18n.changeLanguage(lang);
  }
}

i18n
  .use(initReactI18next)
  .init({
    resources: {
      fr: { translation: fr },
      en: { translation: en },
    },
    lng: "fr",            // default — overridden after login via setAppLanguage()
    fallbackLng: "fr",
    interpolation: {
      escapeValue: false, // React already escapes
    },
    // No suspense mode — translations are bundled, not async
    react: { useSuspense: false },
  });

export default i18n;
