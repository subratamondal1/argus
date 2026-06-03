"use client";

import { AnimatePresence, motion } from "framer-motion";
import { Check, ChevronDown, Circle, Search, Wrench } from "lucide-react";
import { type ReactNode, useState } from "react";

import { cn } from "@/shared/lib/cn";
import { editorialEase } from "@/shared/lib/motion";

import type { AgentEvent } from "../types";
import { BorderBeam, BorderBeamRing } from "./BorderBeam";

type Status = "idle" | "running" | "complete";

interface AgentCard {
  subQuestion: string;
  tool: string | null;
  done: boolean;
}

interface ToolEntry {
  id: number;
  text: string;
}

interface Grouped {
  strategy: string | null;
  reasoning: string | null;
  planned: number | null;
  plannedQuestions: string[];
  agents: AgentCard[];
  tools: ToolEntry[];
  synthFindings: number | null;
  reflection: string | null;
}

const RESEARCHER_LABELS = ["A", "B", "C", "D", "E", "F", "G", "H"];

function group(events: AgentEvent[]): Grouped {
  const agents: AgentCard[] = [];
  const map = new Map<string, AgentCard>();
  const tools: ToolEntry[] = [];
  const grouped: Grouped = {
    strategy: null,
    reasoning: null,
    planned: null,
    plannedQuestions: [],
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
      grouped.plannedQuestions = event.sub_questions ?? [];
      grouped.planned = grouped.plannedQuestions.length;
    } else if (event.type === "synthesize") {
      grouped.synthFindings = event.findings ?? 0;
    } else if (event.type === "reflect") {
      grouped.reflection = event.complete
        ? "complete"
        : `following up on ${(event.missing ?? []).length}`;
    } else if (event.sub_question !== undefined) {
      const question = event.sub_question;
      let card = map.get(question);
      if (card === undefined) {
        card = { subQuestion: question, tool: null, done: false };
        map.set(question, card);
        agents.push(card);
      }
      if (event.type === "tool") {
        card.tool = `${event.name ?? "tool"}${event.query ? ` · ${event.query}` : ""}`;
      }
      if (event.type === "search_done") card.done = true;
    } else if (event.type === "tool") {
      tools.push({
        id: tools.length,
        text: `${event.name ?? "tool"}${event.query ? ` — ${event.query}` : ""}`,
      });
    }
  }

  grouped.agents = agents;
  return grouped;
}

export function Steps({ events, streaming }: { events: AgentEvent[]; streaming: boolean }) {
  const g = group(events);
  const isResearch = g.agents.length > 0 || g.planned !== null || g.strategy === "research";
  const hasBody = g.reasoning !== null || g.agents.length > 0 || g.tools.length > 0;

  // Nothing has come back yet but the request is in flight — show the panel
  // immediately with a running "Routing" row instead of a bare spinner, so the
  // turn never reads as empty while the triage step decides.
  if (g.strategy === null && !hasBody) {
    return streaming ? (
      <Panel title="Steps" meta="Working" beam>
        <PhaseRow label="Routing" detail="Deciding how to answer…" status="running" />
      </Panel>
    ) : null;
  }

  return isResearch ? (
    <ResearchSteps g={g} streaming={streaming} />
  ) : (
    <DirectSteps g={g} streaming={streaming} />
  );
}

