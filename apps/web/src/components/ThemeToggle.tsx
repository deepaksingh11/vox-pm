import { Sun, Moon, Monitor } from "lucide-react";
import type { ThemeMode } from "../hooks/useTheme";
import { cn } from "../lib/utils";

interface Props {
  theme: ThemeMode;
  onSetTheme: (t: ThemeMode) => void;
}

const options: { mode: ThemeMode; Icon: typeof Sun; label: string }[] = [
  { mode: "light",  Icon: Sun,     label: "Light"  },
  { mode: "system", Icon: Monitor, label: "System" },
  { mode: "dark",   Icon: Moon,    label: "Dark"   },
];

export function ThemeToggle({ theme, onSetTheme }: Props) {
  return (
    <div className="flex items-center gap-0.5 rounded-lg bg-muted p-0.5">
      {options.map(({ mode, Icon, label }) => (
        <button
          key={mode}
          onClick={() => onSetTheme(mode)}
          title={label}
          className={cn(
            "flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs font-medium transition-all",
            theme === mode
              ? "bg-background text-foreground shadow-sm"
              : "text-muted-foreground hover:text-foreground"
          )}
        >
          <Icon size={13} />
          <span className="hidden sm:inline">{label}</span>
        </button>
      ))}
    </div>
  );
}
