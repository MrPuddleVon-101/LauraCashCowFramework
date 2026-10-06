/* The bootup.
 *
 * The framework stamps things. So the first thing the site does is stamp
 * itself: the seal lands on ink, a ring is drawn round it by hand, the two
 * weights fill to 45 and 55, and then the whole field is torn off the top of
 * the page to reveal the paper underneath.
 *
 * It runs on every load, because the stamp landing is the best thing the site
 * does and burying it behind a session flag meant almost nobody saw it twice.
 * It is skippable with any key or click, and it does not run at all for a
 * reader who has asked for less motion.
 */

import { useEffect, useRef, useState } from "react";
import { asset } from "../lib/asset";
import { inkEllipse, tornEdge } from "../lib/draw";
import { reduced } from "../lib/motion";

/** 0 dark, 1 stamped, 2 drawn, 3 weighed, 4 tearing, 5 gone. */
type Phase = 0 | 1 | 2 | 3 | 4 | 5;

const BEATS: [Phase, number][] = [[1, 90], [2, 430], [3, 880], [4, 1880], [5, 2560]];

export default function Boot({ onDone }: { onDone?: () => void }) {
  const [phase, setPhase] = useState<Phase>(0);
  const timers = useRef<number[]>([]);

  useEffect(() => {
    const finish = () => {
      document.documentElement.removeAttribute("data-booting");
      onDone?.();
    };

    if (reduced()) { setPhase(5); finish(); return; }

    document.documentElement.setAttribute("data-booting", "");
    timers.current = BEATS.map(([p, at]) =>
      window.setTimeout(() => { setPhase(p); if (p === 5) finish(); }, at),
    );

    // Any key, any click, and the reader is through. The tear still plays, so
    // skipping lands you on the page rather than cutting to black.
    const skip = () => {
      timers.current.forEach(clearTimeout);
      timers.current = [];
      setPhase(4);
      timers.current = [window.setTimeout(() => { setPhase(5); finish(); }, 620)];
    };
    const onKey = (e: KeyboardEvent) => { if (!e.metaKey && !e.ctrlKey) skip(); };
    window.addEventListener("keydown", onKey);
    window.addEventListener("pointerdown", skip);

    return () => {
      timers.current.forEach(clearTimeout);
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("pointerdown", skip);
      document.documentElement.removeAttribute("data-booting");
    };
  }, [onDone]);

  if (phase === 5) return null;

  return (
    <div className="boot" data-phase={phase} aria-hidden="true">
      <div className="boot-field">
        <div className="boot-core">
          <span className="boot-seal">
            <img src={asset("brand/lccf-logo.png")} alt="" draggable={false} />
            <svg className="boot-ring" viewBox="0 0 300 300">
              <path d={inkEllipse(150, 150, 138, 136, 9, 0.035)} fill="none"
                    stroke="var(--gold)" strokeWidth="3" strokeLinecap="round" />
            </svg>
          </span>

          <p className="boot-word">
            {["The", "Laura", "Cash Cow", "Framework"].map((w, i) => (
              <span key={w} style={{ ["--d" as string]: `${i * 70}ms` }}>{w}</span>
            ))}
          </p>

          <div className="boot-bars">
            <i style={{ ["--w" as string]: "45%", ["--d" as string]: "0ms" }}>
              <b>45</b><em>is it good</em>
            </i>
            <i style={{ ["--w" as string]: "55%", ["--d" as string]: "140ms" }}>
              <b>55</b><em>is it good for her</em>
            </i>
          </div>
        </div>

        <span className="boot-skip">press anything to skip</span>
      </div>

      <svg className="boot-tear" viewBox="0 0 1200 40" preserveAspectRatio="none">
        <path d={tornEdge(1200, 40, 17)} fill="var(--ink)" />
      </svg>
    </div>
  );
}
