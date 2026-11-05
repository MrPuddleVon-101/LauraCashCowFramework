/* The motion vocabulary, in one place so it stays consistent.
 *
 * Every helper here is a no-op under prefers-reduced-motion and returns a
 * teardown, because a page that leaks ScrollTriggers across a view change
 * degrades quietly until the scroll stops tracking anything.
 */

import { useEffect, useRef } from "react";

import { ScrollTrigger, gsap, finePointer, prefersReduced } from "./scroll";

/** Pull toward the pointer. For anything that wants to be pressed. */
export function useMagnetic<T extends HTMLElement>(strength = 0.32) {
  const ref = useRef<T>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el || prefersReduced() || !finePointer()) return;

    const xTo = gsap.quickTo(el, "x", { duration: 0.8, ease: "expo.out" });
    const yTo = gsap.quickTo(el, "y", { duration: 0.8, ease: "expo.out" });

    const move = (e: PointerEvent) => {
      const r = el.getBoundingClientRect();
      xTo((e.clientX - r.left - r.width / 2) * strength);
      yTo((e.clientY - r.top - r.height / 2) * strength * 1.1);
    };
    const leave = () => { xTo(0); yTo(0); };

    el.addEventListener("pointermove", move);
    el.addEventListener("pointerleave", leave);
    return () => {
      el.removeEventListener("pointermove", move);
      el.removeEventListener("pointerleave", leave);
      gsap.killTweensOf(el);
    };
  }, [strength]);
  return ref;
}

/** Tilt a card in real perspective as the pointer crosses it. */
export function useTilt3D<T extends HTMLElement>(max = 14) {
  const ref = useRef<T>(null);
  useEffect(() => {
    const stage = ref.current;
    const card = stage?.firstElementChild as HTMLElement | null;
    if (!stage || !card || prefersReduced() || !finePointer()) return;

    gsap.set(card, { transformPerspective: 900, transformStyle: "preserve-3d" });
    const rx = gsap.quickTo(card, "rotationX", { duration: 0.7, ease: "expo.out" });
    const ry = gsap.quickTo(card, "rotationY", { duration: 0.7, ease: "expo.out" });
    const zTo = gsap.quickTo(card, "z", { duration: 0.7, ease: "expo.out" });

    const move = (e: PointerEvent) => {
      const r = stage.getBoundingClientRect();
      ry(((e.clientX - r.left) / r.width - 0.5) * max * 2);
      rx(-((e.clientY - r.top) / r.height - 0.5) * max * 1.6);
      zTo(28);
    };
    const leave = () => { rx(0); ry(0); zTo(0); };

    stage.addEventListener("pointermove", move);
    stage.addEventListener("pointerleave", leave);
    return () => {
      stage.removeEventListener("pointermove", move);
      stage.removeEventListener("pointerleave", leave);
      gsap.killTweensOf(card);
    };
  }, [max]);
  return ref;
}

/** Drift at a different rate to the page. Depth, cheaply. */
export function useParallax<T extends HTMLElement>(distance = 120, scale = 1) {
  const ref = useRef<T>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el || prefersReduced()) return;
    const t = gsap.fromTo(el,
      { yPercent: -distance / 12, scale },
      {
        yPercent: distance / 12,
        ease: "none",
        scrollTrigger: { trigger: el, start: "top bottom", end: "bottom top", scrub: 1 },
      },
    );
    return () => { t.scrollTrigger?.kill(); t.kill(); };
  }, [distance, scale]);
  return ref;
}

/** Reveal a block: it rises, unclips and settles once, when it arrives. */
export function useReveal<T extends HTMLElement>(opts: {
  y?: number; delay?: number; stagger?: number; selector?: string; start?: string;
} = {}) {
  const ref = useRef<T>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (prefersReduced()) {
      gsap.set(el.querySelectorAll(opts.selector ?? ":scope > *"), { clearProps: "all" });
      return;
    }
    const targets = opts.selector
      ? el.querySelectorAll(opts.selector)
      : (el.children.length ? el.children : [el]);

    const tween = gsap.from(targets, {
      y: opts.y ?? 42,
      opacity: 0,
      duration: 1.05,
      ease: "expo.out",
      stagger: opts.stagger ?? 0.075,
      delay: opts.delay ?? 0,
      scrollTrigger: { trigger: el, start: opts.start ?? "top 82%", once: true },
    });
    return () => { tween.scrollTrigger?.kill(); tween.kill(); };
  }, [opts.y, opts.delay, opts.stagger, opts.selector, opts.start]);
  return ref;
}

/** A headline that assembles itself, line by line, from under a mask. */
export function useLineReveal<T extends HTMLElement>(delay = 0) {
  const ref = useRef<T>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const lines = el.querySelectorAll<HTMLElement>(".ln span");
    if (!lines.length) return;
    if (prefersReduced()) { gsap.set(lines, { yPercent: 0, opacity: 1 }); return; }

    const tween = gsap.fromTo(lines,
      { yPercent: 118, opacity: 0, rotate: 3 },
      {
        yPercent: 0, opacity: 1, rotate: 0,
        duration: 1.25, ease: "expo.out", stagger: 0.09, delay,
        scrollTrigger: { trigger: el, start: "top 88%", once: true },
      },
    );
    return () => { tween.scrollTrigger?.kill(); tween.kill(); };
  }, [delay]);
  return ref;
}

/** Count a figure up, once, when it lands on screen. */
export function useCountUp<T extends HTMLElement>(
  value: number, dp = 0, prefix = "", suffix = "",
) {
  const ref = useRef<T>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const fmt = (n: number) =>
      `${prefix}${n.toLocaleString("en-US", {
        minimumFractionDigits: dp, maximumFractionDigits: dp,
      })}${suffix}`;

    if (prefersReduced()) { el.textContent = fmt(value); return; }

    const obj = { n: 0 };
    el.textContent = fmt(0);
    const tween = gsap.to(obj, {
      n: value, duration: 1.8, ease: "expo.out",
      onUpdate: () => { el.textContent = fmt(obj.n); },
      scrollTrigger: { trigger: el, start: "top 90%", once: true },
    });
    return () => { tween.scrollTrigger?.kill(); tween.kill(); };
  }, [value, dp, prefix, suffix]);
  return ref;
}

export { ScrollTrigger, gsap };
