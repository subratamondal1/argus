"use client";

import { ArrowUp, Check, Link2, Loader2, Paperclip, Square, X } from "lucide-react";
import {
  type DragEvent,
  type FormEvent,
  type KeyboardEvent,
  type ReactNode,
  useRef,
  useState,
} from "react";

import { cn } from "@/shared/lib/cn";

import { useIngest } from "../hooks/useIngest";

interface Props {
  onSubmit: (question: string, deep: boolean) => void;
  onCancel: () => void;
  busy: boolean;
}

export function Composer({ onSubmit, onCancel, busy }: Props) {
  const [value, setValue] = useState("");
  const [deep, setDeep] = useState(false);
  const [url, setUrl] = useState("");
  const [showUrl, setShowUrl] = useState(false);
  const [dragging, setDragging] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const { ingestUrl, uploadFile, clearError, status, error, sources } = useIngest();

  function send(): void {
    const question = value.trim();
    if (question.length === 0 || busy) return;
    onSubmit(question, deep);
    setValue("");
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>): void {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      send();
    }
  }

  function onFiles(files: FileList | null): void {
    if (files === null) return;
    for (const file of Array.from(files)) void uploadFile(file);
  }

  function onDrop(event: DragEvent): void {
    event.preventDefault();
    setDragging(false);
    onFiles(event.dataTransfer.files);
  }

  return (
    <div
      className="relative"
      onDragOver={(event) => {
        event.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
    >
      {dragging && (
        <div className="absolute inset-0 z-10 flex items-center justify-center rounded-2xl border-2 border-dashed border-indigo-400 bg-indigo-50/90 text-sm font-medium text-indigo-700 dark:bg-indigo-950/80 dark:text-indigo-200">
          Drop a file to ingest into the corpus
        </div>
      )}

      {(sources.length > 0 || error !== null) && (
        <div className="mb-2 flex flex-wrap gap-2">
          {sources.map((source) => (
            <span
              key={source.label}
              className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-3 py-1 text-xs text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300"
            >
              <Check className="h-3 w-3" />
              {source.label} · {source.chunks} chunks
            </span>
          ))}
          {error !== null && (
            <button
              type="button"
              onClick={clearError}
              className="inline-flex items-center gap-1.5 rounded-full bg-red-50 px-3 py-1 text-xs text-red-600 transition hover:bg-red-100 dark:bg-red-950/50 dark:text-red-300 dark:hover:bg-red-950"
              title="Dismiss"
            >
              {error}
              <X className="h-3 w-3" />
            </button>
          )}
        </div>
      )}

      <form
        onSubmit={(event: FormEvent) => {
          event.preventDefault();
          send();
        }}
        className="rounded-2xl border border-zinc-200 bg-white shadow-sm focus-within:border-zinc-300 dark:border-zinc-800 dark:bg-zinc-900 dark:focus-within:border-zinc-700"
      >
        <textarea
          value={value}
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Ask Argus anything…"
          rows={1}
          className="max-h-48 w-full resize-none bg-transparent px-4 pt-3.5 text-[15px] outline-none placeholder:text-zinc-400 dark:placeholder:text-zinc-500"
          autoFocus
        />

        {showUrl && (
          <div className="flex gap-2 px-3 pb-1">
            <input
              value={url}
              onChange={(event) => setUrl(event.target.value)}
              placeholder="https://… or a local file path"
              className="flex-1 rounded-lg border border-zinc-200 bg-transparent px-3 py-1.5 text-sm outline-none dark:border-zinc-800"
            />
            <button
              type="button"
              onClick={() => {
                const trimmed = url.trim();
                if (trimmed.length > 0) {
                  void ingestUrl(trimmed);
                  setUrl("");
                }
              }}
              className="rounded-lg bg-zinc-900 px-3 py-1.5 text-sm text-white dark:bg-zinc-100 dark:text-zinc-900"
            >
              Add
            </button>
          </div>
        )}

        <div className="flex items-center gap-1 px-2.5 pb-2.5">
          <IconButton title="Attach a file" onClick={() => fileRef.current?.click()}>
            {status === "loading" ? (
              <Loader2 className="h-[18px] w-[18px] animate-spin" />
            ) : (
              <Paperclip className="h-[18px] w-[18px]" />
            )}
          </IconButton>
          <IconButton title="Ingest a URL or path" onClick={() => setShowUrl((v) => !v)}>
            <Link2 className="h-[18px] w-[18px]" />
          </IconButton>
          <button
            type="button"
            onClick={() => setDeep((value) => !value)}
            className={cn(
              "ml-1 rounded-full px-3 py-1.5 text-xs font-medium transition",
              deep
                ? "bg-indigo-600 text-white"
                : "text-zinc-500 hover:bg-zinc-100 dark:hover:bg-zinc-800",
            )}
          >
            Deep research
          </button>

          <div className="flex-1" />

          {busy ? (
            <button
              type="button"
              onClick={onCancel}
              className="rounded-lg bg-zinc-200 p-2 text-zinc-700 hover:bg-zinc-300 dark:bg-zinc-700 dark:text-zinc-100"
              aria-label="Stop"
            >
              <Square className="h-[18px] w-[18px]" />
            </button>
          ) : (
            <button
              type="submit"
              disabled={value.trim().length === 0}
              className="rounded-lg bg-indigo-600 p-2 text-white transition hover:bg-indigo-500 disabled:opacity-30"
              aria-label="Send"
            >
              <ArrowUp className="h-[18px] w-[18px]" />
            </button>
          )}
        </div>
      </form>

      <input
        ref={fileRef}
        type="file"
        hidden
        multiple
        onChange={(event) => onFiles(event.target.files)}
      />
    </div>
  );
}

function IconButton({
  title,
  onClick,
  children,
}: {
  title: string;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      title={title}
      onClick={onClick}
      className="rounded-lg p-2 text-zinc-500 transition hover:bg-zinc-100 hover:text-zinc-800 dark:hover:bg-zinc-800 dark:hover:text-zinc-200"
    >
      {children}
    </button>
  );
}
