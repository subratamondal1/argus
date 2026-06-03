"use client";

import { Composer } from "./components/Composer";
import { Sidebar } from "./components/Sidebar";
import { Turn } from "./components/Turn";
import { useAsk } from "./hooks/useAsk";
import { useStickToBottom } from "./hooks/useStickToBottom";
import { useChatStore } from "./store";

const EXAMPLES = [
  "What's the latest Claude model and what changed?",
  "Research the competitive landscape for AI coding agents in 2026",
  "Compare RRF and cross-encoder rerankers for hybrid retrieval",
];

export function ChatPage() {
  const { ask, cancel } = useAsk();
  const conversation = useChatStore(
    (state) => state.conversations.find((item) => item.id === state.activeId) ?? null,
  );
  const turns = conversation?.turns ?? [];
  const streaming = turns.some((turn) => turn.status === "streaming");
  const scrollRef = useStickToBottom();

  return (
    <div className="flex h-dvh bg-background text-foreground">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center border-b border-foreground/10 px-5 py-3 md:hidden">
          <span className="text-sm font-semibold tracking-tight">Argus</span>
        </header>

        <div ref={scrollRef} className="flex-1 overflow-y-auto">
          <div className="mx-auto max-w-3xl px-4">
            {turns.length === 0 ? (
              <Hero onPick={(question) => ask(question, false)} />
            ) : (
              <div className="py-6">
                {turns.map((turn) => (
                  <Turn key={turn.id} turn={turn} onFollowUp={(question) => ask(question, false)} />
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="border-t border-foreground/10 bg-background/80 backdrop-blur">
          <div className="mx-auto max-w-3xl px-4 py-3">
            <Composer onSubmit={ask} onCancel={cancel} busy={streaming} />
            <p className="mt-2 text-center font-mono text-[10px] uppercase tracking-widest text-foreground/35">
              Argus can be wrong — it cites sources so you can verify
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

function Hero({ onPick }: { onPick: (question: string) => void }) {
  return (
    <div className="flex flex-col items-center gap-7 pt-[14vh] text-center">
      <div>
        <h1 className="font-sans text-3xl font-semibold tracking-tight md:text-4xl">
          What do you want to research?
        </h1>
        <p className="mx-auto mt-3 max-w-md font-serif text-[15px] italic leading-relaxed text-foreground/55">
          Argus decides whether to answer directly or fan out a team of agents over the live web and
          your documents, then cites its sources.
        </p>
      </div>
      <div className="flex w-full max-w-xl flex-col gap-2">
        {EXAMPLES.map((example) => (
          <button
            key={example}
            type="button"
            onClick={() => onPick(example)}
            className="rounded-md border border-foreground/15 px-4 py-2.5 text-left text-sm text-foreground/70 transition hover:border-accent/55 hover:text-foreground"
          >
            {example}
          </button>
        ))}
      </div>
    </div>
  );
}
