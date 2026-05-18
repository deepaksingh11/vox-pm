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
import { DebugPanel } from "./components/DebugPanel";
import { ThemeToggle } from "./components/ThemeToggle";
import { TooltipProvider } from "@/components/ui/tooltip";
import imgUrl from "/vox.svg";

export default function App() {
  const { status, sessionId, error, muted, start, stop, toggleMic } = usePipecatSession();
  const { loadInitialState, applyEvent } = useStore();
  const { theme, setTheme } = useTheme();

  useEffect(() => {
    void loadInitialState();
  }, [loadInitialState]);

  useEventStream(sessionId, applyEvent);

  return (
    <TooltipProvider delayDuration={300}>
      <div className="min-h-screen bg-background flex flex-col">
        <header className="sticky top-0 z-10 backdrop-blur-md bg-background/80 border-b border-border px-4 py-2.5 flex items-center gap-3">
          <div className="flex items-center gap-2.5 flex-1">
            <img src={imgUrl} alt="Vox PM" className="w-7 h-7" />
            <h1 className="text-base font-bold text-foreground tracking-tight">Vox PM</h1>
          </div>
          <ThemeToggle theme={theme} onSetTheme={setTheme} />
        </header>

        <div className="flex-1 flex overflow-hidden">
          {/* Left sidebar — project nav */}
          <aside className="hidden lg:flex flex-col w-56 xl:w-60 border-r border-border bg-card shrink-0">
            <Sidebar />
          </aside>

          {/* Main — task list for selected project */}
          <main className="flex-1 overflow-y-auto scrollbar-thin">
            <TaskPane />
          </main>

          {/* Right sidebar — voice + agent actions */}
          <aside className="hidden lg:flex flex-col w-80 xl:w-96 border-l border-border bg-card shrink-0">
            <div className="p-4 border-b border-border space-y-3">
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

            <div className="flex-1 overflow-hidden p-4">
              <ActionFeed />
            </div>
            <DebugPanel />
          </aside>
        </div>
      </div>
    </TooltipProvider>
  );
}
