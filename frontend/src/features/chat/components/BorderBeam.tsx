"use client";

import type { CSSProperties, ReactNode } from "react";

import { cn } from "@/shared/lib/cn";

// ─────────────────────────────────────────────────────────────────────────────
// BorderBeam — a refined thread of accent light that travels CLOCKWISE around a
// host's EXISTING 1px border + rounded-sm corners to signal "an agent is running".
//
// Technique (the unanimous design-panel winner): a pseudo-element the exact size
// of the host paints a rotating conic-gradient (a single bright accent arc with
// symmetric falloff into transparency). That fill is clipped to a 1px ring by
// stacking two masks and compositing them with `exclude` (the content-box layer
// is subtracted from the border-box layer ⇒ only the 1px padding band survives).
// Rotation is the registered `@property --angle` (see globals.css). ONLY --angle
// changes per frame: no layout, no box-shadow spread, no width/height animation.
// The repaint is confined to the thin masked ring, so ~6 concurrent beams stay
// cheap. `border-radius: inherit` makes the arc ride the host's REAL corners
// (rounded-sm = 4px here), so it is geometrically exact with no hardcoded px.
//
// Color is var(--accent) + color-mix(in oklab, …) ⇒ light (#2563eb) / dark
// (#6aa6ff) adapt with zero JS. prefers-reduced-motion freezes the ring as a
// static soft accent border (CSS @media, no hydration flash).
//
// TWO entry points, same CSS contract (class `argus-border-beam`, `data-beam`,
// `--beam-duration`, `@property --angle`, `@keyframes argus-border-beam`):
//
//   • <BorderBeam>  — WRAPS its child. The host supplies its own 1px border +
//     rounded-sm; BorderBeam adds `relative` and the beam ::before. Use for the
//     Steps Panel.
//
//   • <BorderBeamRing> — a self-contained absolute `inset-0` overlay rendered
//     INSIDE an already-`relative`, bordered, rounded host. No wrapper div, so it
//     never disturbs a parent `layout`/AnimatePresence geometry. Use for each
//     researcher card (a `motion.div` with `layout`).
// ─────────────────────────────────────────────────────────────────────────────

interface BorderBeamProps {
  /** When true, a luminous accent beam travels clockwise around the border. */
  active: boolean;
  /** The element to wrap. It supplies its own 1px border + rounded-sm corners. */
  children: ReactNode;
  /** Seconds for one full clockwise revolution. Lower = faster. Default 4. */
  duration?: number;
  /** Extra classes for the wrapper (it is `relative` + `rounded-sm` by default). */
  className?: string;
}

// Inline `--beam-duration` feeds the keyframe timing in globals.css. Coercing
// through CSSProperties keeps TS strict happy without an `any` cast.
function beamStyle(duration: number): CSSProperties {
  return { "--beam-duration": `${duration}s` } as CSSProperties;
}

export function BorderBeam({ active, children, duration = 4, className }: BorderBeamProps) {
  return (
    <div
      data-beam={active ? "on" : "off"}
      style={beamStyle(duration)}
      className={cn("argus-border-beam relative rounded-sm", className)}
    >
      {children}
    </div>
  );
}

interface BorderBeamRingProps {
  /** When true, the beam travels; when false the overlay is inert (no ::before). */
  active: boolean;
  /** Seconds for one full clockwise revolution. Lower = faster. Default 4. */
  duration?: number;
  /**
   * Extra classes for the overlay. The host MUST be `position: relative` and own
   * its 1px border + rounded-sm. `rounded-[inherit]` makes the ring follow the
   * host's real corners.
   */
  className?: string;
}

// Overlay form: render this as a direct child of an already-relative, bordered,
// rounded host (e.g. a researcher card's motion.div) so the beam never adds a
// wrapper that would break the parent's `layout` projection.
export function BorderBeamRing({ active, duration = 4, className }: BorderBeamRingProps) {
  return (
    <span
      aria-hidden
      data-beam={active ? "on" : "off"}
      style={beamStyle(duration)}
      className={cn(
        "argus-border-beam pointer-events-none absolute inset-0 z-10 rounded-[inherit]",
        className,
      )}
    />
  );
}
