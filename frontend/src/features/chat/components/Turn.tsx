import { motion } from "framer-motion";
import { Loader2 } from "lucide-react";

import { editorialEase } from "@/shared/lib/motion";

import type { Turn as TurnModel } from "../store";
import { Answer } from "./Answer";
import { Artifact } from "./Artifact";
import { Related } from "./Related";
import { Sources } from "./Sources";
import { Steps } from "./Steps";

export function Turn({
  turn,
  onFollowUp,
}: {
  turn: TurnModel;
  onFollowUp: (question: string) => void;
}) {
  const streaming = turn.status === "streaming";
  return (
    <article className="border-b border-foreground/10 py-8 first:pt-2 last:border-0">
      <motion.h2
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: editorialEase }}
        className="mb-5 font-sans text-[22px] font-semibold leading-snug tracking-tight"
      >
        {turn.question}
      </motion.h2>
      <Steps events={turn.events} streaming={streaming} />
      {!streaming && <Sources text={turn.answer} />}
      {turn.artifact ? (
        <Artifact artifact={turn.artifact} />
      ) : (
        <Answer text={turn.answer} streaming={streaming} />
      )}
      {streaming && turn.events.length === 0 && turn.answer.length === 0 && (
        <div className="flex items-center gap-2 text-sm text-foreground/45">
          <Loader2 className="h-4 w-4 animate-spin" /> thinking…
        </div>
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
