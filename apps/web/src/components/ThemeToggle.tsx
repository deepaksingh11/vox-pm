import { Sun, Moon, Monitor, Check } from "lucide-react";
import type { ThemeMode } from "../hooks/useTheme";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

interface Props {
  theme: ThemeMode;
  onSetTheme: (t: ThemeMode) => void;
}

const MODES: { mode: ThemeMode; label: string; icon: typeof Sun }[] = [
  { mode: "light", label: "Light", icon: Sun },
  { mode: "dark", label: "Dark", icon: Moon },
  { mode: "system", label: "System", icon: Monitor },
];

const icons: Record<ThemeMode, typeof Sun> = { light: Sun, system: Monitor, dark: Moon };

export function ThemeToggle({ theme, onSetTheme }: Props) {
  const Icon = icons[theme];

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          aria-label="Change theme"
          className="flex items-center justify-center w-8 h-8 rounded-md text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
        >
          <Icon size={15} />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-36">
        {MODES.map(({ mode, label, icon: ItemIcon }) => (
          <DropdownMenuItem key={mode} onClick={() => onSetTheme(mode)}>
            <ItemIcon size={14} className="text-muted-foreground" />
            {label}
            {theme === mode && <Check size={14} className="ml-auto text-primary" />}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
