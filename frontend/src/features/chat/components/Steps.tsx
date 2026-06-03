"use client";

import { AnimatePresence, motion } from "framer-motion";
import { Brain, Check, ChevronDown, Layers, Loader2, RefreshCw, Search, Wrench } from "lucide-react";
import { useState } from "react";

import { cn } from "@/shared/lib/cn";
import { editorialEase } from "@/shared/lib/motion";

import type { AgentEvent } from "../types";

interface AgentCard {
  subQuestion: string;
  tool: string | null;
  done: boolean;
}

interface Grouped {
  strategy: string | null;
  reasoning: string | null;
  planned: number | null;
  agents: AgentCard[];
  tools: string[];
  synthFindings: number | null;
  reflection: string | null;
}

function group(events: AgentEvent[]): Grouped {
  const order: string[] = [];
  const map = new Map<string, AgentCard>();
  const tools: string[] = [];
  const grouped: Grouped = {
    strategy: null,
    reasoning: null,
    planned: null,
    agents: [],
    tools,
    synthFindings: null,
    reflection: null,
  };

  for (const event of events) {
    if (event.type === "triage") {
      grouped.strategy = event.strategy ?? null;
      grouped.reasoning = event.reasoning ?? null;
    } else if (event.type === "plan") {
      grouped.planned = (event.sub_questions ?? []).length;
    } else if (event.type === "synthesize") {
      grouped.synthFindings = event.findings ?? 0;
    } else if (event.type === "reflect") {
      grouped.reflection = event.complete
        ? "complete"
        : `following up on ${(event.missing ?? []).length}`;
    } else if (event.sub_question !== undefined) {
      const question = event.sub_question;
      if (!map.has(question)) {
        map.set(question, { subQuestion: question, tool: null, done: false });
        order.push(question);
      }
      const card = map.get(question);
      if (card !== undefined) {
        if (event.type === "tool") {
          card.tool = `${event.name ?? "tool"}${event.query ? ` · ${event.query}` : ""}`;
        }
        if (event.type === "search_done") card.done = true;
      }
    } else if (event.type === "tool") {
      tools.push(`${event.name ?? "tool"}${event.query ? ` — ${event.query}` : ""}`);
    }
  }

  grouped.agents = order.map((question) => map.get(question)!);
  return grouped;
}

export function Steps({ events, streaming }: { events: AgentEvent[]; streaming: boolean }) {
  const [open, setOpen] = useState(false);
  const g = group(events);
  const isResearch = g.agents.length > 0 || g.planned !== null || g.strategy === "research";
  const hasBody = g.reasoning !== null || g.agents.length > 0 || g.tools.length > 0;
  if (g.strategy === null && !hasBody) return null;

  const summary = streaming
    ? "Working…"
    : isResearch
      ? `Deep research · ${g.agents.length} agents`
      : "Answered directly";
  const expanded = (streaming || open) && hasBody;

  return (
    <div className="mb-5 overflow-hidden rounded-md border border-foreground/15 bg-foreground/[0.02]">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-center justify-between px-4 py-3 text-left"
      >
        <span className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-widest text-foreground/55">
          {streaming ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin text-accent" />
          ) : (
            <Check className="h-3.5 w-3.5 text-accent" />
          )}
          {summary}
        </span>
        {hasBody && (
          <ChevronDown
            className={cn("h-4 w-4 text-foreground/40 transition", expanded && "rotate-180")}
          />
        )}
      </button>

      {expanded && (
        <div className="space-y-3 px-4 pb-4">
          {g.reasoning !== null && (
            <p className="font-serif text-[13px] italic leading-snug text-foreground/60">
              {g.reasoning}
            </p>
          )}

          {isResearch ? (
            <>
              {g.planned !== null && (
                <div className="flex items-center gap-2 text-sm text-foreground/55">
                  <Brain className="h-4 w-4 text-foreground/40" /> Planned {g.planned} sub-questions,
                  fanned out to parallel agents
                </div>
              )}
              <div className="grid gap-2 sm:grid-cols-2">
                <AnimatePresence initial={false}>
                  {g.agents.map((agent, index) => {
                    const active = streaming && !agent.done;
                    return (
                      <motion.div
                        key={agent.subQuestion}
                        layout
                        initial={{ opacity: 0, y: 8, scale: 0.97 }}
                        animate={{ opacity: 1, y: 0, scale: 1 }}
                        transition={{ duration: 0.35, ease: editorialEase }}
                        className="rounded-md border border-foreground/15 bg-surface p-3"
                      >
                        <div className="flex items-center gap-2">
                          {agent.done ? (
                            <Check className="h-3.5 w-3.5 text-accent" />
                          ) : active ? (
                            <Loader2 className="h-3.5 w-3.5 animate-spin text-accent" />
                          ) : (
                            <Search className="h-3.5 w-3.5 text-foreground/40" />
                          )}
                          <span className="font-mono text-[10px] uppercase tracking-widest text-foreground/45">
                            Agent {index + 1}
                          </span>
                        </div>
                        <p
                          className="mt-1.5 line-clamp-2 font-serif text-[13px] leading-snug text-foreground/85"
                          title={agent.subQuestion}
                        >
                          {agent.subQuestion}
                        </p>
                        {agent.tool !== null && (
                          <p className="mt-1 truncate font-mono text-[11px] text-foreground/40">
                            {agent.tool}
                          </p>
                        )}
                      </motion.div>
                    );
                  })}
                </AnimatePresence>
              </div>
              {g.synthFindings !== null && (
                <div className="flex items-center gap-2 text-sm text-foreground/55">
                  <Layers className="h-4 w-4 text-foreground/40" /> Synthesizing {g.synthFindings}{" "}
                  findings
                </div>
              )}
              {g.reflection !== null && (
                <div className="flex items-center gap-2 text-sm text-foreground/55">
                  <RefreshCw className="h-4 w-4 text-foreground/40" /> Reflection — {g.reflection}
                </div>
              )}
            </>
          ) : (
            g.tools.length > 0 && (
              <ol className="space-y-2">
                {g.tools.map((tool, index) => (
                  <li key={index} className="flex items-center gap-2.5 text-sm text-foreground/55">
                    <Wrench className="h-4 w-4 shrink-0 text-foreground/40" />
                    <span className="truncate">{tool}</span>
                  </li>
                ))}
              </ol>
            )
          )}
        </div>
      )}
    </div>
  );
}
