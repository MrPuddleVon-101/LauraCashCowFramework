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

/* --- a wider vocabulary of marks ------------------------------------------- */

/** A scalloped rosette edge, the kind stamped on a seal or a prize ribbon. */
export function rosette(r: number, teeth = 22, depth = 0.085, seed = 31) {
  const rand = rng(seed);
  const pts: [number, number][] = [];
  for (let i = 0; i < teeth * 2; i++) {
    const a = (i / (teeth * 2)) * Math.PI * 2;
    const out = i % 2 === 0;
    const rr = r * (out ? 1 : 1 - depth) * (1 + rand() * 0.02);
    pts.push([Math.cos(a) * rr, Math.sin(a) * rr]);
  }
  return closedSpline(pts);
}

/** A loose scribble, the sort made while thinking. */
export function scribble(w: number, h: number, loops = 3, seed = 17) {
  const rand = rng(seed);
  const pts: [number, number][] = [];
  const n = loops * 10;
  for (let i = 0; i <= n; i++) {
    const t = i / n;
    const a = t * Math.PI * 2 * loops;
    pts.push([
      t * w + Math.cos(a) * w * 0.07 + rand() * 4,
      h / 2 + Math.sin(a) * h * 0.42 + rand() * 3,
    ]);
  }
  return openSpline(pts);
}

/** A marker swipe, wider in the middle the way a chisel tip lays down ink. */
export function highlight(w: number, h: number, seed = 23) {
  const rand = rng(seed);
  const top: [number, number][] = [];
  const bot: [number, number][] = [];
  const n = 8;
  for (let i = 0; i <= n; i++) {
    const t = i / n;
    const bulge = Math.sin(t * Math.PI) * h * 0.14;
    top.push([t * w, h * 0.12 - bulge * 0.5 + rand() * 2]);
    bot.push([t * w, h * 0.88 + bulge * 0.5 + rand() * 2]);
  }
  const fwd = top.map(([x, y], i) => `${i ? "L" : "M"} ${x.toFixed(1)} ${y.toFixed(1)}`).join(" ");
  const back = bot.reverse().map(([x, y]) => `L ${x.toFixed(1)} ${y.toFixed(1)}`).join(" ");
  return `${fwd} ${back} Z`;
}

/** A splat of ink, for the places a pen was put down too hard. */
export function splat(r: number, seed = 41) {
  const rand = rng(seed);
  const n = 11;
  const pts: [number, number][] = [];
  for (let i = 0; i < n; i++) {
    const a = (i / n) * Math.PI * 2;
    const rr = r * (0.62 + Math.abs(rand()) * 1.5);
    pts.push([Math.cos(a) * rr, Math.sin(a) * rr]);
  }
  return closedSpline(pts);
}

/** A torn-ticket edge: a run of half circles bitten out of a straight line. */
export function perforation(length: number, bite = 5) {
  const n = Math.max(2, Math.round(length / (bite * 2)));
  let d = `M 0 0`;
  for (let i = 0; i < n; i++) {
    const x = ((i + 1) / n) * length;
    d += ` A ${bite} ${bite} 0 0 ${i % 2 ? 1 : 0} ${x} 0`;
  }
  return d;
}

/** A zigzag seam, like pinking shears through paper. */
export function zigzag(w: number, h: number, teeth = 28) {
  const step = w / teeth;
  let d = `M 0 ${h}`;
  for (let i = 0; i <= teeth; i++) {
    d += ` L ${(i * step).toFixed(1)} ${i % 2 ? 1 : h - 1}`;
  }
  return d + ` L ${w} ${h} Z`;
}

/** A running stitch, dashes along a gently wandering line. */
export function stitch(w: number, seed = 13) {
  const rand = rng(seed);
  const pts: [number, number][] = [];
  for (let i = 0; i <= 10; i++) pts.push([(i / 10) * w, 6 + rand() * 4]);
  return openSpline(pts);
}

/** Small hand drawn glyphs, by name. Each is drawn in a 24 by 24 box. */
export const DOODLES: Record<string, string> = {
  star: "M12 2.6 L14.2 9.3 L21.2 9.3 L15.6 13.5 L17.7 20.2 L12 16.1 L6.3 20.2 L8.4 13.5 L2.8 9.3 L9.8 9.3 Z",
  bolt: "M13.5 2 L5 13.4 L10.8 13.4 L9.6 22 L18.6 10.2 L12.6 10.2 Z",
  heart: "M12 20.8 C4.5 15.4 2.4 11.4 3.6 8.1 C4.7 5.1 8.6 4.4 12 8 C15.4 4.4 19.3 5.1 20.4 8.1 C21.6 11.4 19.5 15.4 12 20.8 Z",
  spiral: "M12 12 C12 10.6 13.2 10.2 13.8 11 C14.7 12.2 13.4 14.2 11.5 14.2 C8.9 14.2 7.2 11.6 7.9 8.9 C8.8 5.4 12.8 3.6 16.3 5 C20.5 6.7 22.3 11.8 20.2 16",
  check: "M4 13.2 L9.6 18.8 L20.2 5.6",
  cross: "M5 5 L19 19 M19 5 L5 19",
  eye: "M2.4 12 C6 6.6 18 6.6 21.6 12 C18 17.4 6 17.4 2.4 12 Z M12 9.6 A2.4 2.4 0 1 1 12 14.4 A2.4 2.4 0 1 1 12 9.6",
  coin: "M12 3.2 A8.8 8.8 0 1 1 12 20.8 A8.8 8.8 0 1 1 12 3.2 M12 7.2 L12 16.8 M9.4 9.6 L14.6 14.4",
  arrowCurl: "M3.6 18 C6 9.6 12 5.4 19.2 6.6 M19.2 6.6 L14.4 4.2 M19.2 6.6 L15.6 10.8",
  exclaim: "M12 3.6 L12 14.4 M12 18 L12 20.4",
};
