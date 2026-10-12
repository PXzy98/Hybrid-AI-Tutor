import { Component, type ErrorInfo, type ReactNode } from "react";

type State = { failed: boolean };

/** Shows a message instead of a blank page when a page crashes. */
export default class ErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { failed: false };

  static getDerivedStateFromError(): State {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("page crashed", error, info.componentStack);
  }

  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <div role="alert" className="card mx-auto max-w-lg space-y-3">
        <h1 className="text-lg font-semibold">Something went wrong on this page.</h1>
        <p className="text-sm text-slate-700">Please reload the page. If it happens again, tell your instructor.</p>
        <button type="button" className="btn-primary" onClick={() => window.location.reload()}>Reload</button>
      </div>
    );
  }
}
