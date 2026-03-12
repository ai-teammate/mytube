"use client";

import React, {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  useCallback,
  ReactNode,
} from "react";

export type Theme = "light" | "dark";

export interface ThemeContextValue {
  /** The currently active theme. */
  theme: Theme;
  /** Toggles between light and dark, persists choice to localStorage. */
  toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

const STORAGE_KEY = "theme";
const DEFAULT_THEME: Theme = "light";

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(DEFAULT_THEME);
  const isFirstRender = useRef(true);

  /**
   * On mount (client-only): read the persisted preference from localStorage,
   * apply it to the DOM immediately, and sync React state.
   *
   * We also set `data-theme` here directly so the FOUC-prevention inline
   * script's value is never overwritten by the `[theme]` effect before the
   * state update has taken effect.
   */
  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY) as Theme | null;
    const initial: Theme = stored === "dark" ? "dark" : "light";
    document.body.setAttribute("data-theme", initial);
    setTheme(initial);
  }, []);

  /**
   * Apply data-theme and persist on subsequent theme changes (e.g. toggleTheme).
   * Skipped on the initial render because the mount effect above already
   * handles the first DOM update — running it on the first render with the
   * default "light" value would overwrite the FOUC-prevention script's "dark"
   * setting before the mount effect's setTheme("dark") re-render takes effect.
   */
  useEffect(() => {
    if (isFirstRender.current) {
      isFirstRender.current = false;
      return; // initial value is handled by the mount effect above
    }
    document.body.setAttribute("data-theme", theme);
    localStorage.setItem(STORAGE_KEY, theme);
  }, [theme]);

  const toggleTheme = useCallback(() => {
    setTheme((prev) => (prev === "light" ? "dark" : "light"));
  }, []);

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

/**
 * Returns the ThemeContext value.
 * Must be called inside a <ThemeProvider>.
 */
export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) {
    throw new Error("useTheme must be used within a ThemeProvider");
  }
  return ctx;
}
