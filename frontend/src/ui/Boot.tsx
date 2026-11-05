/* The bootup.
 *
 * The framework stamps things, so the site stamps itself. The seal lands on
 * ink, a ring is drawn round it by hand, a counter runs to a hundred while the
 * two weights fill to 45 and 55, and then the field is torn off the top of the
 * page in two panels to reveal the paper underneath.
 *
 * It runs on every load: the stamp landing is the best thing the site does and
 * hiding it behind a session flag meant almost nobody saw it twice. Any key or
 * click skips to the tear, and a reader who has asked for less motion never
 * sees it at all.
 */

import { useEffect, useRef } from "react";

import { asset } from "../lib/asset";
import { inkEllipse, tornEdge } from "../lib/draw";
import { gsap, prefersReduced } from "../lib/scroll";

export default function Boot({ onDone }: { onDone?: () => void }) {
  const root = useRef<HTMLDivElement>(null);
  const done = useRef(false);

  useEffect(() => {
    const el = root.current;
    if (!el) return;

    const finish = () => {
      if (done.current) return;
      done.current = true;
      document.documentElement.removeAttribute("data-booting");
      onDone?.();
    };

    if (prefersReduced()) { finish(); return; }
    document.documentElement.setAttribute("data-booting", "");

    const ctx = gsap.context(() => {
      const counter = { n: 0 };
      const readout = el.querySelector<HTMLElement>(".boot-count");

      const tl = gsap.timeline({ onComplete: finish });

      tl
        // The seal arrives the way a rubber stamp does: too big, then flat.
        .fromTo(".boot-seal",
          { scale: 1.65, opacity: 0, rotate: -12 },
          { scale: 1, opacity: 1, rotate: -2, duration: 0.5, ease: "back.out(2.2)" })
        .to(".boot-seal", { scale: 0.97, duration: 0.1, yoyo: true, repeat: 1 }, ">-0.05")
        // The ring is drawn round it, by hand, in one pass.
        .fromTo(".boot-ring path",
          { strokeDashoffset: 900 },
          { strokeDashoffset: 0, duration: 0.75, ease: "power2.inOut" }, "-=0.35")
        // Then the name, word by word.
        .fromTo(".boot-word span",
          { yPercent: 120, opacity: 0 },
          { yPercent: 0, opacity: 1, duration: 0.7, stagger: 0.07, ease: "expo.out" }, "-=0.55")
        // The two weights fill while a counter runs underneath them.
        .fromTo(".boot-bars i",
          { opacity: 0, y: 12 },
          { opacity: 1, y: 0, duration: 0.3, stagger: 0.1, ease: "power2.out" }, "-=0.35")
        .fromTo(".boot-fill",
          { scaleX: 0 },
          { scaleX: 1, duration: 0.8, stagger: 0.12, ease: "power3.inOut" }, "<")
        .to(counter, {
          n: 100, duration: 0.9, ease: "power2.inOut",
          onUpdate: () => { if (readout) readout.textContent = String(Math.round(counter.n)).padStart(3, "0"); },
        }, "<")
        .to(".boot-skip", { opacity: 1, duration: 0.3 }, "<")
        .to({}, { duration: 0.22 })
        // The field tears away in two panels, from the middle outwards.
        .to(".boot-core", { opacity: 0, scale: 0.94, duration: 0.4, ease: "power2.in" })
        .to(".boot-panel-a", { yPercent: -102, duration: 0.85, ease: "expo.inOut" }, "-=0.2")
        .to(".boot-panel-b", { yPercent: 102, duration: 0.85, ease: "expo.inOut" }, "<");

      const skip = () => {
        if (done.current) return;
        // Jump to the tear rather than cutting to black: skipping should land
        // you on the page, not snap you onto it.
        const tear = tl.duration() - 1.1;
        if (tl.time() < tear) tl.seek(tear).play();
      };
      const onKey = (e: KeyboardEvent) => { if (!e.metaKey && !e.ctrlKey) skip(); };
      window.addEventListener("keydown", onKey);
      window.addEventListener("pointerdown", skip);

      return () => {
        window.removeEventListener("keydown", onKey);
        window.removeEventListener("pointerdown", skip);
      };
    }, el);

    return () => {
      ctx.revert();
      document.documentElement.removeAttribute("data-booting");
    };
  }, [onDone]);

  return (
    <div className="boot" ref={root} aria-hidden="true">
      <div className="boot-panel boot-panel-a">
        <svg className="boot-tear boot-tear-a" viewBox="0 0 1200 40" preserveAspectRatio="none">
          <path d={tornEdge(1200, 40, 17)} fill="var(--ink)" />
        </svg>
      </div>
      <div className="boot-panel boot-panel-b">
        <svg className="boot-tear boot-tear-b" viewBox="0 0 1200 40" preserveAspectRatio="none">
          <path d={tornEdge(1200, 40, 29)} fill="var(--ink)" />
        </svg>
      </div>

      <div className="boot-core">
        <span className="boot-seal">
          <img src={asset("brand/lccf-logo.png")} alt="" draggable={false} />
          <svg className="boot-ring" viewBox="0 0 300 300">
            <path d={inkEllipse(150, 150, 138, 136, 9, 0.035)} fill="none"
                  stroke="var(--gold)" strokeWidth="3" strokeLinecap="round" />
          </svg>
        </span>

        <p className="boot-word">
          {["The", "Laura", "Cash Cow", "Framework"].map((w) => (
            <span key={w}>{w}</span>
          ))}
        </p>

        <div className="boot-bars">
          <i><span className="boot-fill" /><b>45</b><em>is it good</em></i>
          <i><span className="boot-fill boot-fill-b" /><b>55</b><em>is it good for her</em></i>
        </div>

        <span className="boot-count num">000</span>
      </div>

      <span className="boot-skip">press anything to skip</span>
    </div>
  );
}
