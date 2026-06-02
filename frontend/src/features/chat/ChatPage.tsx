"use client";

import { Spinner } from "@/shared/ui/Spinner";

import { AnswerView } from "./components/AnswerView";
import { ChatInput } from "./components/ChatInput";
import { IngestPanel } from "./components/IngestPanel";
import { ProgressFeed } from "./components/ProgressFeed";
import { useChatStream } from "./hooks/useChatStream";

export function ChatPage() {
  const { events, answer, status, error, ask, cancel } = useChatStream();
  const thinking = status === "streaming" && answer.length === 0;

  return (
    <main className="mx-auto flex min-h-dvh max-w-3xl flex-col gap-5 px-4 py-10">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Argus</h1>
        <p className="text-sm text-black/50 dark:text-white/50">
          Framework-free multi-agent deep-research engine — searches the live web
          and your ingested corpus.
        </p>
      </header>

      <IngestPanel />

      <section className="flex flex-1 flex-col gap-4">
        <ProgressFeed events={events} />
        {thinking && (
          <div className="flex items-center gap-2 text-sm text-black/50 dark:text-white/50">
            <Spinner /> working…
          </div>
        )}
        <AnswerView answer={answer} />
        {error !== null && (
          <p className="rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/40 dark:text-red-300">
            {error}
          </p>
        )}
      </section>

      <ChatInput onSubmit={ask} onCancel={cancel} busy={status === "streaming"} />
    </main>
  );
}
