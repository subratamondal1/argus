"use client";

import { Component, type ReactNode } from "react";

import { logger } from "@/shared/lib/logger";

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error): void {
    logger.error("react error boundary", error);
  }

  render(): ReactNode {
    if (this.state.error !== null) {
      return (
        <div className="m-8 rounded-lg border border-red-300 bg-red-50 p-6 text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">
          <h2 className="font-semibold">Something went wrong</h2>
          <p className="mt-1 text-sm">{this.state.error.message}</p>
          <button
            type="button"
            onClick={() => this.setState({ error: null })}
            className="mt-3 rounded-md border border-red-300 px-3 py-1 text-sm dark:border-red-800"
          >
            Try again
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
