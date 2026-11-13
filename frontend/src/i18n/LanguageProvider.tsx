import { useEffect, useMemo, useState, type ReactNode } from "react";
import { LanguageContext } from "./languageContext";
import { LANGUAGE_STORAGE_KEY, readLanguage, translate, type Language } from "./language";

export function LanguageProvider({ children, initialLanguage }: { children: ReactNode; initialLanguage?: Language }) {
  const [language, setLanguage] = useState<Language>(initialLanguage ?? readLanguage);
  useEffect(() => {
    document.documentElement.lang = language;
    document.title = translate("HOSA · Moon Explorer", language);
    try {
      window.localStorage.setItem(LANGUAGE_STORAGE_KEY, language);
    } catch {
      // Language switching still works when browser storage is unavailable.
    }
  }, [language]);
  const context = useMemo(() => ({ language, setLanguage }), [language]);
  return <LanguageContext.Provider value={context}>{children}</LanguageContext.Provider>;
}
