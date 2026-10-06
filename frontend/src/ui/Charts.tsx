/* Every chart here is drawn by hand on a canvas we control. None of it comes
 * out of a library with its defaults showing, because a default axis is the
 * fastest way to make a page look like it was assembled rather than designed.
 */

import { useMemo, useState } from "react";
import { INKS, SIGNAL_INK, inkCircle } from "../lib/draw";
import { useEnter, useTally } from "../lib/motion";
import type { Category } from "../api";

const polar = (cx: number, cy: number, r: number, deg: number): [number, number] => {
  const a = ((deg - 90) * Math.PI) / 180;
  return [cx + r * Math.cos(a), cy + r * Math.sin(a)];
};

const arcPath = (cx: number, cy: number, r: number, a0: number, a1: number) => {
  const [x0, y0] = polar(cx, cy, r, a0);
  const [x1, y1] = polar(cx, cy, r, a1);
  return `M ${x0} ${y0} A ${r} ${r} 0 ${a1 - a0 > 180 ? 1 : 0} 1 ${x1} ${y1}`;
};

/* --- the verdict ----------------------------------------------------------- */

/**
 * The composite, drawn as a stamp.
 *
 * A stamp is the right object for this. It is the mark a committee puts on a
 * decision, it carries exactly one number, and it is either on the page or it
 * is not. The ring around the rim is that number against 100, with a notch cut
 * at the 90 a green call needs.
 */
export function Stamp({ score, signal, label, size = 300 }: {
  score: number; signal: string; label: string; size?: number;
}) {
  const { ref, inView } = useEnter<HTMLDivElement>(0.3);
  const v = useTally(score, 1300, inView);
  const ink = SIGNAL_INK[signal] ?? "#cf8a14";
  const S = 300, c = S / 2;
  const A0 = 118, SPAN = 304;
  const toA = (p: number) => A0 + (Math.max(0, Math.min(100, p)) / 100) * SPAN;
  const notch = (p: number) => {
    const [x0, y0] = polar(c, c, 122, toA(p));
    const [x1, y1] = polar(c, c, 139, toA(p));
    return `M ${x0} ${y0} L ${x1} ${y1}`;
  };

  // Text runs round the rim, so each arc has to be drawn in the direction the
  // words read: clockwise over the top, anticlockwise under the bottom.
  const [tx0, ty0] = polar(c, c, 99, 292);
  const [tx1, ty1] = polar(c, c, 99, 68);
  const [bx0, by0] = polar(c, c, 97, 248);
  const [bx1, by1] = polar(c, c, 97, 112);

  return (
    <div className="stamp" ref={ref} style={{ width: size }} data-signal={signal}>
      <svg viewBox={`0 0 ${S} ${S}`} role="img"
           aria-label={`Composite ${score.toFixed(0)} of 100. Signal: ${label}.`}>
        <defs>
          <path id="stamp-top" d={`M ${tx0} ${ty0} A 99 99 0 0 1 ${tx1} ${ty1}`} />
          <path id="stamp-bot" d={`M ${bx0} ${by0} A 97 97 0 0 0 ${bx1} ${by1}`} />
        </defs>

        <path d={inkCircle(c, c, 142, 3, 0.012)} fill="none" stroke={ink} strokeWidth="1.8" opacity="0.45" />

        <path d={arcPath(c, c, 130, A0, A0 + SPAN)} fill="none" stroke={ink} strokeWidth="9"
              strokeLinecap="round" opacity="0.15" />
        <path d={arcPath(c, c, 130, A0, Math.max(A0 + 0.6, toA(v)))} fill="none" stroke={ink}
              strokeWidth="9" strokeLinecap="round" />
        <path d={notch(90)} stroke="var(--ink)" strokeWidth="2.6" strokeLinecap="round" />

        <path d={inkCircle(c, c, 116, 9, 0.013)} fill="none" stroke={ink} strokeWidth="3.4" />
        <path d={inkCircle(c, c, 84, 17, 0.016)} fill="none" stroke={ink} strokeWidth="1.6" opacity="0.5" />

        <text className="stamp-ring" fill={ink}>
          <textPath href="#stamp-top" startOffset="50%" textAnchor="middle">
            LAURA CASH COW FRAMEWORK
          </textPath>
        </text>
        <text className="stamp-ring stamp-ring-b" fill={ink}>
          <textPath href="#stamp-bot" startOffset="50%" textAnchor="middle">
            {label.toUpperCase()}
          </textPath>
        </text>

        <text x={c} y={c + 16} textAnchor="middle" className="stamp-num" fill="var(--ink)">
          {v.toFixed(0)}
        </text>
        <text x={c} y={c + 44} textAnchor="middle" className="stamp-sub" fill="var(--ink-3)">
          COMPOSITE / 100
        </text>
      </svg>
    </div>
  );
}

