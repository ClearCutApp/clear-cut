import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";

type Locale = "en" | "es";
const Context = createContext({ locale: "en" as Locale, setLocale: (_: Locale) => {} });
export function LocaleProvider({ children }: { children: ReactNode }) {
  const [locale, setLocale] = useState<Locale>(() => {
    try { return localStorage.getItem("clearcut-locale") === "es" ? "es" : "en"; }
    catch { return "en"; }
  });
  useEffect(() => {
    document.documentElement.lang = locale;
    try { localStorage.setItem("clearcut-locale", locale); } catch { /* Storage is optional. */ }
  }, [locale]);
  return <Context.Provider value={{ locale, setLocale }}>{children}</Context.Provider>;
}
export function useLocale() {
  const { locale, setLocale } = useContext(Context);
  const text = useCallback((en: string, es: string) => locale === "es" ? es : en, [locale]);
  return { locale, setLocale, text };
}
export function LanguageSwitch() {
  const { locale, setLocale } = useLocale();
  return <button className="language-switch" type="button" aria-label="English / Español"
    onClick={() => setLocale(locale === "en" ? "es" : "en")}>{locale === "en" ? "ES" : "EN"}</button>;
}
