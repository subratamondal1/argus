"use client";

import { Menu, PenSquare } from "lucide-react";
import { useEffect, useState } from "react";

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
  const [navOpen, setNavOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const conversation = useChatStore(
    (state) => state.conversations.find((item) => item.id === state.activeId) ?? null,
  );
  const newConversation = useChatStore((state) => state.newConversation);
  const turns = conversation?.turns ?? [];
  const streaming = turns.some((turn) => turn.status === "streaming");
  const scrollRef = useStickToBottom(turns.length);
  const [viewport, setViewport] = useState(0);

  // Track the scroll viewport height so the active turn can be cushioned to fill
  // it — that is what lets a freshly-sent question glide to the top of the view.
  useEffect(() => {
    const element = scrollRef.current;
    if (element === null) return;
    const update = (): void => setViewport(element.clientHeight);
    update();
    const observer = new ResizeObserver(update);
    observer.observe(element);
    return () => observer.disconnect();
  }, [scrollRef]);

  return (
    <div className="flex h-dvh bg-background text-foreground">
      <Sidebar
        open={navOpen}
        onClose={() => setNavOpen(false)}
        collapsed={collapsed}
        onToggleCollapse={() => setCollapsed((value) => !value)}
      />
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between gap-2 border-b border-foreground/10 px-2 py-2 md:hidden">
          <button
            type="button"
            onClick={() => setNavOpen(true)}
            aria-label="Open menu"
            className="rounded-md p-2 text-foreground/70 transition hover:bg-foreground/10"
          >
            <Menu className="h-5 w-5" />
          </button>
          <span className="text-sm font-semibold tracking-tight">Argus</span>
          <button
            type="button"
            onClick={() => newConversation()}
            aria-label="New chat"
            className="rounded-md p-2 text-foreground/70 transition hover:bg-foreground/10"
          >
            <PenSquare className="h-5 w-5" />
          </button>
        </header>

        <div ref={scrollRef} className="flex-1 overflow-y-auto">
          <div className="mx-auto max-w-3xl px-4">
            {turns.length === 0 ? (
              <Hero onPick={(question) => ask(question, false)} />
            ) : (
              <div className="py-6">
                {turns.map((turn, index) => (
                  <Turn
                    key={turn.id}
                    turn={turn}
                    onFollowUp={(question) => ask(question, false)}
                    cushion={
                      index === turns.length - 1 && turn.status === "streaming" ? viewport : 0
                    }
                  />
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="border-t border-foreground/10 bg-background/80 backdrop-blur">
          <div className="mx-auto max-w-3xl px-4 py-3">
            <Composer onSubmit={ask} onCancel={cancel} busy={streaming} />
            <p className="mt-2 truncate whitespace-nowrap text-center font-mono text-[clamp(6.5px,2.3vw,10px)] uppercase tracking-widest text-foreground/35">
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
      <div className="flex w-full max-w-2xl flex-col items-center gap-2.5">
        {EXAMPLES.map((example) => (
          <button
            key={example}
            type="button"
            onClick={() => onPick(example)}
            className="w-fit max-w-full rounded-full border border-foreground/20 px-5 py-2.5 text-center text-sm text-foreground/70 transition hover:border-accent/55 hover:text-foreground hover:shadow-[0_0_20px_-8px_rgba(37,99,235,0.5)] dark:hover:shadow-[0_0_24px_-8px_rgba(106,166,255,0.55)]"
          >
            {example}
          </button>
        ))}
      </div>
    </div>
  );
}