/**
 * The two scores that produced the composite.
 *
 * The columns are drawn at the width of the exponent each one carries, 45 and
 * 55, so you can see that Laura outweighs the security before you read a word.
 */
export function TwoUp({ sqs, lpfs, ccs, signal, gate }: {
  sqs: number; lpfs: number; ccs: number; signal: string; gate: number;
}) {
  const { ref, inView } = useEnter<HTMLDivElement>(0.3);
  const a = useTally(sqs, 1100, inView);
  const b = useTally(lpfs, 1250, inView);
  const ink = SIGNAL_INK[signal] ?? "#cf8a14";

  const rows: [string, string, number, number, string][] = [
    ["Is it any good?", "Security quality", a, 0.45, "var(--ink)"],
    ["Is it good for her?", "Laura fit", b, 0.55, ink],
  ];

  return (
    <div className="twoup" ref={ref}>
      {rows.map(([q, name, val, w, col]) => (
        <div className="tu" key={name} style={{ flexGrow: w * 10 }}>
          <div className="tu-q">{q}</div>
          <div className="tu-col">
            <i className="tu-fill" style={{ height: `${val}%`, background: col }} />
            <i className="tu-gate" style={{ bottom: `${gate}%` }}><b>needs {gate.toFixed(0)}</b></i>
            <span className="tu-val num" style={{ bottom: `calc(${val}% + 8px)` }}>{val.toFixed(0)}</span>
          </div>
          <div className="tu-name">{name}</div>
          <div className="tu-w num">counts {(w * 100).toFixed(0)}%</div>
        </div>
      ))}
      <div className="tu-eq">
        <span className="tu-eq-sign">=</span>
        <span className="tu-eq-val num">{ccs.toFixed(0)}</span>
        <span className="tu-eq-lab">composite</span>
        <span className="tu-eq-note num">geometric mean, 45 / 55</span>
      </div>
    </div>
  );
}

/**
 * What green needs, and what it got.
 *
 * The engine was repeating the same sentence four times, once per threshold.
 * Four short bars say it once and say it faster.
 */
export function Gates({ sqs, lpfs, ccs, dcs, need }: {
  sqs: number; lpfs: number; ccs: number; dcs: number;
  need: { sqs: number; lpfs: number; ccs: number; dcs: number };
}) {
  const rows: [string, number, number][] = [
    ["Security quality", sqs, need.sqs],
    ["Laura fit", lpfs, need.lpfs],
    ["Composite", ccs, need.ccs],
    ["Data confidence", dcs, need.dcs],
  ];
  return (
    <div className="gates">
      <span className="tag bare">What a green call needs</span>
      {rows.map(([label, got, want]) => {
        const ok = got >= want;
        return (
          <div className="gt" key={label} data-ok={ok || undefined}>
            <span className="gt-n">{label}</span>
            <span className="gt-track">
              <i style={{ width: `${Math.min(100, got)}%` }} />
              <b style={{ left: `${want}%` }} />
            </span>
            <span className="gt-v num">{got.toFixed(0)}</span>
            <span className="gt-w num">/ {want}</span>
            <span className="gt-m" aria-hidden="true">{ok ? "✓" : "✕"}</span>
          </div>
        );
      })}
    </div>
  );
}

