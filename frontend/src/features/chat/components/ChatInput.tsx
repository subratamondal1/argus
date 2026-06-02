"use client";

import { ArrowUp } from "lucide-react";
import { type FormEvent, useState } from "react";

import { Button } from "@/shared/ui/Button";
import { Spinner } from "@/shared/ui/Spinner";

interface Props {
  onSubmit: (question: string, deep: boolean) => void;
  onCancel: () => void;
  busy: boolean;
}

export function ChatInput({ onSubmit, onCancel, busy }: Props) {
  const [value, setValue] = useState("");
  const [deep, setDeep] = useState(false);

  function submit(event: FormEvent): void {
    event.preventDefault();
    const question = value.trim();
    if (question.length === 0 || busy) return;
    onSubmit(question, deep);
  }

  return (
    <form
      onSubmit={submit}
      className="flex flex-col gap-3 rounded-2xl border border-black/10 bg-white p-3 shadow-sm dark:border-white/15 dark:bg-white/5"
    >
      <input
        value={value}
        onChange={(event) => setValue(event.target.value)}
        placeholder="Ask Argus anything…"
        className="w-full bg-transparent px-2 py-1.5 text-base outline-none placeholder:text-black/40 dark:placeholder:text-white/40"
        autoFocus
      />
      <div className="flex items-center justify-between">
        <label className="flex cursor-pointer items-center gap-2 text-sm text-black/60 dark:text-white/60">
          <input
            type="checkbox"
            checked={deep}
            onChange={(event) => setDeep(event.target.checked)}
            className="accent-foreground"
          />
          deep research (multi-agent)
        </label>
        {busy ? (
          <Button type="button" variant="ghost" onClick={onCancel}>
            <Spinner /> Stop
          </Button>
        ) : (
          <Button type="submit" aria-label="Send">
            <ArrowUp className="h-4 w-4" /> Ask
          </Button>
        )}
      </div>
    </form>
  );
}
