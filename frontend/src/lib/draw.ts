/* Hand drawn geometry.
 *
 * The logo is an ink drawing, so the shapes around it should wobble like one.
 * Every generator here is seeded, so a given mark looks the same on every
 * render and nothing twitches when React re-runs a component.
 */

function rng(seed: number) {
  let s = seed >>> 0 || 1;
  return () => {
    s ^= s << 13;
    s ^= s >>> 17;
    s ^= s << 5;
    return ((s >>> 0) % 10000) / 10000 - 0.5;
  };
}

/** A circle drawn by a hand that does not use a compass. */
export function inkCircle(cx: number, cy: number, r: number, seed = 7, wobble = 0.06) {
  const rand = rng(seed);
  const n = 14;
  const pts: [number, number][] = [];
  for (let i = 0; i < n; i++) {
    const a = (i / n) * Math.PI * 2 - 0.4;
    const rr = r * (1 + rand() * wobble * 2);
    pts.push([cx + Math.cos(a) * rr * 1.06, cy + Math.sin(a) * rr]);
  }
  return closedSpline(pts);
}

/** The same hand, drawing round a phrase rather than a word. */
export function inkEllipse(cx: number, cy: number, rx: number, ry: number, seed = 7, wobble = 0.05) {
  const rand = rng(seed);
  const n = 18;
  const pts: [number, number][] = [];
  for (let i = 0; i < n; i++) {
    const a = (i / n) * Math.PI * 2 - 0.5;
    const k = 1 + rand() * wobble * 2;
    pts.push([cx + Math.cos(a) * rx * k, cy + Math.sin(a) * ry * k]);
  }
  return closedSpline(pts);
}

/** A drawn underline, the kind made with one fast pass of a marker. */
export function inkUnderline(w: number, h = 12, seed = 11) {
  const rand = rng(seed);
  const n = 7;
  const pts: [number, number][] = [];
  for (let i = 0; i <= n; i++) {
    const t = i / n;
    pts.push([t * w, h * 0.5 + Math.sin(t * Math.PI) * -h * 0.28 + rand() * h * 0.4]);
  }
  return openSpline(pts);
}

/** A loose arrow. The head is two strokes, not a filled triangle. */
export function inkArrow(w: number, h: number, seed = 5) {
  const rand = rng(seed);
  const body = openSpline([
    [2, h * 0.5 + rand() * 3],
    [w * 0.34, h * 0.5 + h * 0.22 + rand() * 3],
    [w * 0.7, h * 0.5 - h * 0.12 + rand() * 3],
    [w - 4, h * 0.5 + rand() * 2],
  ]);
  const head = `M ${w - 16} ${h * 0.5 - 8} L ${w - 3} ${h * 0.5} L ${w - 16} ${h * 0.5 + 9}`;
  return { body, head };
}

/** The four point sparkle from the logo. */
export function sparkle(r: number, inner = 0.26) {
  const p: string[] = [];
  for (let i = 0; i < 4; i++) {
    const a = (i / 4) * Math.PI * 2 - Math.PI / 2;
    const b = a + Math.PI / 4;
    p.push(
      `${i === 0 ? "M" : "L"} ${(Math.cos(a) * r).toFixed(2)} ${(Math.sin(a) * r).toFixed(2)}`,
      `L ${(Math.cos(b) * r * inner).toFixed(2)} ${(Math.sin(b) * r * inner).toFixed(2)}`,
    );
  }
  return p.join(" ") + " Z";
}

/** A torn paper edge, used where one colour field meets the next. */
export function tornEdge(w: number, h: number, seed = 23, teeth = 26) {
  const rand = rng(seed);
  const pts: [number, number][] = [[0, h]];
  for (let i = 0; i <= teeth; i++) {
    const t = i / teeth;
    const y = h * 0.42 + rand() * h * 0.8 + Math.sin(t * 7.3 + seed) * h * 0.16;
    pts.push([t * w, Math.max(1, Math.min(h - 1, y))]);
  }
  pts.push([w, h]);
  return pts.map(([x, y], i) => `${i ? "L" : "M"} ${x.toFixed(1)} ${y.toFixed(1)}`).join(" ") + " Z";
}

/* --- splines --------------------------------------------------------------- */

function openSpline(pts: [number, number][]) {
  if (pts.length < 2) return "";
  let d = `M ${pts[0][0].toFixed(2)} ${pts[0][1].toFixed(2)}`;
  for (let i = 0; i < pts.length - 1; i++) {
    const [x0, y0] = pts[i];
    const [x1, y1] = pts[i + 1];
    const mx = (x0 + x1) / 2;
    const my = (y0 + y1) / 2;
    d += ` Q ${x0.toFixed(2)} ${y0.toFixed(2)} ${mx.toFixed(2)} ${my.toFixed(2)}`;
  }
  const last = pts[pts.length - 1];
  d += ` L ${last[0].toFixed(2)} ${last[1].toFixed(2)}`;
  return d;
}

function closedSpline(pts: [number, number][]) {
  const n = pts.length;
  let d = "";
  for (let i = 0; i <= n; i++) {
    const [x0, y0] = pts[i % n];
    const [x1, y1] = pts[(i + 1) % n];
    const mx = (x0 + x1) / 2;
    const my = (y0 + y1) / 2;
    d += i === 0 ? `M ${mx.toFixed(2)} ${my.toFixed(2)}` : ` Q ${x0.toFixed(2)} ${y0.toFixed(2)} ${mx.toFixed(2)} ${my.toFixed(2)}`;
  }
  return d + " Z";
}

/* --- colour ---------------------------------------------------------------- */

/** The categorical set, lifted off the logo illustration. Identity, never size. */
export const INKS = ["#eba618", "#e8705c", "#3f9b6e", "#b45fa8", "#3d87ad", "#d2601f", "#86912c"];

export const SIGNAL_INK: Record<string, string> = {
  GREEN: "#2a8a53",
  AMBER_PLUS: "#d88d06",
  AMBER: "#d88d06",
  RED: "#cf3f26",
  INSUFFICIENT_DATA: "#6d7f88",
};

/** A deterministic small rotation, so pasted things sit at human angles. */
export function skew(seed: number, deg = 2.2) {
  const r = rng(seed * 97 + 13);
  return +(r() * 2 * deg).toFixed(2);
}
