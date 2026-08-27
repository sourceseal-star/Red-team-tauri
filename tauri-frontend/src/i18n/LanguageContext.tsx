import React, { createContext, useContext, useState, useEffect, ReactNode, useCallback } from 'react';
import { Language, translations, TranslationKey } from './translations';

const STORAGE_KEY = 'sourceseal_lang';
const VALID_LANGUAGES: Language[] = ['es', 'zh', 'en'];

export interface LanguageContextType {
  lang: Language;
  setLang: (lang: Language) => void;
  t: (key: string) => string;
}

const LanguageContext = createContext<LanguageContextType | undefined>(undefined);

const getInitialLanguage = (): Language => {
  if (typeof window !== 'undefined' && window.localStorage) {
    const saved = localStorage.getItem(STORAGE_KEY) as Language;
    if (saved && VALID_LANGUAGES.includes(saved)) {
      return saved;
    }
  }
  return 'es';
};

export const LanguageProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [lang, setLangState] = useState<Language>(getInitialLanguage);

  const setLang = useCallback((newLang: Language) => {
    if (VALID_LANGUAGES.includes(newLang)) {
      setLangState(newLang);
      if (typeof window !== 'undefined' && window.localStorage) {
        localStorage.setItem(STORAGE_KEY, newLang);
      }
    }
  }, []);

  const t = useCallback(
    (key: string): string => {
      const langDict = translations[lang] || translations.es;
      const value = langDict[key as TranslationKey];
      if (value !== undefined) {
        return value;
      }
      const fallbackValue = translations.es[key as TranslationKey];
      if (fallbackValue !== undefined) {
        return fallbackValue;
      }
      return key;
    },
    [lang]
  );

  return (
    <LanguageContext.Provider value={{ lang, setLang, t }}>
      {children}
    </LanguageContext.Provider>
  );
};

export const useLanguage = (): LanguageContextType => {
  const context = useContext(LanguageContext);
  if (!context) {
    throw new Error('useLanguage must be used within a LanguageProvider');
  }
  return context;
};
