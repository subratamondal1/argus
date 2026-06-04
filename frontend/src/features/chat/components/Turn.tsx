"use client";

import { motion } from "framer-motion";
import { Check, Copy, Share2 } from "lucide-react";
import { useState } from "react";

import { cn } from "@/shared/lib/cn";
import { editorialEase } from "@/shared/lib/motion";

import type { Turn as TurnModel } from "../store";
import { Answer } from "./Answer";
import { Related } from "./Related";
import { SourcesStrip } from "./SourcesStrip";
import { Steps } from "./Steps";

export function Turn({
  turn,
  onFollowUp,
  cushion = 0,
}: {
  turn: TurnModel;
  onFollowUp: (question: string) => void;
  cushion?: number;
}) {
  const streaming = turn.status === "streaming";
  const [highlighted, setHighlighted] = useState<number | null>(null);

  // Turns persisted before the sources field existed rehydrate without it.
  const sources = turn.sources ?? [];

  // The strategy is unknown until triage routes the request, so don't label it
  // until then — guessing "Direct answer" on a request that's about to fan out
  // reads as wrong while it spins up.
  const triageStrategy = turn.events.find((event) => event.type === "triage")?.strategy;
  const planned = turn.events.some((event) => event.type === "plan");
  const isResearch = turn.deep || triageStrategy === "research" || planned;
  const known = turn.deep || triageStrategy !== undefined || planned || !streaming;
  const eyebrow = isResearch ? "Deep research" : known ? "Direct answer" : "Working";

  return (
    <article
      className="border-b border-foreground/10 py-8 first:pt-2 last:border-0"
      style={cushion > 0 ? { minHeight: cushion } : undefined}
    >
      <p className="mb-2 font-mono text-[10px] uppercase tracking-widest text-foreground/40">
        {eyebrow}
      </p>
      <motion.h2
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: editorialEase }}
        className="mb-5 font-sans text-[22px] font-semibold leading-snug tracking-tight"
      >
        {turn.question}
      </motion.h2>

      <Steps events={turn.events} streaming={streaming} />

      <SourcesStrip
        sources={sources}
        highlighted={highlighted}
        onEnter={setHighlighted}
        onLeave={() => setHighlighted(null)}
      />

      {turn.answer.length > 0 && (
        <section className="mb-2 rounded-sm border border-foreground/20 bg-surface">
          <header className="flex items-center justify-between gap-3 border-b border-foreground/15 px-4 py-2.5">
            <p className="font-mono text-[10px] uppercase tracking-widest text-foreground/55">
              Answer
            </p>
            <div className="flex items-center gap-3">
              <p
                className={cn(
                  "font-mono text-[10px] uppercase tracking-widest tabular-nums",
                  turn.refining ? "text-accent" : "text-foreground/45",
                )}
              >
                {turn.refining
                  ? "Verifying & refining…"
                  : streaming
                    ? "Streaming"
                    : `Synthesized · ${sources.length} source${sources.length === 1 ? "" : "s"}`}
              </p>
              {!streaming && <AnswerActions question={turn.question} answer={turn.answer} />}
            </div>
          </header>
          <div className="px-4 py-4 md:px-5 md:py-5">
            <Answer
              text={turn.answer}
              streaming={streaming}
              refining={turn.refining}
              sources={sources}
              highlighted={highlighted}
              onCitationEnter={setHighlighted}
              onCitationLeave={() => setHighlighted(null)}
            />
            {/* The draft stays fully readable; a launching "Reviewer Agent" makes
                clear the pause is deliberate self-checking, not a stuck cursor. */}
            {turn.refining && <ReviewingIndicator />}
          </div>
        </section>
      )}

      {turn.error !== null && (
        <p className="mt-3 rounded-md border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-500">
          {turn.error}
        </p>
      )}

      {!streaming && <Related questions={turn.related ?? []} onPick={onFollowUp} />}
    </article>
  );
}

// Shown below the draft while the agent self-verifies and re-researches. Styled
// like the launching of a new agent (pulsing accent dot + label), so the pause
// reads as deliberate work rather than a frozen stream.
function ReviewingIndicator() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: editorialEase }}
      className="mt-5 flex items-center gap-2.5 border-t border-foreground/10 pt-4"
    >
      <motion.span
        animate={{ scale: [1, 1.25, 1], opacity: [0.7, 1, 0.7] }}
        transition={{ duration: 1.4, repeat: Number.POSITIVE_INFINITY, ease: "easeInOut" }}
        className="h-2.5 w-2.5 shrink-0 rounded-full bg-accent shadow-[0_0_8px_rgba(37,99,235,0.9)] dark:shadow-[0_0_10px_rgba(106,166,255,1)]"
      />
      <span className="font-mono text-[10px] uppercase tracking-widest text-accent">
        Reviewer Agent
      </span>
      <span className="font-serif text-[13px] italic leading-snug text-foreground/65">
        verifying the answer and refining for accuracy…
      </span>
    </motion.div>
  );
}

function AnswerActions({ question, answer }: { question: string; answer: string }) {
  const [copied, setCopied] = useState(false);

  async function copy(): Promise<void> {
    await navigator.clipboard.writeText(answer);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1500);
  }

  async function share(): Promise<void> {
    if (typeof navigator.share === "function") {
      try {
        await navigator.share({ title: question, text: answer });
      } catch {
        await copy();
      }
      return;
    }
    await copy();
  }

  return (
    <div className="flex items-center gap-1">
      <button
        type="button"
        onClick={copy}
        title="Copy answer"
        className={cn(
          "rounded p-1.5 transition hover:bg-foreground/10",
          copied ? "text-accent" : "text-foreground/45 hover:text-foreground/75",
        )}
      >
        {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
      </button>
      <button
        type="button"
        onClick={share}
        title="Share answer"
        className="rounded p-1.5 text-foreground/45 transition hover:bg-foreground/10 hover:text-foreground/75"
      >
        <Share2 className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}
