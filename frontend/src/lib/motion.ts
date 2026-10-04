/* Motion plumbing.
 *
 * One rAF loop reads the scroll position for the whole page and hands it to
 * everything that cares. Components never attach their own scroll listener,
 * because thirty listeners each calling getBoundingClientRect is how a page
 * that looks alive ends up feeling slow.
 */

import { useEffect, useRef, useState } from "react";

export const reduced = () =>
  typeof window !== "undefined" &&
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

export const coarse = () =>
  typeof window !== "undefined" && window.matchMedia("(pointer: coarse)").matches;

export const clamp = (v: number, a = 0, b = 1) => (v < a ? a : v > b ? b : v);
export const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
export const easeOut = (t: number) => 1 - Math.pow(1 - t, 3);

/* --- the shared scroll clock ---------------------------------------------- */

type Frame = { y: number; vy: number; h: number; dh: number };
type Sub = (f: Frame) => void;

const subs = new Set<Sub>();
const frame: Frame = { y: 0, vy: 0, h: 0, dh: 0 };
let running = false;

function loop() {
  const y = window.scrollY;
  const raw = y - frame.y;
  frame.vy = lerp(frame.vy, raw, 0.22);
  frame.y = y;
  frame.h = window.innerHeight;
  frame.dh = document.documentElement.scrollHeight;
  for (const s of subs) s(frame);
  if (running) requestAnimationFrame(loop);
}

function subscribe(fn: Sub) {
  subs.add(fn);
  if (!running) {
    running = true;
    frame.y = window.scrollY;
    requestAnimationFrame(loop);
  }
  fn(frame);
  return () => {
    subs.delete(fn);
    if (subs.size === 0) running = false;
  };
}

/** Raw access for anything that wants to drive a node directly. */
export function onScroll(fn: Sub) {
  return subscribe(fn);
}

/* --- reveal ---------------------------------------------------------------- */

/**
 * Marks an element as entered, once. Each piece decides for itself what
 * entering looks like: a uniform fade applied to every section in a document
 * is the tell that nobody chose anything.
 */
export function useEnter<T extends HTMLElement | SVGElement>(threshold = 0.16) {
  const ref = useRef<T>(null);
  const [inView, setInView] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (reduced()) {
      el.dataset.in = "true";
      setInView(true);
      return;
    }
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (!e.isIntersecting) continue;
          el.dataset.in = "true";
          setInView(true);
          io.disconnect();
        }
      },
      { threshold, rootMargin: "0px 0px -6% 0px" },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [threshold]);

  return { ref, inView };
}

/* --- scroll scrubbing ------------------------------------------------------ */

/**
 * Writes a scroll-driven transform straight onto a node. Used for anything
 * that moves every frame, where routing sixty updates a second through React
 * state would cost more than the effect is worth.
 */
export function useDrift<T extends HTMLElement | SVGElement>(
  speed: number,
  opts: { rotate?: number; scale?: number } = {},
) {
  const ref = useRef<T>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el || reduced() || coarse()) return;
    return subscribe(({ y, h }) => {
      const r = el.getBoundingClientRect();
      const mid = r.top + r.height / 2;
      const off = (mid - h / 2) / h;
      const ty = off * speed * -100;
      const rot = opts.rotate ? off * opts.rotate : 0;
      const sc = opts.scale ? 1 + off * opts.scale : 1;
      el.style.setProperty("--dy", `${ty.toFixed(2)}px`);
      el.style.setProperty("--dr", `${rot.toFixed(3)}deg`);
      el.style.setProperty("--ds", sc.toFixed(4));
      void y;
    });
  }, [speed, opts.rotate, opts.scale]);
  return ref;
}

/** Scroll speed, smoothed, for the things that should feel the page moving. */
export function useVelocity() {
  const [v, setV] = useState(0);
  useEffect(() => {
    if (reduced()) return;
    let last = 0;
    return subscribe(({ vy }) => {
      const n = clamp(Math.abs(vy) / 60, 0, 1) * Math.sign(vy || 1);
      if (Math.abs(n - last) < 0.01) return;
      last = n;
      setV(n);
    });
  }, []);
  return v;
}

/* --- pointer --------------------------------------------------------------- */

/** Pointer position relative to an element's centre, in the range -1 to 1. */
export function useTilt<T extends HTMLElement | SVGElement>(strength = 1) {
  const ref = useRef<T>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el || reduced() || coarse()) return;
    let raf = 0;
    const target = { x: 0, y: 0 };
    const cur = { x: 0, y: 0 };

    const move = (e: PointerEvent) => {
      const r = el.getBoundingClientRect();
      target.x = clamp((e.clientX - (r.left + r.width / 2)) / (r.width / 2), -1, 1);
      target.y = clamp((e.clientY - (r.top + r.height / 2)) / (r.height / 2), -1, 1);
    };
    const tick = () => {
      raf = requestAnimationFrame(tick);
      cur.x = lerp(cur.x, target.x, 0.08);
      cur.y = lerp(cur.y, target.y, 0.08);
      el.style.setProperty("--px", (cur.x * strength).toFixed(3));
      el.style.setProperty("--py", (cur.y * strength).toFixed(3));
    };
    window.addEventListener("pointermove", move, { passive: true });
    tick();
    return () => {
      window.removeEventListener("pointermove", move);
      cancelAnimationFrame(raf);
    };
  }, [strength]);
  return ref;
}

/* --- counting -------------------------------------------------------------- */

/** A figure arriving. Runs once, when it is on screen, then holds. */
export function useTally(target: number, ms = 1000, start = true) {
  const [v, setV] = useState(start ? 0 : target);
  const from = useRef(0);

  useEffect(() => {
    if (!start) return;
    if (reduced()) {
      setV(target);
      return;
    }
    const a = from.current;
    const t0 = performance.now();
    let raf = 0;
    const step = (t: number) => {
      const k = clamp((t - t0) / ms);
      const nv = a + (target - a) * easeOut(k);
      from.current = nv;
      setV(nv);
      if (k < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [target, ms, start]);

  return v;
}

/**
 * One observer for every entrance on the page.
 *
 * Elements opt in by carrying a data-anim, wherever they are in the tree, and
 * this marks them when they arrive. Mounted once at the root: the alternative
 * is a ref and an observer per element, which is a lot of machinery for the
 * same effect and quietly leaks observers every time a view changes.
 */
export function useRevealAll() {
  useEffect(() => {
    const mark = (el: Element) => { (el as HTMLElement).dataset.in = "true"; };

    if (reduced()) {
      document.querySelectorAll("[data-anim]").forEach(mark);
      return;
    }

    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (!e.isIntersecting) continue;
          mark(e.target);
          io.unobserve(e.target);
        }
      },
      { threshold: 0.08, rootMargin: "0px 0px -4% 0px" },
    );

    let queued = 0;
    const scan = () => {
      queued = 0;
      document.querySelectorAll("[data-anim]:not([data-in])").forEach((el) => io.observe(el));
    };
    const schedule = () => { if (!queued) queued = requestAnimationFrame(scan); };

    scan();
    const mo = new MutationObserver(schedule);
    mo.observe(document.body, { childList: true, subtree: true });

    return () => {
      cancelAnimationFrame(queued);
      mo.disconnect();
      io.disconnect();
    };
  }, []);
}
