/* The drawn marks. Everything here is decoration with a job: a circle around
 * the word that carries the argument, an arrow pointing at the thing you are
 * meant to press, a torn seam where one colour field ends.
 */

import { asset } from "../lib/asset";
import { useEffect, useRef } from "react";
import {
  DOODLES, highlight, inkArrow, inkCircle, inkEllipse, inkUnderline, perforation,
  rosette, sparkle, splat, stitch, tornEdge, zigzag,
} from "../lib/draw";
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
      <img src={asset("brand/lccf-logo.png")} alt="Laura Cash Cow Framework" className={className} draggable={false} />
      <span className="cow-eye cow-eye-l" aria-hidden="true" />
      <span className="cow-eye cow-eye-r" aria-hidden="true" />
    </div>
  );
}

/* ===========================================================================
   The rest of the drawer: pins, tape, stamps, tags, doodles, margin notes.
   Everything here is decoration that earns its place by pointing at something,
   holding something down, or marking something as checked.
   =========================================================================== */

/** A pushpin, for things held to a board rather than taped to a page. */
export function Pin({ size = 26, color = "var(--red)", className = "", style }: {
  size?: number; color?: string; className?: string; style?: React.CSSProperties;
}) {
  return (
    <svg className={`mk-pin ${className}`} width={size} height={size * 1.25}
         viewBox="0 0 24 30" aria-hidden="true" style={style}>
      <path d="M12 29 L12 16" stroke="var(--ink)" strokeWidth="1.6" strokeLinecap="round" />
      <ellipse cx="12" cy="10" rx="8.4" ry="7.6" fill={color} stroke="var(--ink)" strokeWidth="1.8" />
      <ellipse cx="9.2" cy="7.4" rx="2.6" ry="2" fill="rgba(255,255,255,0.55)" />
    </svg>
  );
}

/** A circular postmark, the kind a counter clerk thumps onto an envelope. */
export function Postmark({ top, bottom, size = 104, color = "var(--rose-dk)", className = "", style }: {
  top: string; bottom?: string; size?: number; color?: string;
  className?: string; style?: React.CSSProperties;
}) {
  const id = `pm${top.replace(/\W/g, "")}${size}`;
  const r = 38;
  const p = (deg: number, rad: number): [number, number] => {
    const a = ((deg - 90) * Math.PI) / 180;
    return [50 + Math.cos(a) * rad, 50 + Math.sin(a) * rad];
  };
  const arc = (a0: number, a1: number, rad: number, sweep = 1) => {
    const [x0, y0] = p(a0, rad); const [x1, y1] = p(a1, rad);
    return `M ${x0} ${y0} A ${rad} ${rad} 0 0 ${sweep} ${x1} ${y1}`;
  };
  return (
    <svg className={`mk-postmark ${className}`} width={size} height={size}
         viewBox="0 0 100 100" aria-hidden="true" style={style}>
      <defs>
        <path id={`${id}t`} d={arc(290, 70, r)} />
        <path id={`${id}b`} d={arc(250, 110, r - 2, 0)} />
      </defs>
      <path d={inkCircle(50, 50, 46, 5, 0.014)} fill="none" stroke={color} strokeWidth="2" opacity="0.6" />
      <path d={inkCircle(50, 50, 41, 9, 0.016)} fill="none" stroke={color} strokeWidth="3" />
      <text className="pm-ring" fill={color}>
        <textPath href={`#${id}t`} startOffset="50%" textAnchor="middle">{top}</textPath>
      </text>
      {bottom && (
        <text className="pm-ring" fill={color}>
          <textPath href={`#${id}b`} startOffset="50%" textAnchor="middle">{bottom}</textPath>
        </text>
      )}
      <path d="M22 50 h56" stroke={color} strokeWidth="1.4" opacity="0.55" />
    </svg>
  );
}

/** A scalloped seal. Used once, for the thing the page is proudest of. */
export function Rosette({ children, size = 128, fill = "var(--gold)", className = "", style }: {
  children?: React.ReactNode; size?: number; fill?: string;
  className?: string; style?: React.CSSProperties;
}) {
  return (
    <span className={`mk-rosette ${className}`} style={{ width: size, height: size, ...style }}>
      <svg viewBox="-70 -70 140 140" aria-hidden="true">
        <path d={rosette(58)} fill={fill} stroke="var(--ink)" strokeWidth="2.4" />
        <path d={inkCircle(0, 0, 47, 11, 0.014)} fill="none" stroke="var(--ink)" strokeWidth="1.6" opacity="0.5" />
      </svg>
      <span className="mk-rosette-in">{children}</span>
    </span>
  );
}

