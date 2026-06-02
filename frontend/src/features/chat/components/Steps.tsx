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

interface AgentCard {
  subQuestion: string;
  tool: string | null;
  done: boolean;
}

interface LinearStep {
  icon: ComponentType<{ className?: string }>;
  text: string;
}

interface Grouped {
  planned: number | null;
  agents: AgentCard[];
  synthFindings: number | null;
  reflection: string | null;
}

function group(events: AgentEvent[]): Grouped {
  const order: string[] = [];
  const map = new Map<string, AgentCard>();
  let planned: number | null = null;
  let synthFindings: number | null = null;
  let reflection: string | null = null;

  for (const event of events) {
    if (event.type === "plan") {
      planned = (event.sub_questions ?? []).length;
      continue;
    }
    if (event.type === "synthesize") {
      synthFindings = event.findings ?? 0;
      continue;
    }
    if (event.type === "reflect") {
      reflection = event.complete
        ? "complete"
        : `following up on ${(event.missing ?? []).length}`;
      continue;
    }
    const question = event.sub_question;
    if (question === undefined) continue;
    if (!map.has(question)) {
      map.set(question, { subQuestion: question, tool: null, done: false });
      order.push(question);
    }
    const card = map.get(question);
    if (card === undefined) continue;
    if (event.type === "tool") {
      card.tool = `${event.name ?? "tool"}${event.query ? ` · ${event.query}` : ""}`;
    }
    if (event.type === "search_done") card.done = true;
  }

  return { planned, agents: order.map((question) => map.get(question)!), synthFindings, reflection };
}

function linearSteps(events: AgentEvent[]): LinearStep[] {
  const steps: LinearStep[] = [];
  for (const event of events) {
    if (event.type === "tool") {
      steps.push({
        icon: Wrench,
        text: `${event.name ?? "tool"}${event.query ? ` — ${event.query}` : ""}`,
      });
    }
  }
  return steps;
}

export function Steps({ events, streaming }: { events: AgentEvent[]; streaming: boolean }) {
  const [open, setOpen] = useState(false);
  if (events.length === 0) return null;
  const grouped = group(events);
  const isDeep = grouped.agents.length > 0 || grouped.planned !== null;
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
          {streaming
            ? "Working…"
            : isDeep
              ? `${grouped.agents.length} agents · researched`
              : "Steps"}
        </span>
        <ChevronDown className={cn("h-4 w-4 text-zinc-400 transition", expanded && "rotate-180")} />
      </button>

      {expanded &&
        (isDeep ? (
          <div className="space-y-3 px-4 pb-4">
            {grouped.planned !== null && (
              <div className="flex items-center gap-2 text-sm text-zinc-500 dark:text-zinc-400">
                <Brain className="h-4 w-4 text-zinc-400" /> Planned {grouped.planned} sub-questions,
                fanned out to parallel agents
              </div>
            )}
            <div className="grid gap-2 sm:grid-cols-2">
              {grouped.agents.map((agent, index) => {
                const active = streaming && !agent.done;
                return (
                  <div
                    key={index}
                    className="rounded-xl border border-zinc-200 bg-white/60 p-3 dark:border-zinc-800 dark:bg-zinc-900/50"
                  >
                    <div className="flex items-center gap-2">
                      {agent.done ? (
                        <Check className="h-3.5 w-3.5 text-emerald-500" />
                      ) : active ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin text-indigo-500" />
                      ) : (
                        <Search className="h-3.5 w-3.5 text-zinc-400" />
                      )}
                      <span className="text-[11px] font-semibold uppercase tracking-wide text-zinc-400">
                        Agent {index + 1}
                      </span>
                    </div>
                    <p
                      className="mt-1.5 line-clamp-2 text-sm text-zinc-700 dark:text-zinc-200"
                      title={agent.subQuestion}
                    >
                      {agent.subQuestion}
                    </p>
                    {agent.tool !== null && (
                      <p className="mt-1 truncate text-xs text-zinc-400" title={agent.tool}>
                        {agent.tool}
                      </p>
                    )}
                  </div>
                );
              })}
            </div>
            {grouped.synthFindings !== null && (
              <div className="flex items-center gap-2 text-sm text-zinc-500 dark:text-zinc-400">
                <Layers className="h-4 w-4 text-zinc-400" /> Synthesizing {grouped.synthFindings}{" "}
                findings
              </div>
            )}
            {grouped.reflection !== null && (
              <div className="flex items-center gap-2 text-sm text-zinc-500 dark:text-zinc-400">
                <RefreshCw className="h-4 w-4 text-zinc-400" /> Reflection — {grouped.reflection}
              </div>
            )}
          </div>
        ) : (
          <ol className="space-y-2.5 px-4 pb-4">
            {linearSteps(events).map((step, index) => {
              const active = streaming && index === linearSteps(events).length - 1;
              const Icon = step.icon;
              return (
                <li key={index} className="flex items-center gap-2.5 text-sm">
                  {active ? (
                    <Loader2 className="h-4 w-4 shrink-0 animate-spin text-indigo-500" />
                  ) : (
                    <Icon className="h-4 w-4 shrink-0 text-zinc-400" />
                  )}
                  <span className="truncate text-zinc-500 dark:text-zinc-400">{step.text}</span>
                </li>
              );
            })}
          </ol>
        ))}
    </div>
  );
}
