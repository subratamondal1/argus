"use client";

import {
  ArrowUp,
  Check,
  Eye,
  Link2,
  Loader2,
  Paperclip,
  Plus,
  Square,
  TriangleAlert,
  X,
} from "lucide-react";
import {
  type ClipboardEvent,
  type DragEvent,
  type FormEvent,
  type KeyboardEvent,
  type ReactNode,
  useEffect,
  useRef,
  useState,
} from "react";
import { createPortal } from "react-dom";

import { cn } from "@/shared/lib/cn";

import { type IngestedSource, MAX_SOURCES, useIngest } from "../hooks/useIngest";
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
  const [preview, setPreview] = useState<IngestedSource | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const {
    ingestUrl,
    uploadFile,
    removeSource,
    cancel,
    clearError,
    status,
    pending,
    atLimit,
    error,
    sources,
  } = useIngest();

  // The preview overlay is position:fixed, but the composer lives inside a
  // backdrop-blur container — and backdrop-filter (like transform) makes that
  // container the containing block for fixed children, trapping the overlay in
  // the input bar and letting the page scroll behind it. While a preview is
  // open, lock background scroll; the overlay itself is portaled to <body> below
  // so it escapes the blur context and pins to the real viewport.
  useEffect(() => {
    if (!preview?.previewUrl) return;
    const previous: string = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previous;
    };
  }, [preview?.previewUrl]);

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
      sources.filter((source) => source.chunks > 0).map((source) => source.label),
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

  // Paste a screenshot or a file copied from the OS straight into the composer:
  // the clipboard carries them as File objects in clipboardData.files. Route them
  // through the same ingest path as drag-drop/the picker. Only swallow the paste
  // when files are present — a normal text paste still lands in the textarea.
  function onPaste(event: ClipboardEvent<HTMLTextAreaElement>): void {
    const files: FileList = event.clipboardData.files;
    if (files.length === 0) return;
    event.preventDefault();
    onFiles(files);
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

      {(sources.length > 0 || error !== null || pending !== null) && (
        // Single row: chips keep their size (shrink-0) and the strip scrolls
        // horizontally once they overflow, rather than wrapping and growing taller.
        <div className="mb-2 flex gap-2 overflow-x-auto pb-1 [scrollbar-width:thin]">
          {pending !== null && (
            <div className="flex h-[58px] w-[58px] shrink-0 flex-col overflow-hidden rounded-md border border-foreground/25 bg-foreground/[0.06] p-1.5 text-foreground/70">
              <div className="flex items-start justify-between">
                <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin text-foreground/55" />
                <button
                  type="button"
                  onClick={cancel}
                  aria-label="Cancel upload"
                  title="Cancel"
                  className="-mt-1 -mr-1 shrink-0 rounded p-0.5 text-foreground/45 transition hover:bg-foreground/15 hover:text-foreground/90"
                >
                  <X className="h-3 w-3" />
                </button>
              </div>
              <div className="mt-0.5 flex flex-1 flex-col justify-end">
                <span className="line-clamp-2 break-all text-[10px] leading-[1.15]">{pending}</span>
                <span className="mt-0.5 text-[9px] text-foreground/45">Reading…</span>
              </div>
            </div>
          )}
          {sources.map((source) => {
            const empty = source.chunks === 0;
            return (
              // Fixed square tile (h == w); the strip scrolls horizontally once
              // tiles overflow rather than wrapping and growing taller.
              <div
                key={source.label}
                title={source.label}
                className={cn(
                  "flex h-[58px] w-[58px] shrink-0 flex-col overflow-hidden rounded-md border p-1.5",
                  empty
                    ? "border-amber-500/40 bg-amber-500/10 text-amber-300"
                    : "border-accent/30 bg-accent/10 text-foreground/80",
                )}
              >
                <div className="flex items-start justify-between">
                  {empty ? (
                    <TriangleAlert className="h-3.5 w-3.5 shrink-0 text-amber-400" />
                  ) : (
                    <Check className="h-3.5 w-3.5 shrink-0 text-accent" />
                  )}
                  <button
                    type="button"
                    onClick={() => removeSource(source.label)}
                    aria-label={`Remove ${source.label}`}
                    className="-mt-1 -mr-1 shrink-0 rounded p-0.5 text-foreground/45 transition hover:bg-foreground/15 hover:text-foreground/90"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </div>
                <button
                  type="button"
                  onClick={() => source.previewUrl && setPreview(source)}
                  disabled={source.previewUrl === null}
                  title={source.previewUrl ? "Preview" : undefined}
                  className={cn(
                    "mt-0.5 flex flex-1 flex-col justify-end text-left",
                    source.previewUrl && "cursor-pointer",
                  )}
                >
                  <span className="line-clamp-2 break-all text-[10px] leading-[1.15]">
                    {source.label}
                  </span>
                  <span className="mt-0.5 flex items-center gap-0.5 truncate text-[9px] text-foreground/50">
                    {source.previewUrl && <Eye className="h-2.5 w-2.5 shrink-0" />}
                    {empty ? "no text" : `${source.chunks} chunks`}
                  </span>
                </button>
              </div>
            );
          })}
          {error !== null && (
            <button
              type="button"
              onClick={clearError}
              className="inline-flex shrink-0 items-center gap-1.5 self-center rounded-none border border-red-500/30 bg-red-500/10 px-3 py-1.5 text-[13px] text-red-500 transition hover:bg-red-500/20"
              title="Dismiss"
            >
              {error}
              <X className="h-3.5 w-3.5" />
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
          onPaste={onPaste}
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
              disabled={status === "loading"}
              aria-label="Add a source"
              aria-expanded={menuOpen}
              className={cn(
                "flex h-8 w-8 items-center justify-center rounded-full border transition disabled:cursor-default",
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
                <div className="absolute bottom-full left-0 z-40 mb-2 w-52 overflow-hidden rounded-xl border border-foreground/20 bg-surface shadow-[0_12px_40px_-12px_rgba(0,0,0,0.8)]">
                  <div className="flex items-center justify-between border-b border-foreground/10 px-3.5 py-2 font-mono text-[10px] uppercase tracking-widest text-foreground/45">
                    <span>Documents</span>
                    <span className={cn(atLimit && "text-amber-400")}>
                      {sources.length} / {MAX_SOURCES}
                    </span>
                  </div>
                  <MenuItem
                    icon={<Paperclip className="h-4 w-4" />}
                    label="Attach a file"
                    disabled={atLimit}
                    onClick={() => {
                      setMenuOpen(false);
                      fileRef.current?.click();
                    }}
                  />
                  <MenuItem
                    icon={<Link2 className="h-4 w-4" />}
                    label="Ingest a URL"
                    disabled={atLimit}
                    onClick={() => {
                      setMenuOpen(false);
                      setShowUrl(true);
                    }}
                  />
                  {atLimit && (
                    <p className="border-t border-foreground/10 px-3.5 py-2 text-[11px] leading-snug text-amber-400/90">
                      Limit reached — remove a document to add another.
                    </p>
                  )}
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
                ? "border-accent/70 bg-foreground/[0.09]"
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

      {preview?.previewUrl &&
        createPortal(
          <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 sm:p-6">
            <button
              type="button"
              aria-label="Close preview"
              onClick={() => setPreview(null)}
              className="absolute inset-0 bg-black/70 backdrop-blur-sm"
            />
            <div className="relative flex h-[92vh] w-full max-w-4xl flex-col overflow-hidden rounded-lg border border-foreground/20 bg-surface shadow-[0_20px_60px_-20px_rgba(0,0,0,0.8)]">
              <div className="flex items-center justify-between gap-3 border-b border-foreground/15 px-4 py-2.5">
                <span className="truncate font-mono text-[11px] uppercase tracking-widest text-foreground/65">
                  {preview.label}
                </span>
                <button
                  type="button"
                  onClick={() => setPreview(null)}
                  aria-label="Close preview"
                  className="rounded p-1 text-foreground/55 transition hover:bg-foreground/10 hover:text-foreground/90"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
              <iframe src={preview.previewUrl} title={preview.label} className="flex-1 bg-white" />
            </div>
          </div>,
          document.body,
        )}
    </div>
  );
}

function MenuItem({
  icon,
  label,
  onClick,
  disabled = false,
}: {
  icon: ReactNode;
  label: string;
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="flex w-full items-center gap-3 px-3.5 py-2.5 text-left text-sm text-foreground/80 transition hover:bg-foreground/[0.06] hover:text-foreground disabled:cursor-default disabled:opacity-40 disabled:hover:bg-transparent disabled:hover:text-foreground/80"
    >
      <span className="text-foreground/55">{icon}</span>
      {label}
    </button>
  );
}