/* --- the breakdown --------------------------------------------------------- */

/**
 * Where the hundred points went.
 *
 * This replaces a polar area chart that was lovely and hard to read. The ruler
 * is literally the score: every category gets a slice of the bar as wide as the
 * points it carries, filled as far as it earned them, and the filled share of
 * the whole bar is the number at the top. Hatching is points left on the table.
 */
export function Breakdown({ categories, labels, active, onPick, score, kind, gate }: {
  categories: Category[];
  labels: Record<string, string>;
  active: string | null;
  onPick: (k: string | null) => void;
  score: number;
  kind: "quality" | "fit";
  gate: number;
}) {
  const { ref, inView } = useEnter<HTMLDivElement>(0.2);
  const shown = useTally(1, 900, inView);

  const rows = useMemo(() => {
    const list = categories.map((c, i) => ({
      cat: c,
      pts: c.points_declared || c.points_available || 0,
      ink: INKS[i % INKS.length],
    }));
    return list.sort((x, y) => y.pts - x.pts);
  }, [categories]);

  const total = rows.reduce((a, r) => a + r.pts, 0) || 100;
  const widest = Math.max(...rows.map((r) => r.pts), 1);

  return (
    <div className={`bd bd-${kind}`} ref={ref} onPointerLeave={() => onPick(null)}>
      <div className="bd-ruler" role="img"
           aria-label={`${score.toFixed(0)} of 100 points earned across ${rows.length} categories`}>
        {rows.map(({ cat, pts, ink }) => (
          <span key={cat.key} className="bd-seg" style={{ flexGrow: pts }}
                data-dim={active && active !== cat.key ? "true" : undefined}
                onPointerEnter={() => onPick(cat.key)}
                onClick={() => onPick(active === cat.key ? null : cat.key)}
                title={`${labels[cat.key] ?? cat.key}: ${cat.points_earned.toFixed(1)} of ${pts} points`}>
            <i style={{ width: `${cat.score * shown}%`, background: ink }} />
          </span>
        ))}
        <b className="bd-gate" style={{ left: `${gate}%` }}><span>{gate.toFixed(0)}</span></b>
      </div>
      <div className="bd-scale num" aria-hidden="true">
        <span>0</span><span>50</span><span>what green needs</span>
      </div>

      <ul className="bd-rows">
        {rows.map(({ cat, pts, ink }) => (
          <li key={cat.key}>
            <button data-on={active === cat.key || undefined}
                    onPointerEnter={() => onPick(cat.key)}
                    onClick={() => onPick(active === cat.key ? null : cat.key)}>
              <i className="bd-sw" style={{ background: ink }} />
              <span className="bd-n">{labels[cat.key] ?? cat.key}</span>
              <span className="bd-bar" style={{ width: `${(pts / widest) * 100}%` }}>
                <em style={{ width: `${cat.score * shown}%`, background: ink }} />
              </span>
              <span className="bd-p num">{cat.points_earned.toFixed(1)}<small>/{pts}</small></span>
              <span className="bd-s num">{cat.score.toFixed(0)}</span>
            </button>
          </li>
        ))}
      </ul>
      <p className="bd-help fine">
        Bar length is how many of the hundred points the category carries. The solid part
        is what it earned. Pick one to pull its metrics up at the bottom of the page.
      </p>
    </div>
  );
}

/* --- the ladder ------------------------------------------------------------ */

type Payment = {
  year: number; required: number; present_value: number; discount_rate_pct: number;
  state: string; state_description: string; notes: string[]; shortfall: number;
};

/**
 * Ten columns, one per payment. The outline is the $50,000 due. The fill is
 * what it costs to lock in today, which is why the columns shrink as the years
 * get later: the back of the ladder is the cheap end.
 */
