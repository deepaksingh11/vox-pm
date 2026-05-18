import { Sun, Moon, Monitor } from "lucide-react";
import type { ThemeMode } from "../hooks/useTheme";

interface Props {
  theme: ThemeMode;
  onSetTheme: (t: ThemeMode) => void;
}

const cycle: ThemeMode[] = ["light", "system", "dark"];
const icons: Record<ThemeMode, typeof Sun> = { light: Sun, system: Monitor, dark: Moon };
const labels: Record<ThemeMode, string> = { light: "Light", system: "System", dark: "Dark" };

export function ThemeToggle({ theme, onSetTheme }: Props) {
  const Icon = icons[theme];
  const next = cycle[(cycle.indexOf(theme) + 1) % cycle.length];

  return (
    <button
      onClick={() => onSetTheme(next)}
      title={`${labels[theme]} — click to switch`}
      className="flex items-center justify-center w-8 h-8 rounded-md text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
    >
      <Icon size={15} />
    </button>
  );
}
