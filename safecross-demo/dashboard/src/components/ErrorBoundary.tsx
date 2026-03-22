import { Component, type ReactNode, type ErrorInfo } from "react";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Component error:", error, info);
  }

  render() {
    if (this.state.hasError) {
      return (
        this.props.fallback ?? (
          <div
            style={{
              background: "#1E293B",
              borderRadius: 12,
              padding: 16,
              color: "#EF4444",
              fontSize: 13,
              textAlign: "center",
            }}
          >
            Something went wrong. Refresh to retry.
          </div>
        )
      );
    }
    return this.props.children;
  }
}
