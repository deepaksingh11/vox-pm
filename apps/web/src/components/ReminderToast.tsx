import { useEffect } from "react";
import { Bell, X } from "lucide-react";
import { useStore } from "../hooks/useStore";

// Auto-dismiss the reminder toast after this long; the entry also persists in the action feed.
const AUTO_DISMISS_MS = 10_000;

export function ReminderToast() {
  const reminderNotice = useStore((s) => s.reminderNotice);
  const clearReminderNotice = useStore((s) => s.clearReminderNotice);

  useEffect(() => {
    if (!reminderNotice) return;
    const id = setTimeout(clearReminderNotice, AUTO_DISMISS_MS);
    return () => clearTimeout(id);
  }, [reminderNotice, clearReminderNotice]);

  if (!reminderNotice) return null;

  return (
    <div
      className="bg-amber-500/15 border border-amber-500/40 rounded-xl px-4 py-3 flex items-start gap-3"
      style={{ animation: "fade-in 0.2s ease-out" }}
      role="alert"
      aria-live="assertive"
    >
      <Bell size={16} className="text-amber-500 shrink-0 mt-0.5" />
      <div className="flex-1 min-w-0">
        <p className="text-[11px] font-semibold uppercase tracking-wide text-amber-600 dark:text-amber-400">
          Reminder
        </p>
        <p className="text-sm font-medium text-foreground truncate">{reminderNotice.task.title}</p>
      </div>
      <button
        onClick={clearReminderNotice}
        aria-label="Dismiss reminder"
        className="text-muted-foreground hover:text-foreground transition-colors"
      >
        <X size={14} />
      </button>
    </div>
  );
}
