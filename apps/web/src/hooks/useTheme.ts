import { useState, useEffect, useCallback } from "react";

export type ThemeMode = "light" | "dark" | "system";

function resolveMode(mode: ThemeMode): "light" | "dark" {
  if (mode === "system") {
    return matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  return mode;
}

function applyResolved(resolved: "light" | "dark") {
  document.documentElement.classList.toggle("dark", resolved === "dark");
}

export function useTheme() {
  const [theme, setThemeState] = useState<ThemeMode>(() => {
    return (localStorage.getItem("vox-pm-theme") as ThemeMode) ?? "system";
  });

  const setTheme = useCallback((next: ThemeMode) => {
    localStorage.setItem("vox-pm-theme", next);
    setThemeState(next);
  }, []);

  useEffect(() => {
    applyResolved(resolveMode(theme));

    if (theme !== "system") return;

    const mq = matchMedia("(prefers-color-scheme: dark)");
    const onChange = (e: MediaQueryListEvent) => {
      applyResolved(e.matches ? "dark" : "light");
    };
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, [theme]);

  return { theme, setTheme };
}
