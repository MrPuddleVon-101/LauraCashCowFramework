/* The drawn marks. Everything here is decoration with a job: a circle around
 * the word that carries the argument, an arrow pointing at the thing you are
 * meant to press, a torn seam where one colour field ends.
 */

import { useEffect, useRef } from "react";
import { inkArrow, inkEllipse, inkUnderline, sparkle, tornEdge } from "../lib/draw";
import { useEnter } from "../lib/motion";

/** Circles a word. Draws itself when it arrives. */
export function Ring({ seed = 7, color = "var(--gold)", delay = 300 }: {
  seed?: number; color?: string; delay?: number;
}) {
  const { ref } = useEnter<SVGSVGElement>(0.5);
  return (
    <svg ref={ref} className="mk-ring draw-line" viewBox="0 0 220 86" preserveAspectRatio="none"
         aria-hidden="true" style={{ ["--len" as string]: "560", ["--delay" as string]: `${delay}ms` }}>
      <path d={inkEllipse(110, 43, 104, 38, seed, 0.055)} fill="none" stroke={color}
            strokeWidth="3.4" strokeLinecap="round" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

/** Underlines a word with one fast pass. */
export function Underline({ color = "var(--rose-dk)", delay = 420, seed = 11 }: {
  color?: string; delay?: number; seed?: number;
}) {
  const { ref } = useEnter<SVGSVGElement>(0.5);
  return (
    <svg ref={ref} className="mk-under draw-line" viewBox="0 0 200 14" preserveAspectRatio="none"
         aria-hidden="true" style={{ ["--len" as string]: "230", ["--delay" as string]: `${delay}ms` }}>
      <path d={inkUnderline(200, 14, seed)} fill="none" stroke={color} strokeWidth="4"
            strokeLinecap="round" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

/** Points at something. */
export function Arrow({ w = 96, h = 44, color = "var(--ink)", className = "", rotate = 0 }: {
  w?: number; h?: number; color?: string; className?: string; rotate?: number;
}) {
  const { ref } = useEnter<SVGSVGElement>(0.4);
  const a = inkArrow(w, h, 5);
  return (
    <svg ref={ref} className={`mk-arrow draw-line ${className}`} width={w} height={h}
         viewBox={`0 0 ${w} ${h}`} aria-hidden="true"
         style={{ ["--len" as string]: "200", transform: `rotate(${rotate}deg)` }}>
      <path d={a.body} fill="none" stroke={color} strokeWidth="2.6" strokeLinecap="round" />
      <path d={a.head} fill="none" stroke={color} strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/** The four point star from the logo. */
export function Spark({ size = 22, color = "var(--gold)", className = "", style }: {
  size?: number; color?: string; className?: string; style?: React.CSSProperties;
}) {
  return (
    <svg className={`mk-spark ${className}`} width={size} height={size} viewBox="-16 -16 32 32"
         aria-hidden="true" style={style}>
      <path d={sparkle(14)} fill={color} />
    </svg>
  );
}

/** The seam between two colour fields. */
export function Tear({ fill, seed = 23, flip = false }: { fill: string; seed?: number; flip?: boolean }) {
  return (
    <div className="tear" aria-hidden="true" style={flip ? { transform: "scaleY(-1)" } : undefined}>
      <svg viewBox="0 0 1200 34" preserveAspectRatio="none">
        <path d={tornEdge(1200, 34, seed)} fill={fill} />
      </svg>
    </div>
  );
}

/** Halftone dots, the printed kind, used to shade a block without a gradient. */
export function Halftone({ color = "var(--ink)", opacity = 0.14, size = 9, className = "" }: {
  color?: string; opacity?: number; size?: number; className?: string;
}) {
  const id = `ht${size}${String(color).replace(/\W/g, "")}`;
  return (
    <svg className={`mk-halftone ${className}`} aria-hidden="true" style={{ opacity }}>
      <defs>
        <pattern id={id} width={size} height={size} patternUnits="userSpaceOnUse">
          <circle cx={size / 2} cy={size / 2} r={size * 0.19} fill={color} />
        </pattern>
      </defs>
      <rect width="100%" height="100%" fill={`url(#${id})`} />
    </svg>
  );
}

/**
 * The cow from the logo, watching the pointer.
 *
 * The badge is the drawing. The pupils are two discs placed over where the
 * sunglasses sit, and they track the pointer within a small radius, so the
 * mascot looks at whatever you are about to click.
 */
export function Cow({ size = 220, className = "", watch = true }: {
  size?: number; className?: string; watch?: boolean;
}) {
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = box.current;
    if (!el || !watch) return;
    if (window.matchMedia("(pointer: coarse)").matches) return;
    let raf = 0;
    const to = { x: 0, y: 0 };
    const at = { x: 0, y: 0 };
    const move = (e: PointerEvent) => {
      const r = el.getBoundingClientRect();
      const dx = e.clientX - (r.left + r.width / 2);
      const dy = e.clientY - (r.top + r.height * 0.42);
      const d = Math.hypot(dx, dy) || 1;
      const k = Math.min(1, d / 420);
      to.x = (dx / d) * k;
      to.y = (dy / d) * k;
    };
    const tick = () => {
      raf = requestAnimationFrame(tick);
      at.x += (to.x - at.x) * 0.1;
      at.y += (to.y - at.y) * 0.1;
      el.style.setProperty("--ex", `${(at.x * 5.2).toFixed(2)}px`);
      el.style.setProperty("--ey", `${(at.y * 3.6).toFixed(2)}px`);
      el.style.setProperty("--hx", `${(at.x * 2.4).toFixed(2)}deg`);
    };
    window.addEventListener("pointermove", move, { passive: true });
    tick();
    return () => { window.removeEventListener("pointermove", move); cancelAnimationFrame(raf); };
  }, [watch]);

  return (
    <div className="cow" ref={box} style={{ ["--size" as string]: `${size}px` }}>
      <img src="/brand/lccf-logo.png" alt="Laura Cash Cow Framework" className={className} draggable={false} />
      <span className="cow-eye cow-eye-l" aria-hidden="true" />
      <span className="cow-eye cow-eye-r" aria-hidden="true" />
    </div>
  );
}
