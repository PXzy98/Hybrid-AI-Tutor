import { Component, type ErrorInfo, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { useI18n } from "@/i18n";

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
    <div role="alert" className="mx-auto max-w-lg space-y-3 rounded-xl border bg-card p-6">
      <h1 className="text-lg font-semibold">{t("error.title")}</h1>
      <p className="text-sm text-muted-foreground">{t("error.body")}</p>
      <Button type="button" onClick={() => window.location.reload()}>{t("error.reload")}</Button>
    </div>
  );
}
