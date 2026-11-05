/* The pointer, as a solid disc.
 *
 * This replaces the native cursor rather than trailing it. The disc is the
 * cursor: it grows over anything pressable, grows further and carries a word
 * when the element has one to say, shrinks under the press, and gets out of the
 * way entirely over a text field where the caret has to be visible.
 *
 * It reads its colour from the band underneath, so the disc is gold on paper
 * and cream on ink and never disappears into the page.
 *
 * Driven by gsap.quickTo rather than by React state: this moves every frame and
 * routing that through a render is how a cursor ends up lagging the hand.
 */

import { useEffect, useRef } from "react";

import { finePointer, gsap, prefersReduced } from "../lib/scroll";

const PRESSABLE =
  'a, button, input, select, textarea, label, summary, [role="button"], [data-cursor]';

export default function Cursor() {
  const root = useRef<HTMLDivElement>(null);
  const label = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    const el = root.current;
    const say = label.current;
    if (!el || !say) return;
    if (!finePointer() || prefersReduced()) return;

    // Only hide the native cursor once we know we can draw a replacement.
    document.documentElement.classList.add("has-cursor");

    const xTo = gsap.quickTo(el, "x", { duration: 0.42, ease: "expo.out" });
    const yTo = gsap.quickTo(el, "y", { duration: 0.42, ease: "expo.out" });

    let raf = 0;
    // The latest event, so the frame's hit test reads where the pointer is now
    // rather than where it was when the frame was scheduled.
    let last: PointerEvent | null = null;

    const move = (e: PointerEvent) => {
      xTo(e.clientX);
      yTo(e.clientY);
      last = e;
      // A page can load with the pointer already inside it, in which case
      // pointerenter never fires and the disc would stay hidden for good. The
      // first movement is the reliable signal that there is a pointer here.
      el.classList.remove("is-out");
      if (raf) return;
      // Hit testing is the expensive half, so it runs once a frame rather than
      // once an event.
      raf = requestAnimationFrame(() => {
        raf = 0;
        const t = last?.target as Element | null;
        const hit = t?.closest?.(PRESSABLE) as HTMLElement | null;
        const word = hit?.dataset?.cursor;
        const typing = t?.closest?.("input, textarea, select, [data-cursor-hide]");

        el.classList.toggle("is-live", Boolean(hit) && !typing);
        el.classList.toggle("is-word", Boolean(word) && !typing);
        el.classList.toggle("is-hidden", Boolean(typing));
        if (word && say.textContent !== word) say.textContent = word;

        // Which field it is standing on decides what colour it has to be.
        const band = t?.closest?.(".band-ink, .band-gold, .band-rose, .boot") as HTMLElement | null;
        const tone = band?.classList.contains("band-ink") ? "ink"
          : band?.classList.contains("band-gold") ? "gold"
          : band?.classList.contains("band-rose") ? "rose"
          : band?.classList.contains("boot") ? "ink" : "";
        el.dataset.on = tone;
      });
    };

    const down = () => el.classList.add("is-down");
    const up = () => el.classList.remove("is-down");
    const enter = () => el.classList.remove("is-out");
    const leave = () => el.classList.add("is-out");

    window.addEventListener("pointermove", move, { passive: true });
    window.addEventListener("pointerdown", down, { passive: true });
    window.addEventListener("pointerup", up, { passive: true });
    document.addEventListener("pointerenter", enter);
    document.addEventListener("pointerleave", leave);

    return () => {
      document.documentElement.classList.remove("has-cursor");
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerdown", down);
      window.removeEventListener("pointerup", up);
      document.removeEventListener("pointerenter", enter);
      document.removeEventListener("pointerleave", leave);
      cancelAnimationFrame(raf);
      gsap.killTweensOf(el);
    };
  }, []);

  return (
    <div className="cursor is-out" ref={root} aria-hidden="true">
      <span className="cursor-disc">
        <span className="cursor-label" ref={label} />
      </span>
    </div>
  );
}
