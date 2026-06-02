"use client";

import { useEffect, useRef } from "react";

import { Composer } from "./components/Composer";
import { Sidebar } from "./components/Sidebar";
import { Turn } from "./components/Turn";
import { useAsk } from "./hooks/useAsk";
import { useChatStore } from "./store";

const EXAMPLES = [
  "What's the latest Claude model and what changed?",
  "Compare RRF and cross-encoder rerankers for hybrid retrieval",
  "Summarize the EU AI Act timeline for 2026",
];

export function ChatPage() {
  const { ask, cancel } = useAsk();
  const conversation = useChatStore(
    (state) => state.conversations.find((item) => item.id === state.activeId) ?? null,
  );
  const turns = conversation?.turns ?? [];
  const streaming = turns.some((turn) => turn.status === "streaming");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns.length]);

  return (
    <div className="flex h-dvh bg-white dark:bg-zinc-950">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center border-b border-zinc-200/60 px-5 py-3 dark:border-zinc-800/60 md:hidden">
          <span className="text-sm font-semibold tracking-tight">Argus</span>
        </header>

        <div className="flex-1 overflow-y-auto">
          <div className="mx-auto max-w-3xl px-4">
            {turns.length === 0 ? (
              <Hero onPick={(question) => ask(question, false)} />
            ) : (
              <div className="py-6">
                {turns.map((turn) => (
                  <Turn key={turn.id} turn={turn} onFollowUp={(question) => ask(question, false)} />
                ))}
                <div ref={bottomRef} />
              </div>
            )}
          </div>
        </div>

        <div className="border-t border-zinc-200/60 bg-white/80 backdrop-blur dark:border-zinc-800/60 dark:bg-zinc-950/80">
          <div className="mx-auto max-w-3xl px-4 py-3">
            <Composer onSubmit={ask} onCancel={cancel} busy={streaming} />
            <p className="mt-2 text-center text-[11px] text-zinc-400">
              Argus can be wrong — it cites sources so you can verify.
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
        <h1 className="text-3xl font-semibold tracking-tight">What do you want to research?</h1>
        <p className="mt-2.5 text-zinc-500 dark:text-zinc-400">
          Argus searches the live web and your ingested documents, then cites its sources.
        </p>
      </div>
      <div className="flex flex-wrap justify-center gap-2">
        {EXAMPLES.map((example) => (
          <button
            key={example}
            type="button"
            onClick={() => onPick(example)}
            className="rounded-full border border-zinc-200 px-4 py-2 text-sm text-zinc-600 transition hover:border-zinc-300 hover:bg-zinc-50 dark:border-zinc-800 dark:text-zinc-300 dark:hover:bg-zinc-900"
          >
            {example}
          </button>
        ))}
      </div>
    </div>
  );
}
