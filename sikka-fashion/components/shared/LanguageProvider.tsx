"use client";

import { createContext, useContext, useState, useCallback, useEffect, ReactNode } from "react";
import { translations, Language, TranslationKey } from "@/utils/translations";

interface LanguageContextType {
  language: Language;
  toggleLanguage: () => void;
  t: (key: TranslationKey) => string;
  isRTL: boolean;
}

const LanguageContext = createContext<LanguageContextType | undefined>(undefined);

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [language, setLanguage] = useState<Language>("ar");
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const saved = localStorage.getItem("khizana-lang") as Language | null;
    if (saved === "ar" || saved === "en") {
      setLanguage(saved);
    }
    setMounted(true);
  }, []);

  const toggleLanguage = useCallback(() => {
    setLanguage((prev) => {
      const next = prev === "ar" ? "en" : "ar";
      localStorage.setItem("khizana-lang", next);
      return next;
    });
  }, []);

  const t = useCallback(
    (key: TranslationKey) => {
      return translations[language][key] || key;
    },
    [language]
  );

  const isRTL = language === "ar";

  if (!mounted) {
    return (
      <LanguageContext.Provider value={{ language: "ar", toggleLanguage, t, isRTL: true }}>
        <div dir="rtl" lang="ar">
          {children}
        </div>
      </LanguageContext.Provider>
    );
  }

  return (
    <LanguageContext.Provider value={{ language, toggleLanguage, t, isRTL }}>
      <div dir={isRTL ? "rtl" : "ltr"} lang={language}>
        {children}
      </div>
    </LanguageContext.Provider>
  );
}

export function useLanguage() {
  const context = useContext(LanguageContext);
  if (!context) {
    throw new Error("useLanguage must be used within a LanguageProvider");
  }
  return context;
}
