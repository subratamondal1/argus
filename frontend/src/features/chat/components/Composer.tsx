"use client";

import { ArrowUp, Check, Link2, Loader2, Paperclip, Plus, Square, X } from "lucide-react";
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
import { TextShimmer } from "./TextShimmer";

interface Props {
  onSubmit: (question: string, deep: boolean, ingested: string[]) => void;
  onCancel: () => void;
  busy: boolean;
}

export function Composer({ onSubmit, onCancel, busy }: Props) {
  const [value, setValue] = useState("");
  const [deep, setDeep] = useState(false);
  const [url, setUrl] = useState("");
  const [showUrl, setShowUrl] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [dragging, setDragging] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const { ingestUrl, uploadFile, clearError, status, error, sources } = useIngest();

  // Grow the textarea to fit its content up to ~8 lines (192px = max-h-48),
  // then scroll. Native rows={1} alone would clip multi-line input.
  function autosize(el: HTMLTextAreaElement): void {
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 192)}px`;
  }

  function send(): void {
    const question = value.trim();
    if (question.length === 0 || busy) return;
    onSubmit(
      question,
      deep,
      sources.map((source) => source.label),
    );
    setValue("");
    if (textareaRef.current) textareaRef.current.style.height = "auto";
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
    // biome-ignore lint/a11y/noStaticElementInteractions: drag-and-drop dropzone wraps the composer; file upload is also reachable via the + menu.
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
        <div className="absolute inset-0 z-20 flex items-center justify-center rounded-2xl border-2 border-dashed border-accent bg-background/90 font-mono text-[11px] uppercase tracking-widest text-accent">
          Drop a file to ingest
        </div>
      )}

      {(sources.length > 0 || error !== null) && (
        <div className="mb-2 flex flex-wrap gap-2">
          {sources.map((source) => (
            <span
              key={source.label}
              className="inline-flex items-center gap-1.5 rounded-full border border-accent/30 bg-accent/10 px-3 py-1 text-xs text-foreground/75"
            >
              <Check className="h-3 w-3 text-accent" />
              {source.label} · {source.chunks} chunks
            </span>
          ))}
          {error !== null && (
            <button
              type="button"
              onClick={clearError}
              className="inline-flex items-center gap-1.5 rounded-full border border-red-500/30 bg-red-500/10 px-3 py-1 text-xs text-red-500 transition hover:bg-red-500/20"
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
        className="rounded-2xl border border-foreground/30 bg-foreground/[0.05] shadow-[0_10px_34px_-14px_rgba(0,0,0,0.8)] transition-all duration-200 has-[textarea:focus]:border-accent/60 has-[textarea:focus]:bg-foreground/[0.07] has-[textarea:focus]:shadow-[0_0_0_3px_rgba(37,99,235,0.16),0_12px_38px_-12px_rgba(37,99,235,0.4)] dark:has-[textarea:focus]:shadow-[0_0_0_3px_rgba(106,166,255,0.18),0_14px_44px_-12px_rgba(106,166,255,0.4)]"
      >
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(event) => {
            setValue(event.target.value);
            autosize(event.target);
          }}
          onKeyDown={onKeyDown}
          placeholder="Ask Argus anything…"
          rows={1}
          className="max-h-48 w-full resize-none overflow-y-auto bg-transparent px-4 pt-3.5 font-serif text-[15px] outline-none placeholder:text-foreground/50"
          // biome-ignore lint/a11y/noAutofocus: the composer is the page's primary action; focusing it on load is the intended single-input UX.
          autoFocus
        />

        {showUrl && (
          <div className="flex gap-2 px-3 pb-1">
            <input
              value={url}
              onChange={(event) => setUrl(event.target.value)}
              placeholder="https://… or a local file path"
              className="flex-1 rounded-md border border-foreground/15 bg-transparent px-3 py-1.5 text-sm outline-none focus:border-accent/50"
            />
            <button
              type="button"
              onClick={() => {
                const trimmed = url.trim();
                if (trimmed.length > 0) {
                  void ingestUrl(trimmed);
                  setUrl("");
                  setShowUrl(false);
                }
              }}
              className="rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition hover:opacity-90"
            >
              Add
            </button>
          </div>
        )}

        <div className="flex items-center gap-1.5 px-2.5 pb-2.5">
          <div className="relative">
            <button
              type="button"
              onClick={() => setMenuOpen((open) => !open)}
              aria-label="Add a source"
              aria-expanded={menuOpen}
              className={cn(
                "flex h-8 w-8 items-center justify-center rounded-full border transition",
                menuOpen
                  ? "border-accent/50 bg-accent/10 text-accent"
                  : "border-foreground/20 text-foreground/60 hover:border-foreground/40 hover:text-foreground/90",
              )}
            >
              {status === "loading" ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Plus className={cn("h-4 w-4 transition-transform", menuOpen && "rotate-45")} />
              )}
            </button>

            {menuOpen && (
              <>
                <button
                  type="button"
                  aria-label="Close menu"
                  className="fixed inset-0 z-30 cursor-default"
                  onClick={() => setMenuOpen(false)}
                />
                <div className="absolute bottom-full left-0 z-40 mb-2 w-48 overflow-hidden rounded-xl border border-foreground/20 bg-surface shadow-[0_12px_40px_-12px_rgba(0,0,0,0.8)]">
                  <MenuItem
                    icon={<Paperclip className="h-4 w-4" />}
                    label="Attach a file"
                    onClick={() => {
                      setMenuOpen(false);
                      fileRef.current?.click();
                    }}
                  />
                  <MenuItem
                    icon={<Link2 className="h-4 w-4" />}
                    label="Ingest a URL"
                    onClick={() => {
                      setMenuOpen(false);
                      setShowUrl(true);
                    }}
                  />
                </div>
              </>
            )}
          </div>

          <button
            type="button"
            onClick={() => setDeep((on) => !on)}
            aria-pressed={deep}
            className={cn(
              "rounded-full border px-3 py-1.5 font-mono text-[10px] uppercase tracking-widest transition",
              deep
                ? "border-accent/70 bg-accent/15"
                : "border-foreground/25 bg-foreground/[0.04] text-foreground/70 hover:border-foreground/45 hover:text-foreground/90",
            )}
          >
            {deep ? (
              <TextShimmer
                duration={2.2}
                baseColor="color-mix(in oklab, var(--accent) 55%, transparent)"
                shimmerColor="var(--accent)"
              >
                Deep research
              </TextShimmer>
            ) : (
              "Deep research"
            )}
          </button>

          <div className="flex-1" />

          {busy ? (
            <button
              type="button"
              onClick={onCancel}
              className="rounded-lg bg-foreground/15 p-2 text-foreground/80 transition hover:bg-foreground/25"
              aria-label="Stop"
            >
              <Square className="h-[18px] w-[18px]" />
            </button>
          ) : (
            <button
              type="submit"
              disabled={value.trim().length === 0}
              className="rounded-lg bg-accent p-2 text-white transition hover:opacity-90 disabled:opacity-30"
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

function MenuItem({
  icon,
  label,
  onClick,
}: {
  icon: ReactNode;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex w-full items-center gap-3 px-3.5 py-2.5 text-left text-sm text-foreground/80 transition hover:bg-foreground/[0.06] hover:text-foreground"
    >
      <span className="text-foreground/55">{icon}</span>
      {label}
    </button>
  );
}
