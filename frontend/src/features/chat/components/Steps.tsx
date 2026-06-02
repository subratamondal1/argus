"use client";

import {
  Brain,
  Check,
  ChevronDown,
  Layers,
  Loader2,
  RefreshCw,
  Search,
  Wrench,
} from "lucide-react";
import { type ComponentType, useState } from "react";

import { cn } from "@/shared/lib/cn";

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
  const [open, setOpen] = useState(false);
  const steps = events.map(describe).filter((step): step is Step => step !== null);
  if (steps.length === 0) return null;
  const expanded = streaming || open;

  return (
    <div className="mb-5 overflow-hidden rounded-2xl border border-zinc-200 bg-zinc-50/70 dark:border-zinc-800 dark:bg-zinc-900/40">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-center justify-between px-4 py-3 text-left"
      >
        <span className="flex items-center gap-2 text-[12px] font-medium text-zinc-500 dark:text-zinc-400">
          {streaming ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin text-indigo-500" />
          ) : (
            <Check className="h-3.5 w-3.5 text-emerald-500" />
          )}
          {streaming ? "Working…" : `${steps.length} steps`}
        </span>
        <ChevronDown
          className={cn("h-4 w-4 text-zinc-400 transition", expanded && "rotate-180")}
        />
      </button>
      {expanded && (
        <ol className="space-y-2.5 px-4 pb-4">
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
                  className={cn(
                    "truncate",
                    active
                      ? "text-zinc-900 dark:text-zinc-100"
                      : "text-zinc-500 dark:text-zinc-400",
                  )}
                >
                  {step.text}
                </span>
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}
