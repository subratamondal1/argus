import { Brain, Layers, Loader2, RefreshCw, Search, Wrench } from "lucide-react";
import type { ComponentType } from "react";

import type { AgentEvent } from "../types";

interface Step {
  icon: ComponentType<{ className?: string }>;
  text: string;
}

function describe(event: AgentEvent): Step | null {
  switch (event.type) {
    case "plan":
      return {
        icon: Brain,
        text: `Planning — ${(event.sub_questions ?? []).length} sub-questions`,
      };
    case "search_start":
      return { icon: Search, text: `Researching — ${event.sub_question ?? ""}` };
    case "tool":
      return {
        icon: Wrench,
        text: `${event.name ?? "tool"}${event.query ? ` — ${event.query}` : ""}`,
      };
    case "synthesize":
      return { icon: Layers, text: `Synthesizing ${event.findings ?? 0} findings` };
    case "reflect":
      return {
        icon: RefreshCw,
        text: event.complete
          ? "Reflection — complete"
          : `Reflection — following up on ${(event.missing ?? []).length}`,
      };
    default:
      return null;
  }
}

export function Steps({ events, streaming }: { events: AgentEvent[]; streaming: boolean }) {
  const steps = events.map(describe).filter((step): step is Step => step !== null);
  if (steps.length === 0) return null;

  return (
    <div className="mb-6 rounded-2xl border border-zinc-200 bg-zinc-50/70 p-4 dark:border-zinc-800 dark:bg-zinc-900/40">
      <div className="mb-3 text-[11px] font-semibold uppercase tracking-wider text-zinc-400">
        Steps
      </div>
      <ol className="space-y-2.5">
        {steps.map((step, index) => {
          const active = streaming && index === steps.length - 1;
          const Icon = step.icon;
          return (
            <li key={index} className="flex items-center gap-2.5 text-sm">
              {active ? (
                <Loader2 className="h-4 w-4 shrink-0 animate-spin text-indigo-500" />
              ) : (
                <Icon className="h-4 w-4 shrink-0 text-zinc-400" />
              )}
              <span
                className={
                  active
                    ? "truncate text-zinc-900 dark:text-zinc-100"
                    : "truncate text-zinc-500 dark:text-zinc-400"
                }
              >
                {step.text}
              </span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
