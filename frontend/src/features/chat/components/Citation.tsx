"use client";

import { cn } from "@/shared/lib/cn";

import { sourceLabel, sourceMeta } from "../lib/source";
import type { Source } from "../types";

// An inline [N] citation rendered as an accent superscript with a hover
// popover that shows the exact source it points to — number, origin/relevance,
// location, and snippet — plus an "Open source" link. Hovering also drives the
// shared highlight so the matching card in the sources strip lights up in
// lockstep (bidirectional). A CSS-only popover (group-hover visibility) keeps
// it dependency-free; the parent answer panel must not clip overflow.
export function Citation({
  source,
  highlighted,
  onEnter,
  onLeave,
}: {
  source: Source;
  highlighted: boolean;
  onEnter: () => void;
  onLeave: () => void;
}) {
  return (
    <a
      href={source.url}
      target="_blank"
      rel="noreferrer"
      aria-label={`Citation ${source.id} — ${sourceLabel(source)}`}
      className="group relative inline-block align-baseline no-underline"
      onMouseEnter={onEnter}
      onMouseLeave={onLeave}
      onFocus={onEnter}
      onBlur={onLeave}
    >
      <sup
        className={cn(
          "mx-px cursor-pointer select-none rounded-sm px-1 py-0.5 font-mono text-[10px] transition-all",
          highlighted
            ? "bg-accent/20 text-accent [text-shadow:0_0_8px_var(--accent)]"
            : "text-accent/80 hover:text-accent hover:[text-shadow:0_0_6px_var(--accent)]",
        )}
      >
        [{source.id}]
      </sup>
      <span
        role="tooltip"
        className="invisible absolute bottom-full left-1/2 z-50 mb-2 w-72 -translate-x-1/2 rounded-md border border-foreground/20 bg-surface px-3 py-2.5 opacity-0 shadow-[0_8px_24px_-8px_rgba(0,0,0,0.45)] transition-[opacity,visibility] duration-150 ease-out group-hover:visible group-hover:opacity-100"
      >
        <span className="mb-1 flex items-center justify-between gap-2 font-mono text-[9px] uppercase tracking-widest text-foreground/55">
          <span className="text-accent">[{source.id}]</span>
          <span className="tabular-nums">{sourceMeta(source)}</span>
        </span>
        <span className="block truncate font-mono text-[10px] leading-relaxed text-foreground/65">
          {sourceLabel(source)}
        </span>
        <span className="mt-1.5 block font-serif text-[12px] leading-snug text-foreground/85">
          {source.snippet}
        </span>
        <span className="mt-2 block border-t border-foreground/15 pt-1.5 font-mono text-[9px] uppercase tracking-widest text-accent">
          Open source ↗
        </span>
      </span>
    </a>
  );
}
