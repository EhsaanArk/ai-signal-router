import { Component, type ErrorInfo, type ReactNode } from "react";
import * as Sentry from "@sentry/react";
import { AlertTriangle, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { isChunkLoadError, getChunkReloadKey } from "@/lib/lazy-retry";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  isChunkError: boolean;
  resetKey: number;
}

export class ErrorBoundary extends Component<Props, State> {
  private reloadTimer: ReturnType<typeof setTimeout> | null = null;

  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, isChunkError: false, resetKey: 0 };
  }

  static getDerivedStateFromError(error: Error): Partial<State> {
    return {
      hasError: true,
      isChunkError: isChunkLoadError(error),
    };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("ErrorBoundary caught:", error, errorInfo);

    if (isChunkLoadError(error)) {
      Sentry.captureException(error, {
        tags: { type: "chunk_load_error" },
        contexts: { react: { componentStack: errorInfo.componentStack ?? "" } },
      });

      // Auto-reload after 1.5s (with sessionStorage guard to prevent loops)
      const key = getChunkReloadKey();
      if (!sessionStorage.getItem(key)) {
        sessionStorage.setItem(key, "1");
        this.reloadTimer = setTimeout(() => window.location.reload(), 1500);
      }
    } else {
      Sentry.captureException(error, {
        contexts: { react: { componentStack: errorInfo.componentStack ?? "" } },
      });
    }
  }

  componentWillUnmount() {
    if (this.reloadTimer) clearTimeout(this.reloadTimer);
  }

  render() {
    if (this.state.hasError) {
      // Chunk load error: show updating UI
      if (this.state.isChunkError) {
        return (
          <div className="flex min-h-screen flex-col items-center justify-center gap-4 p-4">
            <Loader2 className="h-8 w-8 animate-spin text-primary" />
            <p className="text-sm text-muted-foreground">
              Updating to latest version...
            </p>
          </div>
        );
      }

      // Generic error UI
      return (
        <div className="flex min-h-screen flex-col items-center justify-center gap-4 p-4">
          <AlertTriangle className="h-12 w-12 text-destructive" />
          <h2 className="text-xl font-semibold">Something went wrong</h2>
          <p className="text-sm text-muted-foreground">
            An unexpected error occurred.
          </p>
          <Button
            onClick={() =>
              this.setState((prev) => ({
                hasError: false,
                isChunkError: false,
                resetKey: prev.resetKey + 1,
              }))
            }
          >
            Try again
          </Button>
        </div>
      );
    }

    return <div key={this.state.resetKey}>{this.props.children}</div>;
  }
}
