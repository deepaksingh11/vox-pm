import { useEffect } from "react";
import { Zap } from "lucide-react";
import { usePipecatSession } from "./hooks/usePipecatSession";
import { useEventStream } from "./hooks/useEventStream";
import { useStore } from "./hooks/useStore";
import { useTheme } from "./hooks/useTheme";
import { VoiceControl } from "./components/VoiceControl";
import { LiveTranscript } from "./components/LiveTranscript";
import { ActionFeed } from "./components/ActionFeed";
import { DebugPanel } from "./components/DebugPanel";
import { ProjectList } from "./components/ProjectList";
import { ClarificationPrompt } from "./components/ClarificationPrompt";
import { ThemeToggle } from "./components/ThemeToggle";

export default function App() {
  const { status, sessionId, error, muted, start, stop, toggleMic } = usePipecatSession();
  const { loadInitialState, applyEvent } = useStore();
  const { theme, setTheme } = useTheme();

  useEffect(() => {
    void loadInitialState();
  }, [loadInitialState]);

  useEventStream(sessionId, applyEvent);

  return (
    <div className="min-h-screen bg-background flex flex-col">
      <header className="sticky top-0 z-10 backdrop-blur-md bg-background/80 border-b border-border px-6 py-3 flex items-center gap-3">
        <div className="flex items-center gap-2.5 flex-1">
          <div className="w-7 h-7 rounded-lg bg-primary flex items-center justify-center shadow-sm">
            <Zap size={14} className="text-primary-foreground" />
          </div>
          <h1 className="text-base font-bold text-foreground tracking-tight">Vox PM</h1>
          <span className="text-xs text-muted-foreground hidden sm:block">voice-first project manager</span>
        </div>
        <ThemeToggle theme={theme} onSetTheme={setTheme} />
      </header>

      <div className="flex-1 flex flex-col lg:flex-row overflow-hidden">
        <main className="flex-1 overflow-y-auto p-6 scrollbar-thin">
          <ProjectList />
        </main>

        <aside className="w-full lg:w-80 xl:w-96 border-t lg:border-t-0 lg:border-l border-border flex flex-col bg-card">
          <div className="p-5 border-b border-border space-y-3">
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
  );
}
