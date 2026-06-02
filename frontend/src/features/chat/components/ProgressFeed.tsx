import { Brain, Layers, RefreshCw, Search, Wrench } from "lucide-react";
import type { ComponentType } from "react";

import type { AgentEvent } from "../types";

interface Row {
  icon: ComponentType<{ className?: string }>;
  text: string;
}

function describe(event: AgentEvent): Row | null {
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

export function ProgressFeed({ events }: { events: AgentEvent[] }) {
  const rows = events.map(describe).filter((row): row is Row => row !== null);
  if (rows.length === 0) return null;

  return (
    <ul className="space-y-1.5 rounded-xl border border-black/10 bg-black/[0.02] p-3 text-sm dark:border-white/10 dark:bg-white/[0.03]">
      {rows.map(({ icon: Icon, text }, index) => (
        <li
          key={index}
          className="flex items-center gap-2 text-black/70 dark:text-white/70"
        >
          <Icon className="h-3.5 w-3.5 shrink-0 text-black/40 dark:text-white/40" />
          <span className="truncate">{text}</span>
        </li>
      ))}
    </ul>
  );
}
