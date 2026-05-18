import { useEffect } from "react";
import { Zap } from "lucide-react";
import { usePipecatSession } from "./hooks/usePipecatSession";
import { useEventStream } from "./hooks/useEventStream";
import { useStore } from "./hooks/useStore";
import { VoiceControl } from "./components/VoiceControl";
import { LiveTranscript } from "./components/LiveTranscript";
import { ActionFeed } from "./components/ActionFeed";
import { ProjectList } from "./components/ProjectList";
import { ClarificationPrompt } from "./components/ClarificationPrompt";

export default function App() {
  const { status, sessionId, error, start, stop, toggleMic } = usePipecatSession();
  const { loadInitialState, applyEvent } = useStore();

  useEffect(() => {
    void loadInitialState();
  }, [loadInitialState]);

  useEventStream(sessionId, applyEvent);

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col">
      {/* Header */}
      <header className="border-b border-slate-800 px-6 py-4 flex items-center gap-3">
        <Zap size={20} className="text-brand-500" />
        <h1 className="text-lg font-bold text-slate-100 tracking-tight">Vox PM</h1>
        <span className="text-xs text-slate-500 ml-1">voice-first project manager</span>
      </header>

      <div className="flex-1 flex flex-col lg:flex-row gap-0 overflow-hidden">
        {/* Left: Projects */}
        <main className="flex-1 overflow-y-auto p-6 scrollbar-thin">
          <ProjectList />
        </main>

        {/* Right: Voice + Feed */}
        <aside className="w-full lg:w-80 xl:w-96 border-t lg:border-t-0 lg:border-l border-slate-800 flex flex-col gap-0 bg-slate-950">
          {/* Voice controls panel */}
          <div className="p-5 border-b border-slate-800 space-y-4">
            <VoiceControl
              status={status}
              onStart={start}
              onStop={stop}
              onToggleMic={toggleMic}
              error={error}
            />
            <LiveTranscript />
            <ClarificationPrompt />
          </div>

          {/* Action feed */}
          <div className="flex-1 overflow-hidden p-4">
            <ActionFeed />
          </div>
        </aside>
      </div>
    </div>
  );
}
