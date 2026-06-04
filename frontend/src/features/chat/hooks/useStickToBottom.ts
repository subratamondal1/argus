"use client";

import { type RefObject, useEffect, useRef } from "react";

// RAF-eased auto-scroll that keeps streaming content in view. Each frame glides
// 25% of the remaining distance toward the bottom, so the synthesizer's output
// stays pinned as it prints.
//
// Following disengages ONLY on a real user gesture — a wheel-up or a finger
// dragging the content down to read earlier text — and re-engages once the view
// is back near the bottom. This is deliberate: on mobile, the browser's address
// bar showing/hiding (and content reflowing as tokens land) fires `scroll`
// events whose scrollTop no longer matches what we set. The old heuristic read
// those as the user scrolling and latched following OFF, freezing the view while
// the answer kept generating below the fold. Gestures don't fire on resize or on
// our own scroll, so keying off them is robust.
//
// `turnCount` re-engages following whenever a new turn is appended. Combined with
// the per-turn cushion (the last streaming turn is sized to one viewport), the
// new question glides to the TOP of the view — its content then fills in below.
export function useStickToBottom(turnCount: number): RefObject<HTMLDivElement | null> {
  const ref = useRef<HTMLDivElement>(null);
  const follow = useRef(true);
  const touching = useRef(false);
  const touchStartY = useRef(0);
  const lastTop = useRef(0);
  const lastHeight = useRef(0);
  const prevCount = useRef(turnCount);

  useEffect(() => {
    if (turnCount > prevCount.current) follow.current = true;
    prevCount.current = turnCount;
  }, [turnCount]);

  useEffect(() => {
    const element = ref.current;
    if (element === null) return;

    const nearBottom = (): boolean =>
      element.scrollHeight - element.scrollTop - element.clientHeight < 24;

    const onWheel = (event: WheelEvent): void => {
      if (event.deltaY < 0) follow.current = false;
    };
    const onTouchStart = (event: TouchEvent): void => {
      touching.current = true;
      touchStartY.current = event.touches[0]?.clientY ?? 0;
    };
    const onTouchMove = (event: TouchEvent): void => {
      // Finger moving DOWN drags the content down — i.e. the user is scrolling UP
      // to read earlier output. Stop chasing the bottom.
      const y: number = event.touches[0]?.clientY ?? 0;
      if (y - touchStartY.current > 10) follow.current = false;
    };
    const onTouchEnd = (): void => {
      touching.current = false;
      if (nearBottom()) follow.current = true;
    };
    const onScroll = (): void => {
      // A clientHeight change means the mobile address bar (not the user) drove
      // this scroll — never disengage on it.
      const resized: boolean = element.clientHeight !== lastHeight.current;
      lastHeight.current = element.clientHeight;
      if (!touching.current) {
        if (nearBottom()) follow.current = true;
        else if (!resized && element.scrollTop < lastTop.current - 4) follow.current = false;
      }
      lastTop.current = element.scrollTop;
    };

    element.addEventListener("wheel", onWheel, { passive: true });
    element.addEventListener("touchstart", onTouchStart, { passive: true });
    element.addEventListener("touchmove", onTouchMove, { passive: true });
    element.addEventListener("touchend", onTouchEnd, { passive: true });
    element.addEventListener("scroll", onScroll, { passive: true });

    let frame = 0;
    const tick = (): void => {
      const current = ref.current;
      if (current !== null && follow.current && !touching.current) {
        const target: number = current.scrollHeight - current.clientHeight;
        if (target - current.scrollTop > 1) {
          current.scrollTop = current.scrollTop + (target - current.scrollTop) * 0.25;
        }
        lastTop.current = current.scrollTop;
      }
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);

    return () => {
      element.removeEventListener("wheel", onWheel);
      element.removeEventListener("touchstart", onTouchStart);
      element.removeEventListener("touchmove", onTouchMove);
      element.removeEventListener("touchend", onTouchEnd);
      element.removeEventListener("scroll", onScroll);
      cancelAnimationFrame(frame);
    };
  }, []);

  return ref;
}
