"use client";

import { FileUp } from "lucide-react";
import { type FormEvent, useState } from "react";

import { Button } from "@/shared/ui/Button";
import { Spinner } from "@/shared/ui/Spinner";

import { useIngest } from "../hooks/useIngest";

export function IngestPanel() {
  const [source, setSource] = useState("");
  const { ingest, status, message } = useIngest();

  function submit(event: FormEvent): void {
    event.preventDefault();
    const value = source.trim();
    if (value.length === 0 || status === "loading") return;
    void ingest(value);
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-2">
      <div className="flex gap-2">
        <input
          value={source}
          onChange={(event) => setSource(event.target.value)}
          placeholder="Ingest a file path or URL into the corpus…"
          className="flex-1 rounded-lg border border-black/10 bg-transparent px-3 py-2 text-sm outline-none placeholder:text-black/40 dark:border-white/15 dark:placeholder:text-white/40"
        />
        <Button type="submit" variant="ghost" disabled={status === "loading"}>
          {status === "loading" ? <Spinner /> : <FileUp className="h-4 w-4" />}
          Ingest
        </Button>
      </div>
      {message.length > 0 && (
        <p
          className={
            status === "error"
              ? "text-sm text-red-600 dark:text-red-400"
              : "text-sm text-black/50 dark:text-white/50"
          }
        >
          {message}
        </p>
      )}
    </form>
  );
}
