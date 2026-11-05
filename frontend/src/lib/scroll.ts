/* One scroll driver for the whole page.
 *
 * Lenis takes the wheel and smooths it, GSAP's ticker drives Lenis, and
 * ScrollTrigger is told to read from Lenis rather than from the native scroll
 * event. Three clocks fighting each other is how a page ends up janky, so
 * there is exactly one and everything else subscribes to it.
 *
 * Lenis scrolls the window for real, so window.scrollY stays honest and the
 * older clock in lib/motion.ts keeps working untouched.
 */

import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import Lenis from "lenis";

gsap.registerPlugin(ScrollTrigger);

let lenis: Lenis | null = null;

export const prefersReduced = () =>
  typeof window !== "undefined" &&
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

export const finePointer = () =>
  typeof window !== "undefined" &&
  window.matchMedia("(hover: hover) and (pointer: fine)").matches;

/** Start smooth scrolling. Safe to call twice; the second call is ignored. */
export function startScroll(): Lenis | null {
  if (lenis) return lenis;
  if (typeof window === "undefined") return null;

  // Asking for less motion means the page scrolls exactly as the OS says it
  // should. Smoothing is the first thing that has to go, not the last.
  if (prefersReduced()) {
    ScrollTrigger.refresh();
    return null;
  }

  lenis = new Lenis({
    duration: 1.05,
    // A long, shallow ease: the page keeps a little weight after the wheel
    // stops without feeling like it is sliding on ice.
    easing: (t: number) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
    smoothWheel: true,
    // Touch devices already have inertial scrolling from the OS, and layering
    // ours on top of theirs feels like lag rather than polish.
    syncTouch: false,
  });

  lenis.on("scroll", ScrollTrigger.update);
  gsap.ticker.add((time) => lenis?.raf(time * 1000));
  gsap.ticker.lagSmoothing(0);

  return lenis;
}

export function stopScroll() {
  lenis?.destroy();
  lenis = null;
}

/** Jump to an element, through Lenis so the easing matches everything else. */
export function scrollTo(target: string | HTMLElement, offset = -80) {
  if (lenis) {
    lenis.scrollTo(target, { offset, duration: 1.2 });
    return;
  }
  const el = typeof target === "string" ? document.querySelector(target) : target;
  el?.scrollIntoView({ behavior: prefersReduced() ? "auto" : "smooth", block: "start" });
}

/** Hold the page still, for the loader and for any open overlay. */
export function lockScroll(locked: boolean) {
  if (lenis) locked ? lenis.stop() : lenis.start();
  document.documentElement.classList.toggle("is-locked", locked);
}

export { gsap, ScrollTrigger };
