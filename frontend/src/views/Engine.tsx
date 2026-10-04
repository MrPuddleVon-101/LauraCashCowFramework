import { useEffect, useRef, useState } from "react";
import { clamp, onScroll, reduced } from "../lib/motion";
import { Spark } from "../ui/Marks";

/**
 * The pipeline, scrubbed by the scroll.
 *
 * A candidate is carried along a belt through four stations and comes out the
 * far end as a signal. The order is the argument: the gate runs before any
 * number is weighted, so a score can never be used to talk its way past a rule.
 * Scrolling is what moves it, which makes the order something you do rather
 * than something you are told.
 */

const BELT =
  "M 40 250 C 170 170, 300 330, 450 250 C 600 170, 640 170, 775 250 C 910 330, 1000 330, 1160 250";

type Station = {
  at: number;
  x: number;
  y: number;
  side: "up" | "down";
  n: string;
  title: string;
  line: string;
  body: React.ReactNode;
  tint: string;
};

const STATIONS: Station[] = [
  {
    at: 0.1, x: 166, y: 216, side: "up", n: "01", tint: "var(--sky)",
    title: "Name the job",
    line: "Nothing is scored without a role.",
    body: (
      <div className="st-row">
        <span className="chip">Broad U.S. equity ETF</span>
        <span className="chip chip-gold">Core Growth</span>
      </div>
    ),
  },
  {
    at: 0.37, x: 450, y: 250, side: "down", n: "02", tint: "var(--red)",
    title: "The Red Gate",
    line: "Runs before a single weight is applied.",
    body: (
      <div className="st-gate">
        <span className="st-gate-pass">PASS</span>
        <span className="st-gate-note">A perpetual bond fund offered as a 2034 matcher dies here, at any score.</span>
      </div>
    ),
  },
  {
    at: 0.64, x: 775, y: 250, side: "up", n: "03", tint: "var(--gold)",
    title: "Score it twice",
    line: "Once on its merits. Once against her liabilities.",
    body: (
      <div className="st-two">
        <span><b className="num">75</b> quality</span>
        <span><b className="num">74</b> fit</span>
      </div>
    ),
  },
  {
    at: 0.9, x: 1040, y: 292, side: "down", n: "04", tint: "var(--sage)",
    title: "Combine, 45 / 55",
    line: "Weighted toward her, so a strong security cannot carry a poor fit.",
    body: (
      <div className="st-out">
        <span className="st-out-v num">75</span>
        <span className="chip chip-amber">Amber</span>
      </div>
    ),
  },
];

export default function Engine() {
  const hostRef = useRef<HTMLDivElement>(null);
  const pathRef = useRef<SVGPathElement>(null);
  const tokenRef = useRef<SVGGElement>(null);
  const beltRef = useRef<SVGPathElement>(null);
  const [live, setLive] = useState(reduced() ? 3 : -1);

  useEffect(() => {
    const host = hostRef.current;
    const path = pathRef.current;
    const token = tokenRef.current;
    const belt = beltRef.current;
    if (!host || !path || !token || !belt) return;
    if (reduced()) return;

    const len = path.getTotalLength();
    belt.style.strokeDasharray = `${len}`;
    let shown = -1;

    return onScroll(({ h }) => {
      const r = host.getBoundingClientRect();
      const travel = Math.max(1, r.height - h);
      const p = clamp(-r.top / travel);

      // The belt draws itself just ahead of the token, so the path appears to
      // be laid down by the thing travelling on it.
      belt.style.strokeDashoffset = `${len * (1 - clamp(p * 1.12 + 0.04))}`;

      const pt = path.getPointAtLength(len * p);
      const ahead = path.getPointAtLength(Math.min(len, len * p + 10));
      const ang = (Math.atan2(ahead.y - pt.y, ahead.x - pt.x) * 180) / Math.PI;
      token.setAttribute(
        "transform",
        `translate(${pt.x.toFixed(1)} ${pt.y.toFixed(1)}) rotate(${(ang * 0.5).toFixed(2)})`,
      );

      let idx = -1;
      for (let i = 0; i < STATIONS.length; i++) if (p >= STATIONS[i].at - 0.07) idx = i;
      if (idx !== shown) {
        shown = idx;
        setLive(idx);
      }
    });
  }, []);

  return (
    <div className="engine" ref={hostRef}>
      <div className="engine-stick">
        <div className="wrap engine-head">
          <span className="tag">The engine</span>
          <h2>Four steps, always in this order</h2>
          <p className="lede">Scroll, and watch a candidate go through it.</p>
        </div>

        <div className="engine-stage">
          <svg className="engine-belt" viewBox="0 0 1200 480" aria-hidden="true">
            <path d={BELT} fill="none" stroke="rgba(246,236,217,0.17)" strokeWidth="3"
                  strokeLinecap="round" strokeDasharray="1 11" />
            <path ref={beltRef} d={BELT} fill="none" stroke="var(--gold)" strokeWidth="3.4" strokeLinecap="round" />
            <path ref={pathRef} d={BELT} fill="none" stroke="none" />

            {STATIONS.map((s, i) => (
              <circle key={s.n} cx={s.x} cy={s.y} r={live >= i ? 10 : 6}
                      className="engine-node" data-on={live >= i || undefined}
                      fill={live >= i ? s.tint : "var(--ink)"} stroke="var(--gold)" strokeWidth="2.4" />
            ))}

            <g ref={tokenRef} className="engine-token">
              <rect x="-46" y="-26" width="92" height="52" rx="6" fill="var(--paper-hi)"
                    stroke="var(--ink)" strokeWidth="2.4" />
              <text x="0" y="-2" textAnchor="middle" className="engine-token-t">AVUS</text>
              <text x="0" y="15" textAnchor="middle" className="engine-token-s">candidate</text>
            </g>
          </svg>

          {STATIONS.map((s, i) => (
            <article
              key={s.n}
              className={`station station-${s.side}`}
              data-on={live >= i || undefined}
              style={{ left: `${(s.x / 1200) * 100}%`, ["--tint" as string]: s.tint }}
            >
              <span className="st-n num">{s.n}</span>
              <h3>{s.title}</h3>
              <p className="st-l">{s.line}</p>
              {s.body}
              {i === 3 && <Spark size={26} className="st-spark" color="var(--gold-hi)" />}
            </article>
          ))}
        </div>
      </div>
    </div>
  );
}