function ResearchSteps({ g, streaming }: { g: Grouped; streaming: boolean }) {
  const doneAgents = g.agents.filter((agent) => agent.done).length;
  const allAgentsDone = g.agents.length > 0 && doneAgents === g.agents.length;
  const synthSeen = g.synthFindings !== null;

  const plannerStatus: Status = g.planned !== null ? "complete" : streaming ? "running" : "idle";
  const researchersStatus: Status =
    g.agents.length === 0
      ? g.planned !== null && streaming
        ? "running"
        : "idle"
      : synthSeen || (allAgentsDone && !streaming)
        ? "complete"
        : "running";
  const synthesizerStatus: Status = !synthSeen ? "idle" : streaming ? "running" : "complete";

  const completed = [plannerStatus, researchersStatus, synthesizerStatus].filter(
    (status) => status === "complete",
  ).length;

  return (
    <Panel title="Steps" meta={`${completed} of 3 complete`} beam={streaming}>
      {g.reasoning !== null && (
        <p className="border-b border-foreground/10 px-4 py-3 font-serif text-[13px] italic leading-snug text-foreground/65">
          {g.reasoning}
        </p>
      )}

      <PhaseRow
        label="Planner Agent"
        detail={plannerDetail(plannerStatus, g.planned ?? 0)}
        status={plannerStatus}
      >
        {g.plannedQuestions.length > 0 && (
          <ol className="space-y-1.5">
            {g.plannedQuestions.map((question, index) => (
              <li
                key={question}
                className="flex items-start gap-2.5 font-serif text-[13px] leading-snug text-foreground/85"
              >
                <span className="mt-0.5 font-mono text-[11px] tabular-nums text-foreground/40">
                  {String(index + 1).padStart(2, "0")}
                </span>
                <span className="flex-1">{question}</span>
              </li>
            ))}
          </ol>
        )}
      </PhaseRow>

      <PhaseRow
        label={g.agents.length > 0 ? `${g.agents.length} Parallel Researchers` : "Researchers"}
        detail={researchersDetail(researchersStatus, doneAgents, g.agents.length)}
        status={researchersStatus}
      >
        {g.agents.length > 0 && (
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
                    className={cn(
                      "relative rounded-sm border p-3",
                      active
                        ? "border-accent/40 bg-accent/[0.04]"
                        : "border-foreground/20 bg-background",
                    )}
                  >
                    <BorderBeamRing active={active} duration={3.2 + (index % 3) * 0.5} />
                    <div className="flex items-center gap-2">
                      {agent.done ? (
                        <span className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-accent">
                          <Check className="h-2.5 w-2.5 text-white" />
                        </span>
                      ) : active ? (
                        <motion.span
                          animate={{ scale: [1, 1.25, 1], opacity: [0.7, 1, 0.7] }}
                          transition={{ duration: 1.4, repeat: Infinity, ease: "easeInOut" }}
                          className="h-2.5 w-2.5 shrink-0 rounded-full bg-accent shadow-[0_0_8px_rgba(37,99,235,0.9)] dark:shadow-[0_0_10px_rgba(106,166,255,1)]"
                        />
                      ) : (
                        <Search className="h-3.5 w-3.5 shrink-0 text-foreground/40" />
                      )}
                      <span
                        className={cn(
                          "font-mono text-[10px] uppercase tracking-widest",
                          active ? "text-accent" : "text-foreground/55",
                        )}
                      >
                        Researcher {RESEARCHER_LABELS[index] ?? index + 1}
                      </span>
                      <span className="ml-auto font-mono text-[9px] uppercase tracking-widest">
                        {active ? (
                          <span className="text-accent">running</span>
                        ) : agent.done ? (
                          <span className="text-accent/55">done</span>
                        ) : (
                          <span className="text-foreground/30">queued</span>
                        )}
                      </span>
                    </div>
                    <p
                      className="mt-2 line-clamp-2 font-serif text-[13px] leading-snug text-foreground/90"
                      title={agent.subQuestion}
                    >
                      {agent.subQuestion}
                    </p>
                    {agent.tool !== null && (
                      <p className="mt-1.5 truncate font-mono text-[11px] text-foreground/45">
                        {agent.tool}
                      </p>
                    )}
                  </motion.div>
                );
              })}
            </AnimatePresence>
          </div>
        )}
      </PhaseRow>

      <PhaseRow
        label="Synthesizer Agent"
        detail={synthesizerDetail(synthesizerStatus, g.reflection)}
        status={synthesizerStatus}
      />
    </Panel>
  );
}

function DirectSteps({ g, streaming }: { g: Grouped; streaming: boolean }) {
  const status: Status = streaming ? "running" : "complete";
  return (
    <Panel title="Steps" meta="Direct" beam={streaming}>
      <PhaseRow
        label="Direct answer"
        detail={g.reasoning ?? (streaming ? "Answering directly…" : "Answered directly.")}
        status={status}
      >
        {g.tools.length > 0 && (
          <ol className="space-y-2">
            {g.tools.map((tool) => (
              <li key={tool.id} className="flex items-center gap-2.5 text-sm text-foreground/65">
                <Wrench className="h-4 w-4 shrink-0 text-accent/70" />
                <span className="truncate">{tool.text}</span>
              </li>
            ))}
          </ol>
        )}
      </PhaseRow>
    </Panel>
  );
}

