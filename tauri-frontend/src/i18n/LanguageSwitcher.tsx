import React, { useState, useRef, useEffect } from 'react';
import { Globe, ChevronDown } from 'lucide-react';
import { useLanguage } from './LanguageContext';
import { Language } from './translations';

interface LanguageOption {
  code: Language;
  label: string;
}

const LANGUAGE_OPTIONS: LanguageOption[] = [
  { code: 'es', label: 'Español' },
  { code: 'zh', label: '简体中文' },
  { code: 'en', label: 'English' },
];

export const LanguageSwitcher: React.FC = () => {
  const { lang, setLang } = useLanguage();
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const currentOption = LANGUAGE_OPTIONS.find((opt) => opt.code === lang) || LANGUAGE_OPTIONS[0];

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  const handleSelect = (code: Language) => {
    setLang(code);
    setIsOpen(false);
  };

  return (
    <div className="relative inline-block text-left" ref={dropdownRef}>
      <button
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        className="h-8 px-2.5 rounded-md bg-slate-900 border border-slate-700 hover:border-slate-600 text-slate-200 text-xs font-medium flex items-center gap-1.5 focus:outline-none focus:ring-1 focus:ring-cyan-400 cursor-pointer transition-colors"
        aria-haspopup="true"
        aria-expanded={isOpen}
      >
        <Globe className="w-4 h-4 text-cyan-400 shrink-0" />
        <span>{currentOption.label}</span>
        <ChevronDown className={`w-3.5 h-3.5 text-slate-400 transition-transform duration-150 ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {isOpen && (
        <div className="absolute right-0 mt-1 w-36 rounded-md bg-slate-900 border border-slate-700 shadow-xl py-1 z-50 text-xs">
          {LANGUAGE_OPTIONS.map((option) => {
            const isSelected = option.code === lang;
            return (
              <button
                key={option.code}
                type="button"
                onClick={() => handleSelect(option.code)}
                className={`w-full text-left px-3 py-1.5 flex items-center justify-between transition-colors ${
                  isSelected
                    ? 'bg-slate-800 text-cyan-400 font-semibold'
                    : 'text-slate-200 hover:bg-slate-800 hover:text-cyan-400'
                }`}
              >
                <span>{option.label}</span>
                {isSelected && <span className="w-1.5 h-1.5 rounded-full bg-cyan-400" />}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default LanguageSwitcher;
