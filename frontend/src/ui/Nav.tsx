import { asset } from "../lib/asset";
import { useEffect, useState } from "react";
import { onScroll } from "../lib/motion";

export type View = "home" | "score";

/** The overview is one page, so its navigation is a set of places on it. */
export const SECTIONS: [string, string][] = [
  ["client", "The client"],
  ["scores", "The two scores"],
  ["engine", "How it runs"],
  ["rules", "The rules"],
];

export function Nav({ view, go }: { view: View; go: (v: View) => void }) {
  const [stuck, setStuck] = useState(false);
  const [here, setHere] = useState<string>("");

  useEffect(() => onScroll(({ y, h }) => {
    setStuck(y > 24);
    if (view !== "home") return;
    let found = "";
    for (const [id] of SECTIONS) {
      const el = document.getElementById(id);
      if (el && el.getBoundingClientRect().top < h * 0.42) found = id;
    }
    setHere(found);
  }), [view]);

  const jump = (id: string) => {
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <header className={`nav${stuck ? " is-stuck" : ""}`}>
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
          <nav className="tabs" aria-label="On this page">
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

        <button className="nav-cta" onClick={() => go("score")} data-quiet={view === "score" || undefined}>
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
