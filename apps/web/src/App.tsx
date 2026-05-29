import { useEffect } from "react";
import { usePipecatSession } from "./hooks/usePipecatSession";
import { useEventStream } from "./hooks/useEventStream";
import { useStore } from "./hooks/useStore";
import { useTheme } from "./hooks/useTheme";
import { VoiceControl } from "./components/VoiceControl";
import { LiveTranscript } from "./components/LiveTranscript";
import { ActionFeed } from "./components/ActionFeed";
import { Sidebar } from "./components/Sidebar";
import { TaskPane } from "./components/TaskPane";
import { ClarificationPrompt } from "./components/ClarificationPrompt";
import { DebugPanel, useDebugEnabled } from "./components/DebugPanel";
import { ThemeToggle } from "./components/ThemeToggle";
import { TooltipProvider, Tooltip, TooltipTrigger, TooltipContent } from "@/components/ui/tooltip";
import imgUrl from "/vox.svg";
// Import the stable client id that api.ts manages; avoids a second localStorage
// read and guarantees both WS and REST use the exact same value.
import { clientId } from "./lib/api";

export default function App() {
  const { status, error, muted, start, stop, toggleMic } = usePipecatSession();
  const applyEvent = useStore((s) => s.applyEvent);
  const loadInitialState = useStore((s) => s.loadInitialState);
  const { theme, setTheme } = useTheme();
  const { enabled: debugEnabled, toggle: toggleDebug } = useDebugEnabled();

  useEffect(() => {
    void loadInitialState();
  }, [loadInitialState]);

  useEventStream(clientId, applyEvent, loadInitialState);

  return (
    <TooltipProvider delayDuration={300}>
      <div className="h-screen bg-background flex flex-col overflow-hidden">
        <header className="sticky top-0 z-10 backdrop-blur-md bg-background/80 border-b border-border px-4 py-2.5 flex items-center gap-3">
          <div className="flex items-center gap-2.5 flex-1">
            <img src={imgUrl} alt="Vox PM" className="w-7 h-7" />
            <h1 className="text-base font-bold text-foreground tracking-tight">Vox PM</h1>
          </div>
          <Tooltip>
            <TooltipTrigger asChild>
              <button
                onClick={toggleDebug}
                aria-label={debugEnabled ? "Hide debug panel" : "Show debug panel"}
                aria-pressed={debugEnabled}
                className={`flex items-center justify-center w-8 h-8 rounded-md transition-colors text-xs font-bold ${
                  debugEnabled
                    ? "bg-primary/15 text-primary"
                    : "text-muted-foreground/40 hover:text-muted-foreground hover:bg-accent"
                }`}
              >
                D
              </button>
            </TooltipTrigger>
            <TooltipContent side="bottom">
              {debugEnabled ? "Hide debug events panel" : "Show debug events panel — raw WebSocket events"}
            </TooltipContent>
          </Tooltip>
          <ThemeToggle theme={theme} onSetTheme={setTheme} />
        </header>

        <div className="flex-1 flex overflow-hidden">
          <aside className="hidden lg:flex flex-col w-56 xl:w-60 border-r border-border bg-card shrink-0">
            <Sidebar />
          </aside>

          <main className="flex-1 overflow-y-auto scrollbar-thin">
            <TaskPane />
          </main>

          <aside className="hidden lg:flex flex-col w-80 xl:w-96 border-l border-border bg-card shrink-0 overflow-hidden">
            <div className="shrink-0 p-4 border-b border-border space-y-3">
              <VoiceControl
                status={status}
                isMuted={muted}
                onStart={start}
                onStop={stop}
                onToggleMic={toggleMic}
                error={error}
              />
              <LiveTranscript />
              <ClarificationPrompt />
            </div>

            <div className="flex-1 min-h-0 overflow-y-auto scrollbar-thin p-4">
              <ActionFeed />
            </div>

            <div className="shrink-0">
              <DebugPanel enabled={debugEnabled} />
            </div>
          </aside>
        </div>
      </div>
    </TooltipProvider>
  );
}
