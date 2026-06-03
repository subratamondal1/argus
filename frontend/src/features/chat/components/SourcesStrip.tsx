"use client";

import { motion } from "framer-motion";
import { useEffect, useRef } from "react";

import { cn } from "@/shared/lib/cn";
import { editorialEase } from "@/shared/lib/motion";

import { sourceLabel, sourceMeta } from "../lib/source";
import type { Source } from "../types";

// Horizontal scrolling sources strip — a card per retrieval, numbered to match
// the inline [N] citations in the answer. Bidirectional highlight: hovering a
// card lights the matching citation below, and hovering a citation lights the
// matching card here and smooth-scrolls it into view. Shares the editorial
// panel chrome with the steps + answer panels.
export function SourcesStrip({
  sources,
  highlighted,
  onEnter,
  onLeave,
}: {
  sources: Source[];
  highlighted: number | null;
  onEnter: (id: number) => void;
  onLeave: () => void;
}) {
  const cardRefs = useRef<Map<number, HTMLAnchorElement>>(new Map());

  useEffect(() => {
    if (highlighted === null) return;
    const el = cardRefs.current.get(highlighted);
    if (el === undefined) return;
    el.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "center" });
  }, [highlighted]);

  if (sources.length === 0) return null;

  return (
    <section className="mb-5 overflow-hidden rounded-sm border border-foreground/20 bg-surface">
      <header className="flex items-center justify-between border-b border-foreground/15 px-4 py-2.5">
        <p className="font-mono text-[10px] uppercase tracking-widest text-foreground/55">Sources</p>
        <p className="font-mono text-[10px] uppercase tracking-widest tabular-nums text-foreground/45">
          {sources.length} retrieved
        </p>
      </header>
      <div className="relative">
        <div className="flex gap-2.5 overflow-x-auto scroll-smooth px-4 py-3.5 [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
          {sources.map((source) => {
            const active = highlighted === source.id;
            return (
              <motion.a
                key={source.id}
                href={source.url}
                target="_blank"
                rel="noreferrer"
                ref={(el) => {
                  if (el) cardRefs.current.set(source.id, el);
                  else cardRefs.current.delete(source.id);
                }}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.35, ease: editorialEase }}
                onMouseEnter={() => onEnter(source.id)}
                onMouseLeave={onLeave}
                onFocus={() => onEnter(source.id)}
                onBlur={onLeave}
                className={cn(
                  "block w-[260px] shrink-0 cursor-pointer rounded-sm border bg-background px-3 py-2.5 no-underline transition-all duration-200 ease-out",
                  active
                    ? "border-accent/70 shadow-[0_0_24px_-6px_rgba(37,99,235,0.55)] dark:shadow-[0_0_30px_-4px_rgba(106,166,255,0.7)]"
                    : "border-foreground/20 hover:border-foreground/40",
                )}
              >
                <div className="mb-1.5 flex items-center justify-between gap-2">
                  <span
                    className={cn(
                      "font-mono text-[10px] tabular-nums transition-colors",
                      active ? "text-accent" : "text-foreground/55",
                    )}
                  >
                    [{source.id}]
                  </span>
                  <span className="font-mono text-[9px] uppercase tracking-widest tabular-nums text-foreground/40">
                    {sourceMeta(source)}
                  </span>
                </div>
                <p className="line-clamp-1 font-mono text-[10px] leading-relaxed text-foreground/60">
                  {sourceLabel(source)}
                </p>
                <p className="mt-1.5 line-clamp-3 font-serif text-[12px] leading-snug text-foreground/85">
                  {source.snippet}
                </p>
              </motion.a>
            );
          })}
        </div>
        <div className="pointer-events-none absolute inset-y-0 right-0 w-12 bg-gradient-to-l from-background to-transparent" />
      </div>
    </section>
  );
}
