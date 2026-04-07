import { AlertTriangle, RefreshCcw } from "lucide-react";
import React from "react";

import { captureUIError } from "../observability/client";

type ErrorBoundaryState = {
  hasError: boolean;
  message: string;
};

type ErrorBoundaryProps = React.PropsWithChildren<{
  moduleName?: string;
}>;

export class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, message: "" };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, message: error.message };
  }

  componentDidCatch(error: Error) {
    console.error("UI crashed", error);
    captureUIError(error, { module: this.props.moduleName || "global" });
  }

  render() {
    if (!this.state.hasError) {
      return this.props.children;
    }

    return (
      <div className="flex min-h-[70vh] items-center justify-center p-6">
        <div className="card max-w-lg space-y-4 p-6 text-center">
          <AlertTriangle className="mx-auto h-10 w-10 text-[rgb(var(--danger))]" />
          <h2 className="text-2xl font-semibold">Something went wrong</h2>
          <p className="text-sm text-[rgb(var(--text-dim))]">{this.state.message || "Unexpected dashboard error."}</p>
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="mx-auto inline-flex items-center gap-2 rounded-xl bg-[rgb(var(--primary))] px-4 py-2 text-sm font-semibold text-white"
          >
            <RefreshCcw className="h-4 w-4" /> Retry
          </button>
        </div>
      </div>
    );
  }
}