/** A swing tag on a string, for a figure that wants calling out. */
export function PriceTag({ children, color = "var(--sage-hi)", className = "", style }: {
  children: React.ReactNode; color?: string; className?: string; style?: React.CSSProperties;
}) {
  return (
    <span className={`mk-tag ${className}`} style={style}>
      <svg viewBox="0 0 120 54" preserveAspectRatio="none" aria-hidden="true">
        <path d="M14 2 L116 2 Q118 2 118 4 L118 50 Q118 52 116 52 L14 52 L2 27 Z"
              fill={color} stroke="var(--ink)" strokeWidth="2.4" />
        <circle cx="16" cy="27" r="3.4" fill="var(--paper)" stroke="var(--ink)" strokeWidth="1.8" />
      </svg>
      <span className="mk-tag-in">{children}</span>
    </span>
  );
}

/** A marker swipe laid behind a phrase. */
export function Mark({ children, color = "var(--gold-hi)", seed = 23 }: {
  children: React.ReactNode; color?: string; seed?: number;
}) {
  return (
    <span className="mk-hl">
      <svg viewBox="0 0 200 40" preserveAspectRatio="none" aria-hidden="true">
        <path d={highlight(200, 40, seed)} fill={color} />
      </svg>
      <span>{children}</span>
    </span>
  );
}

/** One of the small glyphs from the doodle sheet. */
export function Doodle({ name, size = 22, color = "var(--ink)", fill = false, className = "", style }: {
  name: keyof typeof DOODLES | string; size?: number; color?: string; fill?: boolean;
  className?: string; style?: React.CSSProperties;
}) {
  const d = DOODLES[name as string] ?? DOODLES.star;
  return (
    <svg className={`mk-doodle ${className}`} width={size} height={size} viewBox="0 0 24 24"
         aria-hidden="true" style={style}>
      <path d={d} fill={fill ? color : "none"} stroke={color} strokeWidth={fill ? 1.4 : 2}
            strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/** A note in the margin, in the hand of somebody who read this before you. */
export function Note({ children, side = "right", rotate = -3, className = "" }: {
  children: React.ReactNode; side?: "left" | "right"; rotate?: number; className?: string;
}) {
  return (
    <span className={`mk-note mk-note-${side} ${className}`} style={{ rotate: `${rotate}deg` }}>
      <Doodle name="arrowCurl" size={26} color="var(--ink-4)"
              className={`mk-note-arrow mk-note-arrow-${side}`} />
      <i>{children}</i>
    </span>
  );
}

/** A blot of ink. Purely a texture, placed where a page would have caught one. */
export function Splat({ size = 40, color = "var(--rose)", opacity = 0.5, seed = 41, className = "", style }: {
  size?: number; color?: string; opacity?: number; seed?: number;
  className?: string; style?: React.CSSProperties;
}) {
  return (
    <svg className={`mk-splat ${className}`} width={size} height={size} viewBox="-50 -50 100 100"
         aria-hidden="true" style={{ opacity, ...style }}>
      <path d={splat(34, seed)} fill={color} />
    </svg>
  );
}

/** Ruled or gridded paper, as a background layer. */
export function Paper({ kind = "grid", size = 26, color = "rgba(22,18,15,0.07)", className = "" }: {
  kind?: "grid" | "rule" | "dot"; size?: number; color?: string; className?: string;
}) {
  const id = `pp${kind}${size}${String(color).replace(/\W/g, "")}`;
  return (
    <svg className={`mk-paper ${className}`} aria-hidden="true">
      <defs>
        <pattern id={id} width={size} height={size} patternUnits="userSpaceOnUse">
          {kind === "dot" && <circle cx={size / 2} cy={size / 2} r="1.3" fill={color} />}
          {kind !== "dot" && <path d={`M0 ${size} H${size}`} stroke={color} strokeWidth="1" />}
          {kind === "grid" && <path d={`M${size} 0 V${size}`} stroke={color} strokeWidth="1" />}
        </pattern>
      </defs>
      <rect width="100%" height="100%" fill={`url(#${id})`} />
    </svg>
  );
}

/** Seams with a bit more character than a straight rule. */
export function Seam({ kind = "zig", fill, flip = false }: {
  kind?: "zig" | "perf" | "stitch"; fill: string; flip?: boolean;
}) {
  if (kind === "perf") {
    return (
      <div className="seam seam-perf" aria-hidden="true" style={flip ? { transform: "scaleY(-1)" } : undefined}>
        <svg viewBox="0 0 1200 18" preserveAspectRatio="none">
          <rect width="1200" height="18" fill={fill} />
          <path d={perforation(1200, 7)} transform="translate(0 18)" fill="var(--paper)" />
        </svg>
      </div>
    );
  }
  if (kind === "stitch") {
    return (
      <div className="seam seam-stitch" aria-hidden="true">
        <svg viewBox="0 0 1200 16" preserveAspectRatio="none">
          <path d={stitch(1200)} fill="none" stroke={fill} strokeWidth="3"
                strokeDasharray="14 11" strokeLinecap="round" />
        </svg>
      </div>
    );
  }
  return (
    <div className="seam" aria-hidden="true" style={flip ? { transform: "scaleY(-1)" } : undefined}>
      <svg viewBox="0 0 1200 22" preserveAspectRatio="none">
        <path d={zigzag(1200, 22)} fill={fill} />
      </svg>
    </div>
  );
}
