import { Component, type ErrorInfo, type ReactNode } from "react";

import { useI18n } from "../i18n";

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
    return this.state.failed ? <Crashed /> : this.props.children;
  }
}

function Crashed() {
  const { t } = useI18n();
  return (
    <div role="alert" className="card mx-auto max-w-lg space-y-3">
      <h1 className="text-lg font-semibold">{t("error.title")}</h1>
      <p className="text-sm text-slate-700">{t("error.body")}</p>
      <button type="button" className="btn-primary" onClick={() => window.location.reload()}>{t("error.reload")}</button>
    </div>
  );
}