export function LadderChart({ payments }: { payments: Payment[] }) {
  const { ref, inView } = useEnter<HTMLDivElement>(0.18);
  const grow = useTally(1, 1200, inView);
  const [at, setAt] = useState<number | null>(null);
  const hi = Math.max(...payments.map((p) => p.required), 1);
  const rates = payments.map((p) => p.discount_rate_pct);
  const rLo = Math.min(...rates) - 0.08, rHi = Math.max(...rates) + 0.08;

  return (
    <div className="ladder" ref={ref} onPointerLeave={() => setAt(null)}>
      <div className="ladder-cols">
        {payments.map((p, i) => {
          const fill = (p.present_value / hi) * 100 * grow;
          const open = at === p.year;
          return (
            <button key={p.year} className="lc" data-state={p.state} data-open={open || undefined}
                    onPointerEnter={() => setAt(p.year)} onFocus={() => setAt(p.year)}
                    onClick={() => setAt(open ? null : p.year)}
                    style={{ ["--d" as string]: `${i * 55}ms` }}>
              <span className="lc-cost num">${Math.round(p.present_value / 1000)}k</span>
              <span className="lc-tube">
                <i className="lc-fill" style={{ height: `${fill}%` }} />
                <i className="lc-rate" style={{
                  bottom: `${((p.discount_rate_pct - rLo) / (rHi - rLo)) * 100}%`,
                }} />
              </span>
              <span className="lc-year num">{p.year}</span>
            </button>
          );
        })}
      </div>

      <div className="ladder-foot">
        <span className="tag bare">
          Outline: the $50,000 due. Fill: what it costs today. Dot: the Treasury yield for that maturity.
        </span>
      </div>

      {at !== null && (() => {
        const p = payments.find((x) => x.year === at)!;
        return (
          <div className="ladder-read" key={p.year}>
            <span className="lr-y num">{p.year}</span>
            <span className={`chip chip-${p.state === "MATCHED" ? "green" : p.state === "UNFUNDED" ? "red" : "rose"}`}>
              {p.state.replace(/_/g, " ").toLowerCase()}
            </span>
            <span className="lr-d">{p.state_description}</span>
            <span className="lr-n num">
              costs ${Math.round(p.present_value).toLocaleString("en-US")} today at {p.discount_rate_pct.toFixed(2)}%
            </span>
            {p.notes[0] && <span className="lr-note">{p.notes[0]}</span>}
          </div>
        );
      })()}
    </div>
  );
}

/* --- small parts ----------------------------------------------------------- */

/** Five years of price, drawn small. */
export function Trace({ values, w = 190, h = 46 }: { values: number[]; w?: number; h?: number }) {
  if (!values || values.length < 2) return null;
  const lo = Math.min(...values), hi = Math.max(...values);
  const span = hi - lo || 1;
  const pts = values.map((v, i): [number, number] => [
    (i / (values.length - 1)) * w,
    h - ((v - lo) / span) * (h - 6) - 3,
  ]);
  const d = pts.map(([x, y], i) => `${i ? "L" : "M"} ${x.toFixed(1)} ${y.toFixed(1)}`).join(" ");
  const up = values[values.length - 1] >= values[0];
  return (
    <svg className="trace" width={w} height={h} viewBox={`0 0 ${w} ${h}`} aria-hidden="true">
      <path d={`${d} L ${w} ${h} L 0 ${h} Z`} fill={up ? "var(--sage-hi)" : "var(--rose-hi)"} opacity="0.7" />
      <path d={d} fill="none" stroke={up ? "var(--sage-dk)" : "var(--rose-dk)"} strokeWidth="2" strokeLinejoin="round" />
    </svg>
  );
}

/** One metric against its peers. The notch is the median it is measured from. */
export function Meter({ score, status }: { score: number; status: string }) {
  if (status === "NOT_APPLICABLE") return <span className="meter is-na">not applicable</span>;
  const tone = score >= 70 ? "good" : score >= 45 ? "mid" : "weak";
  return (
    <span className={`meter meter-${tone}`} data-missing={status === "MISSING" || undefined}>
      <i style={{ width: `${Math.max(2, Math.min(100, score))}%` }} />
      <b className="meter-notch" />
    </span>
  );
}

/** A proportion, drawn as a row of blocks. Counting beats reading a percent. */
