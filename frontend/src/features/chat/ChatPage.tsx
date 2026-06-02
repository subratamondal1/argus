"use client";

import { Loader2 } from "lucide-react";

import { Answer } from "./components/Answer";
import { Composer } from "./components/Composer";
import { Steps } from "./components/Steps";
import { useChatStream } from "./hooks/useChatStream";

const EXAMPLES = [
  "What's the latest Claude model and what changed?",
  "Compare RRF and cross-encoder rerankers for hybrid retrieval",
  "Summarize the EU AI Act timeline for 2026",
];

export function ChatPage() {
  const { question, events, answer, status, error, ask, cancel } = useChatStream();
  const idle = status === "idle" && question.length === 0;
  const streaming = status === "streaming";

  return (
    <div className="flex h-dvh flex-col bg-white dark:bg-zinc-950">
      <header className="flex items-center justify-between border-b border-zinc-200/60 px-5 py-3 dark:border-zinc-800/60">
        <span className="text-sm font-semibold tracking-tight">Argus</span>
        <span className="text-xs text-zinc-400">multi-agent deep research</span>
      </header>

      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-3xl px-4 py-8">
          {idle ? (
            <div className="flex flex-col items-center gap-7 pt-[12vh] text-center">
              <div>
                <h1 className="text-3xl font-semibold tracking-tight">
                  What do you want to research?
                </h1>
                <p className="mt-2.5 text-zinc-500 dark:text-zinc-400">
                  Argus searches the live web and your ingested documents, then cites
                  its sources.
                </p>
              </div>
              <div className="flex flex-wrap justify-center gap-2">
                {EXAMPLES.map((example) => (
                  <button
                    key={example}
                    type="button"
                    onClick={() => ask(example, false)}
                    className="rounded-full border border-zinc-200 px-4 py-2 text-sm text-zinc-600 transition hover:border-zinc-300 hover:bg-zinc-50 dark:border-zinc-800 dark:text-zinc-300 dark:hover:bg-zinc-900"
                  >
                    {example}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div>
              <h2 className="mb-5 text-xl font-semibold tracking-tight">{question}</h2>
              <Steps events={events} streaming={streaming} />
              <Answer text={answer} streaming={streaming} />
              {streaming && answer.length === 0 && (
                <div className="flex items-center gap-2 text-sm text-zinc-400">
                  <Loader2 className="h-4 w-4 animate-spin" /> thinking…
                </div>
              )}
              {error !== null && (
                <p className="mt-4 rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/40 dark:text-red-300">
                  {error}
                </p>
              )}
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
  );
}
