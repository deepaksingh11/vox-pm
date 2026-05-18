import { Component, type ReactNode } from "react";

interface Props { children: ReactNode; }
interface State { error: Error | null; }

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;

    return (
      <div className="h-screen flex items-center justify-center bg-background">
        <div className="text-center px-6 max-w-md">
          <div className="mx-auto mb-4 w-12 h-12 rounded-full bg-destructive/10 flex items-center justify-center">
            <span className="text-destructive text-xl font-bold">!</span>
          </div>
          <p className="text-sm font-semibold text-foreground mb-1">Something went wrong</p>
          <p className="text-xs text-muted-foreground mb-4 font-mono truncate">{error.message}</p>
          <button
            onClick={() => window.location.reload()}
            className="px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors"
          >
            Reload app
          </button>
        </div>
      </div>
    );
  }
}
