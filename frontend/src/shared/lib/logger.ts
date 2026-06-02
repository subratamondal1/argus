// Minimal structured frontend logger with a bounded breadcrumb trail. Logging
// must never crash the app, so every path is guarded. A backend log sink can be
// added later by POSTing entries to the API.

type Level = "info" | "warn" | "error";

interface Breadcrumb {
  action: string;
  at: string;
}

class Logger {
  private breadcrumbs: Breadcrumb[] = [];
  readonly correlationId: string =
    typeof crypto !== "undefined" ? crypto.randomUUID() : "no-crypto";

  breadcrumb(action: string): void {
    this.breadcrumbs.push({ action, at: new Date().toISOString() });
    if (this.breadcrumbs.length > 20) this.breadcrumbs.shift();
  }

  log(level: Level, message: string, meta?: Record<string, unknown>): void {
    const entry = {
      level,
      message,
      correlationId: this.correlationId,
      breadcrumbs: [...this.breadcrumbs],
      ...meta,
    };
    try {
      console[level === "info" ? "log" : level](JSON.stringify(entry));
    } catch {
      // never throw from logging
    }
  }

  error(message: string, error?: unknown): void {
    this.log("error", message, {
      error: error instanceof Error ? error.message : String(error),
    });
  }
}

export const logger = new Logger();
