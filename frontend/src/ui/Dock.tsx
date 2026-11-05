/* The dock.
 *
 * The cover has a field you can type a ticker into, and then it leaves the
 * screen and the reader spends ten thousand pixels reading about a thing they
 * can no longer do. The dock is that field, following them down.
 *
 * It arrives once the cover is gone and stands down inside the closing band,
 * which has its own field and does not need two. It is a button until you
 * reach for it, then it is the field: idle, it is one object in the corner
 * rather than a form parked over the page.
 */

import { useEffect, useRef, useState } from "react";

import { gsap, prefersReduced } from "../lib/scroll";
import { onScroll } from "../lib/motion";
import { useMagnetic } from "../lib/fx";

export default function Dock({ go }: { go: (v: "home" | "score", ticker?: string) => void }) {
  const root = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const btn = useMagnetic<HTMLButtonElement>(0.3);
  const [shown, setShown] = useState(false);
  const [open, setOpen] = useState(false);
  const [v, setV] = useState("");

  useEffect(() => onScroll(({ y, h, dh }) => {
    // Past the cover, and not once the closing band is on screen: that band
    // asks the same question with more room to ask it in.
    const closer = document.querySelector(".closer");
    const closerUp = closer ? closer.getBoundingClientRect().top < h * 0.85 : y > dh - h * 1.6;
    setShown(y > h * 0.9 && !closerUp);
  }), []);

  useEffect(() => {
    const el = root.current;
    if (!el) return;
    if (prefersReduced()) { gsap.set(el, { y: 0, opacity: shown ? 1 : 0, pointerEvents: shown ? "auto" : "none" }); return; }
    const tween = gsap.to(el, {
      y: shown ? 0 : 90,
      opacity: shown ? 1 : 0,
      duration: 0.55,
      ease: shown ? "back.out(1.6)" : "power2.in",
      pointerEvents: shown ? "auto" : "none",
    });
    return () => { tween.kill(); };
  }, [shown]);

  useEffect(() => { if (open) input.current?.focus(); }, [open]);
  useEffect(() => { if (!shown) setOpen(false); }, [shown]);

  const send = () => {
    const t = v.trim().toUpperCase();
    if (t) go("score", t);
  };

  return (
    <div className={`dock${open ? " is-open" : ""}`} ref={root}>
      <form
        className="dock-in"
        onSubmit={(e) => { e.preventDefault(); open ? send() : setOpen(true); }}
      >
        <label className="dock-f">
          <span className="dock-k">Ticker</span>
          <input
            ref={input}
            value={v}
            onChange={(e) => setV(e.target.value.toUpperCase())}
            onBlur={() => { if (!v.trim()) setOpen(false); }}
            onKeyDown={(e) => { if (e.key === "Escape") setOpen(false); }}
            placeholder="AVUS"
            spellCheck={false}
            autoComplete="off"
            maxLength={24}
            aria-label="Ticker to score"
            tabIndex={open ? 0 : -1}
          />
        </label>
        <button className="dock-go" type="submit" ref={btn} data-cursor="score it">
          <span>{open ? "Score it" : "Score a ticker"}</span>
          <svg viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true">
            <path d="M2.5 9h12M10 4l5 5-5 5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
      </form>
    </div>
  );
}