function Panel({
  title,
  meta,
  beam = false,
  children,
}: {
  title: string;
  meta: string;
  beam?: boolean;
  children: ReactNode;
}) {
  return (
    <BorderBeam active={beam} duration={5} className="mb-5">
      <section className="overflow-hidden rounded-sm border border-foreground/20 bg-surface">
        <header className="flex items-center justify-between border-b border-foreground/15 px-4 py-2.5">
          <p className="font-mono text-[10px] uppercase tracking-widest text-foreground/55">
            {title}
          </p>
          <p className="font-mono text-[10px] uppercase tracking-widest tabular-nums text-foreground/45">
            {meta}
          </p>
        </header>
        <ol>{children}</ol>
      </section>
    </BorderBeam>
  );
}

function PhaseRow({
  label,
  detail,
  status,
  children,
}: {
  label: string;
  detail: string;
  status: Status;
  children?: ReactNode;
}) {
  const [override, setOverride] = useState<boolean | null>(null);
  const hasContent = Boolean(children);
  const expanded = (override ?? status === "running") && hasContent;

  return (
    <li className="border-b border-foreground/10 px-4 py-3.5 last:border-b-0">
      <div className="flex items-start gap-3">
        <span className="mt-0.5 shrink-0">
          <PhaseIcon status={status} />
        </span>
        <div className="min-w-0 flex-1">
          <button
            type="button"
            onClick={hasContent ? () => setOverride(!expanded) : undefined}
            disabled={!hasContent}
            aria-expanded={hasContent ? expanded : undefined}
            className={cn(
              "flex w-full items-center justify-between gap-3 text-left",
              hasContent ? "cursor-pointer" : "cursor-default",
            )}
          >
            <span className="flex-1 font-sans text-[14px] font-semibold leading-tight text-foreground">
              {label}
            </span>
            <span className="flex items-center gap-2">
              <StatusPill status={status} />
              {hasContent && (
                <ChevronDown
                  className={cn(
                    "h-3.5 w-3.5 text-foreground/40 transition-transform duration-200 ease-out",
                    expanded && "rotate-180",
                  )}
                />
              )}
            </span>
          </button>
          <p className="mt-1 font-serif text-[13px] leading-snug text-foreground/65">{detail}</p>
          <AnimatePresence initial={false}>
            {expanded && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                transition={{ duration: 0.3, ease: editorialEase }}
                className="overflow-hidden"
              >
                <div className="mt-3">{children}</div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </li>
  );
}

function PhaseIcon({ status }: { status: Status }) {
  if (status === "complete") {
    return (
      <span className="flex h-5 w-5 items-center justify-center rounded-full bg-accent">
        <Check className="h-3 w-3 text-white" strokeWidth={3} />
      </span>
    );
  }
  if (status === "running") {
    return (
      <motion.span
        animate={{ scale: [1, 1.06, 1], opacity: [0.85, 1, 0.85] }}
        transition={{ duration: 1.4, repeat: Infinity, ease: "easeInOut" }}
        className="flex h-5 w-5 items-center justify-center rounded-full border-2 border-accent bg-accent/15 shadow-[0_0_18px_-2px_rgba(37,99,235,0.55)] dark:shadow-[0_0_24px_-2px_rgba(106,166,255,0.7)]"
      >
        <span className="block h-1.5 w-1.5 rounded-full bg-accent" />
      </motion.span>
    );
  }
  return (
    <span className="flex h-5 w-5 items-center justify-center">
      <Circle className="h-4 w-4 text-foreground/25" strokeWidth={1.5} />
    </span>
  );
}

function StatusPill({ status }: { status: Status }) {
  const text = status === "idle" ? "Idle" : status === "running" ? "Running" : "Done";
  const tone =
    status === "idle"
      ? "text-foreground/35"
      : status === "running"
        ? "text-accent"
        : "text-accent/65";
  return <span className={cn("font-mono text-[9px] uppercase tracking-widest", tone)}>{text}</span>;
}

function plannerDetail(status: Status, planned: number): string {
  if (status === "complete") return `Decomposed into ${planned} sub-questions.`;
  if (status === "running") return "Decomposing the question…";
  return "Awaiting query.";
}

function researchersDetail(status: Status, done: number, total: number): string {
  if (status === "complete") return `${total} agents retrieved sources in parallel.`;
  if (status === "running") return `${done} of ${total} agents complete…`;
  return "Awaiting decomposition.";
}

function synthesizerDetail(status: Status, reflection: string | null): string {
  if (status === "complete") {
    return reflection === "complete"
      ? "Synthesized and verified a cited answer."
      : "Synthesized a cited answer.";
  }
  if (status === "running") return "Streaming the cited answer…";
  return "Awaiting evidence.";
}
