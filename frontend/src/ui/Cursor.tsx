/* The pointer's shadow.
 *
 * The real cursor is never hidden: hiding it costs a reader their one reliable
 * landmark and buys a gimmick. What this adds is the ink the pointer would
 * leave if it were a pen. A gold blot lags a few frames behind the tip, it
 * opens into a drawn ring over anything you can actually press, and it drops a
 * short trail of drying dots when you move fast.
 *
 * One rAF loop, two transforms, nothing routed through React state per frame.
 */

import { useEffect, useRef, useState } from "react";
import { inkCircle } from "../lib/draw";
import { coarse, lerp, reduced } from "../lib/motion";

const LIVE = "a, button, input, select, textarea, summary, [role='button'], [data-cursor]";

export default function Cursor() {
  const blot = useRef<HTMLDivElement>(null);
  const trail = useRef<HTMLDivElement>(null);
  const say = useRef<HTMLSpanElement>(null);
  const [on, setOn] = useState(false);

  // Deciding whether to draw and wiring the loop are two passes on purpose:
  // the nodes below only exist once this says yes, so a single effect would
  // read null refs and quietly give up.
  useEffect(() => {
    if (coarse()) return;
    if (!window.matchMedia("(pointer: fine)").matches) return;
    setOn(true);
  }, []);

  useEffect(() => {
    if (!on) return;

    const b = blot.current;
    const t = trail.current;
    const s = say.current;
    if (!b || !t || !s) return;

    // Asking for less motion removes the spring lag and the drying ink, which
    // are decoration. The ring and the label stay: they report what is under
    // the pointer, which is a state change, not an ornament.
    const calm = reduced();
    b.dataset.calm = calm ? "true" : "false";

    const to = { x: innerWidth / 2, y: innerHeight / 2 };
    const at = { ...to };
    let raf = 0;
    let seen = false;
    let lastDrop = 0;
    let ink = 0;
    //: The control under the pointer, when it is small enough that being drawn
    //  toward its middle reads as attraction rather than as the cursor refusing
    //  to go where it was put. A text field or a whole card is left alone.
    let magnet: DOMRect | null = null;
    const PULL = 0.3;

    const move = (e: PointerEvent) => {
      to.x = e.clientX;
      to.y = e.clientY;
      if (!seen) { seen = true; at.x = to.x; at.y = to.y; b.dataset.seen = "true"; }

      const el = (e.target as Element | null)?.closest?.(LIVE) as HTMLElement | null;
      const label = el?.dataset?.cursor;
      const word = label && label !== "true" ? label : "";
      b.dataset.live = el ? "true" : "false";
      b.dataset.say = word ? "true" : "false";
      if (s.textContent !== word) s.textContent = word;

      // A control can declare the colour it answers in, so the ring over a red
      // verdict is not the same ring as the one over a gold button.
      const tone = el?.dataset?.cursorTone ?? "";
      if (b.dataset.tone !== tone) b.dataset.tone = tone;

      magnet = null;
      if (el && !calm) {
        const r = el.getBoundingClientRect();
        const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName);
        if (!typing && r.width < 340 && r.height < 170) magnet = r;
      }
    };

    const down = (e: PointerEvent) => {
      b.dataset.down = "true";
      if (calm) return;
      const ring = document.createElement("i");
      ring.className = "cur-press";
      ring.style.left = `${e.clientX}px`;
      ring.style.top = `${e.clientY}px`;
      t.appendChild(ring);
      setTimeout(() => ring.remove(), 520);
    };
    const up = () => { b.dataset.down = "false"; };

    const tick = (now: number) => {
      raf = requestAnimationFrame(tick);
      const px = at.x;
      const py = at.y;
      let tx = to.x;
      let ty = to.y;
      if (magnet) {
        tx = to.x + (magnet.left + magnet.width / 2 - to.x) * PULL;
        ty = to.y + (magnet.top + magnet.height / 2 - to.y) * PULL;
      }
      const k = calm ? 1 : 0.19;
      at.x = lerp(at.x, tx, k);
      at.y = lerp(at.y, ty, k);
      b.style.transform = `translate3d(${at.x.toFixed(1)}px, ${at.y.toFixed(1)}px, 0)`;

      // A pen only leaves a mark when it is moving. Below walking pace the
      // trail stops, so a resting pointer does not quietly litter the page.
      const speed = Math.hypot(at.x - px, at.y - py);
      if (!calm && speed > 7 && now - lastDrop > 46 && ink < 14) {
        lastDrop = now;
        ink++;
        const dot = document.createElement("i");
        dot.className = "cur-drop";
        dot.style.left = `${px.toFixed(0)}px`;
        dot.style.top = `${py.toFixed(0)}px`;
        dot.style.setProperty("--s", (0.5 + Math.min(1, speed / 34) * 0.9).toFixed(2));
        t.appendChild(dot);
        setTimeout(() => { dot.remove(); ink--; }, 620);
      }
    };

    window.addEventListener("pointermove", move, { passive: true });
    window.addEventListener("pointerdown", down, { passive: true });
    window.addEventListener("pointerup", up, { passive: true });
    raf = requestAnimationFrame(tick);

    return () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerdown", down);
      window.removeEventListener("pointerup", up);
      cancelAnimationFrame(raf);
    };
  }, [on]);

  if (!on) return null;

  return (
    <>
      <div className="cur-trail" ref={trail} aria-hidden="true" />
      <div className="cur" ref={blot} aria-hidden="true">
        <span className="cur-dot" />
        <svg className="cur-ring" viewBox="-40 -40 80 80">
          <path d={inkCircle(0, 0, 32, 23, 0.05)} fill="none" stroke="var(--ink)"
                strokeWidth="2" strokeLinecap="round" />
        </svg>
        <span className="cur-say" ref={say} />
      </div>
    </>
  );
}
