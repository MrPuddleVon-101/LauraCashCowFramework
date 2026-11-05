/* The bar.
 *
 * It sits over a moving world, so it is glass rather than paper, and it earns
 * its place by reporting two things the reader cannot otherwise see: which
 * part of the argument they are in, and how far up the climb they have got.
 *
 * The marker under the links is one element that slides between them rather
 * than a border toggled on each one. That means the bar animates the change
 * instead of just redrawing it, which is the difference between a state
 * change you notice and one you do not.
 */

import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";

import { asset } from "../lib/asset";
import { onScroll } from "../lib/motion";
import { useMagnetic } from "../lib/fx";

export type View = "home" | "score";

/** The overview is one page, so its navigation is a set of places on it. */
export const SECTIONS: [string, string][] = [
  ["client", "The client"],
  ["scores", "The two scores"],
  ["engine", "How it runs"],
  ["rules", "The rules"],
];

export function Nav({ view, go }: { view: View; go: (v: View, ticker?: string) => void }) {
  const cta = useMagnetic<HTMLButtonElement>(0.34);
  const [stuck, setStuck] = useState(false);
  const [here, setHere] = useState<string>("");
  const [climb, setClimb] = useState(0);

  const tabsRef = useRef<HTMLElement>(null);
  const [marker, setMarker] = useState<{ x: number; w: number } | null>(null);

  useEffect(() => onScroll(({ y, h, dh }) => {
    setStuck(y > 24);
    setClimb(Math.min(1, y / Math.max(1, dh - h)));
    if (view !== "home") return;
    let found = "";
    for (const [id] of SECTIONS) {
      const el = document.getElementById(id);
      if (el && el.getBoundingClientRect().top < h * 0.42) found = id;
    }
    setHere(found);
  }), [view]);

  // The marker is measured off the live button, so it stays correct when the
  // labels reflow or the font loads late.
  const measure = useCallback(() => {
    const row = tabsRef.current;
    if (!row) return setMarker(null);
    const on = row.querySelector<HTMLElement>('[aria-current="true"]');
    if (!on) return setMarker(null);
    setMarker({ x: on.offsetLeft, w: on.offsetWidth });
  }, []);

  useLayoutEffect(measure, [here, view, measure]);
  useEffect(() => {
    window.addEventListener("resize", measure);
    document.fonts?.ready?.then(measure).catch(() => {});
    return () => window.removeEventListener("resize", measure);
  }, [measure]);

  const jump = (id: string) => {
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    // Over the dark world the bar has to invert, or the wordmark sits black on
    // black until the reader scrolls past it.
    <header className={`nav${stuck ? " is-stuck" : ""}${view === "home" ? " is-night" : ""}`}>
      <div className="nav-in">
        <button className="brand" onClick={() => go("home")}>
          <img src={asset("brand/lccf-logo.png")} alt="" draggable={false} />
          <span className="brand-w">
            <span className="brand-1">Stonky</span>
            <span className="brand-x">×</span>
            <span className="brand-2">Cash Cows</span>
          </span>
        </button>

        {view === "home" ? (
          <nav className="tabs" aria-label="On this page" ref={tabsRef}>
            {marker && (
              <span className="tab-mark" aria-hidden="true"
                    style={{ transform: `translateX(${marker.x}px)`, width: marker.w }} />
            )}
            {SECTIONS.map(([id, label]) => (
              <button key={id} className="tab" aria-current={here === id} onClick={() => jump(id)}>
                {label}
              </button>
            ))}
          </nav>
        ) : (
          <nav className="tabs" aria-label="Sections">
            <button className="tab tab-back" onClick={() => go("home")}>
              <svg viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="2.3" aria-hidden="true">
                <path d="M15.5 9h-12M8 4L3 9l5 5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              Back to the start
            </button>
          </nav>
        )}

        {/* How far up the chart the reader has flown. It is the one number the
            page cannot show any other way. */}
        {view === "home" && (
          <span className="nav-climb" aria-hidden="true">
            <svg viewBox="0 0 34 34">
              <circle cx="17" cy="17" r="14" className="nav-climb-t" />
              <circle cx="17" cy="17" r="14" className="nav-climb-v"
                      style={{ strokeDasharray: 88, strokeDashoffset: 88 * (1 - climb) }} />
            </svg>
            <b className="num">{Math.round(climb * 100)}</b>
          </span>
        )}

        <button className="nav-cta" ref={cta} onClick={() => go("score")} data-quiet={view === "score" || undefined}
                data-cursor={view === "score" ? "new" : "score"}>
          <span>{view === "score" ? "New ticker" : "Score a ticker"}</span>
          <svg viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="2.3" aria-hidden="true">
            <path d="M2.5 9h12M10 4l5 5-5 5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
      </div>
    </header>
  );
}

/** How far down the document you are, drawn as a filling rule under the bar. */
export function Progress() {
  const [p, setP] = useState(0);
  useEffect(() => onScroll(({ y, h, dh }) => {
    const max = Math.max(1, dh - h);
    setP(Math.min(1, y / max));
  }), []);
  return (
    <div className="progress" aria-hidden="true">
      <i style={{ transform: `scaleX(${p.toFixed(4)})` }} />
    </div>
  );
}
