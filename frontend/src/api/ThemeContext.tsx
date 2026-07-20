import { createContext, useContext, useState, useEffect, type ReactNode } from "react";

type ThemeMode = "light" | "dark" | "system";

interface ThemeContextType {
  mode: ThemeMode;
  isDark: boolean;
  setMode: (m: ThemeMode) => void;
}

const ThemeContext = createContext<ThemeContextType>({
  mode: "system",
  isDark: false,
  setMode: () => {},
});

function getSystemDark(): boolean {
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [mode, setModeState] = useState<ThemeMode>(() => {
    return (localStorage.getItem("zhigu_theme") as ThemeMode) || "system";
  });

  const [isDark, setIsDark] = useState(() => {
    const saved = localStorage.getItem("zhigu_theme") as ThemeMode;
    return saved === "dark" || (!saved && getSystemDark()) || (saved === "system" && getSystemDark());
  });

  const setMode = (m: ThemeMode) => {
    setModeState(m);
    localStorage.setItem("zhigu_theme", m);
    setIsDark(m === "dark" || (m === "system" && getSystemDark()));
  };

  useEffect(() => {
    if (mode === "system") {
      const mq = window.matchMedia("(prefers-color-scheme: dark)");
      const handler = (e: MediaQueryListEvent) => setIsDark(e.matches);
      mq.addEventListener("change", handler);
      return () => mq.removeEventListener("change", handler);
    }
  }, [mode]);

  // Sync data-theme attribute on body for CSS variable overrides
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", isDark ? "dark" : "light");
  }, [isDark]);

  return (
    <ThemeContext.Provider value={{ mode, isDark, setMode }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  return useContext(ThemeContext);
}
