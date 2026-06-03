"use client";

import { motion } from "framer-motion";
import type { CSSProperties } from "react";

import { cn } from "@/shared/lib/cn";

// Text Shimmer (adapted from motion-primitives) — a single bright band glides
// left → right across muted text on a continuous loop, the canonical "thinking /
// generating" shimmer. The base text sits at a dimmed color; a transparent-
// except-the-centre gradient overlays a bright band whose width scales with the
// text length, and framer-motion sweeps its background-position. The clip comes
// from Tailwind's bg-clip-text/text-transparent (Lightning CSS strips raw
// background-clip:text but emits these correctly); the gradients are inline so
// they pass through untouched.
export function TextShimmer({
  children,
  className,
  duration = 2,
  spread = 2,
}: {
  children: string;
  className?: string;
  duration?: number;
  spread?: number;
}) {
  const dynamicSpread = children.length * spread;
  return (
    <motion.span
      className={cn("inline-block bg-clip-text text-transparent", className)}
      initial={{ backgroundPosition: "100% center" }}
      animate={{ backgroundPosition: "0% center" }}
      transition={{ repeat: Number.POSITIVE_INFINITY, duration, ease: "linear" }}
      style={
        {
          "--spread": `${dynamicSpread}px`,
          "--base-color": "color-mix(in oklab, var(--foreground) 42%, transparent)",
          "--shimmer-color": "var(--foreground)",
          backgroundImage:
            "linear-gradient(90deg, transparent calc(50% - var(--spread)), var(--shimmer-color), transparent calc(50% + var(--spread))), linear-gradient(var(--base-color), var(--base-color))",
          backgroundSize: "250% 100%, auto",
          backgroundRepeat: "no-repeat",
        } as CSSProperties
      }
    >
      {children}
    </motion.span>
  );
}
