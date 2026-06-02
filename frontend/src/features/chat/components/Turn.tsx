import { Loader2 } from "lucide-react";

import type { Turn as TurnModel } from "../store";
import { Answer } from "./Answer";
import { Steps } from "./Steps";

export function Turn({ turn }: { turn: TurnModel }) {
  const streaming = turn.status === "streaming";
  return (
    <article className="border-b border-zinc-200/50 py-7 first:pt-2 last:border-0 dark:border-zinc-800/40">
      <h2 className="mb-5 text-[22px] font-semibold leading-snug tracking-tight">
        {turn.question}
      </h2>
      <Steps events={turn.events} streaming={streaming} />
      <Answer text={turn.answer} streaming={streaming} />
      {streaming && turn.answer.length === 0 && (
        <div className="flex items-center gap-2 text-sm text-zinc-400">
          <Loader2 className="h-4 w-4 animate-spin" /> thinking…
        </div>
      )}
      {turn.error !== null && (
        <p className="mt-3 rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/40 dark:text-red-300">
          {turn.error}
        </p>
      )}
    </article>
  );
}
