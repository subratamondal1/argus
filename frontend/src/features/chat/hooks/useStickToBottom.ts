"use client";

import { type RefObject, useEffect, useRef } from "react";

// RAF-eased auto-scroll-to-bottom: each frame glides 25% of the remaining
// distance toward the bottom, so streaming content stays in view smoothly
// instead of snapping line-by-line. Following pauses when the user scrolls up
// (past a 80px threshold) and re-engages when they return to the bottom.
export function useStickToBottom(): RefObject<HTMLDivElement | null> {
  const ref = useRef<HTMLDivElement>(null);
  const follow = useRef(true);

  useEffect(() => {
    const element = ref.current;
    if (element === null) return;

    const onScroll = (): void => {
      const distance = element.scrollHeight - element.scrollTop - element.clientHeight;
      follow.current = distance < 80;
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
