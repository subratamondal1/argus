"use client";

import { type RefObject, useEffect, useRef } from "react";

// RAF-eased auto-scroll. Each frame glides 25% of the remaining distance toward
// the bottom, so streaming content stays in view smoothly. Following pauses when
// the user scrolls up (past an 80px threshold) and re-engages near the bottom.
//
// `turnCount` re-engages following whenever a new turn is appended. Combined
// with the per-turn cushion (the last streaming turn is sized to one viewport),
// the new question glides to the TOP of the view — its content then fills in
// below, just like the first turn — instead of landing at the bottom of a long
// scroll.
export function useStickToBottom(turnCount: number): RefObject<HTMLDivElement | null> {
  const ref = useRef<HTMLDivElement>(null);
  const follow = useRef(true);
  // The scrollTop we last set ourselves. A scroll event that lands away from it
  // is the USER scrolling; one that matches it is our own RAF (or content
  // growing under a pinned view) and must NOT disengage following — that was the
  // bug where streaming output scrolled out of sight whenever a chunk landed.
  const lastTop = useRef(-1);
  const prevCount = useRef(turnCount);

  useEffect(() => {
    if (turnCount > prevCount.current) follow.current = true;
    prevCount.current = turnCount;
  }, [turnCount]);

  useEffect(() => {
    const element = ref.current;
    if (element === null) return;

    const onScroll = (): void => {
      if (lastTop.current >= 0 && Math.abs(element.scrollTop - lastTop.current) <= 2) return;
      const distance = element.scrollHeight - element.scrollTop - element.clientHeight;
      follow.current = distance < 120;
    };
    element.addEventListener("scroll", onScroll, { passive: true });

    let frame = 0;
    const tick = (): void => {
      const current = ref.current;
      if (current !== null && follow.current) {
        const target = current.scrollHeight - current.clientHeight;
        if (target - current.scrollTop > 1) {
          current.scrollTop = current.scrollTop + (target - current.scrollTop) * 0.25;
        }
        lastTop.current = current.scrollTop;
      }
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);

    return () => {
      element.removeEventListener("scroll", onScroll);
      cancelAnimationFrame(frame);
    };
  }, []);

  return ref;
}
