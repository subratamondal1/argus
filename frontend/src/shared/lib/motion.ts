import type { Variants } from "framer-motion";

// The Vercel "editorial" easing — sharp deceleration, no spring overshoot.
export const editorialEase: [number, number, number, number] = [0.16, 1, 0.3, 1];

export const fadeUp: Variants = {
  hidden: { opacity: 0, y: 8 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: editorialEase } },
};
