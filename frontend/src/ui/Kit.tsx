import { asset } from "../lib/asset";
import { useEffect, useRef, useState } from "react";
import { skew } from "../lib/draw";
import { reduced, useEnter, useTally, useVelocity } from "../lib/motion";

/* --- buttons --------------------------------------------------------------- */

export function Btn({
  children, onClick, kind = "plain", size = "", arrow = false, disabled, href, title,
}: {
  children: React.ReactNode;
  onClick?: () => void;
  kind?: "plain" | "go" | "ink";
  size?: "" | "lg" | "sm";
  arrow?: boolean;
  disabled?: boolean;
  href?: string;
  title?: string;
}) {
  const cls = `btn${kind === "go" ? " btn-go" : kind === "ink" ? " btn-ink" : ""}${size ? ` btn-${size}` : ""}`;
  const inner = (
    <>
      <span>{children}</span>
      {arrow && (
        <svg viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="2.2" aria-hidden="true">
          <path d="M2.5 9h12M10 4l5 5-5 5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      )}
    </>
  );
  if (href) {
    return <a className={cls} href={href} target="_blank" rel="noreferrer noopener" title={title}>{inner}</a>;
  }
  return <button className={cls} onClick={onClick} disabled={disabled} title={title}>{inner}</button>;
}

/* --- numbers --------------------------------------------------------------- */

/**
 * A figure that arrives. It counts once, when it reaches the screen, because
 * the number landing is the result landing. It does not re-run on hover and it
 * does not loop.
 */
export function Fig({
  value, dp = 0, prefix = "", suffix = "", className = "", ms = 1100, compact = false,
}: {
  value: number; dp?: number; prefix?: string; suffix?: string;
  className?: string; ms?: number; compact?: boolean;
}) {
  const { ref, inView } = useEnter<HTMLSpanElement>(0.5);
  const v = useTally(value, ms, inView);
  const body = compact ? short(v) : v.toLocaleString("en-US", {
    minimumFractionDigits: dp, maximumFractionDigits: dp,
  });
  return (
    <span ref={ref} className={`fig num ${className}`}>
      {prefix}{body}{suffix}
    </span>
  );
}

function short(n: number) {
  const a = Math.abs(n);
  if (a >= 1e12) return `${(n / 1e12).toFixed(2)}T`;
  if (a >= 1e9) return `${(n / 1e9).toFixed(1)}B`;
  if (a >= 1e6) return `${(n / 1e6).toFixed(1)}M`;
  if (a >= 1e4) return `${Math.round(n / 1e3)}k`;
  return Math.round(n).toLocaleString("en-US");
}

/* --- pasted paper ---------------------------------------------------------- */

/**
 * A card that reads as a piece of paper laid on the page: a human angle, a
 * hard short shadow, and a strip of tape if it needs holding down.
 */
export function Paper({
  children, seed = 1, tape, className = "", tilt = 2.2, anim = "paste", delay = 0, onClick, style,
}: {
  children: React.ReactNode;
  seed?: number;
  tape?: "left" | "right" | "both" | false;
  className?: string;
  tilt?: number;
  anim?: "paste" | "stamp" | "rise" | false;
  delay?: number;
  onClick?: () => void;
  style?: React.CSSProperties;
}) {
  const rot = skew(seed, tilt);
  const Tag: any = onClick ? "button" : "div";
  return (
    <Tag
      className={`paper ${className}${onClick ? " is-live" : ""}`}
      onClick={onClick}
      data-anim={anim || undefined}
      style={{
        ["--rot" as string]: `${rot}deg`,
        ["--delay" as string]: `${delay}ms`,
        ["--fr" as string]: `${rot - 4}deg`,
        ...style,
      }}
    >
      {tape && tape !== "both" && <i className={`tape tape-${tape}`} aria-hidden="true" />}
      {tape === "both" && (<><i className="tape tape-left" aria-hidden="true" /><i className="tape tape-right" aria-hidden="true" /></>)}
      {children}
    </Tag>
  );
}

/* --- marquee --------------------------------------------------------------- */

/**
 * A ticker strip that feels the page move. It runs at a slow base speed and
 * the scroll adds to it, so the strip accelerates while you scroll and settles
 * when you stop. Scrolling upward reverses it.
 */
export function Marquee({ children, speed = 36, className = "" }: {
  children: React.ReactNode; speed?: number; className?: string;
}) {
  const track = useRef<HTMLDivElement>(null);
  const v = useVelocity();
  const offset = useRef(0);
  const vRef = useRef(0);
  vRef.current = v;

  useEffect(() => {
    const el = track.current;
    if (!el || reduced()) return;
    let raf = 0;
    let last = performance.now();
    const tick = (t: number) => {
      raf = requestAnimationFrame(tick);
      const dt = Math.min(64, t - last) / 1000;
      last = t;
      const w = el.scrollWidth / 2 || 1;
      offset.current -= (speed + vRef.current * 420) * dt;
      if (offset.current <= -w) offset.current += w;
      if (offset.current > 0) offset.current -= w;
      el.style.transform = `translate3d(${offset.current.toFixed(2)}px,0,0)`;
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [speed]);

  return (
    <div className={`marquee ${className}`} aria-hidden="true">
      <div className="marquee-track" ref={track}>
        <div className="marquee-run">{children}</div>
        <div className="marquee-run">{children}</div>
      </div>
    </div>
  );
}

/* --- disclosure ------------------------------------------------------------ */

/** Everything the committee needs and nobody reads first. Folded by default. */
export function Fold({ title, note, children, open: initial = false }: {
  title: string; note?: string; children: React.ReactNode; open?: boolean;
}) {
  const [open, setOpen] = useState(initial);
  return (
    <section className={`fold${open ? " is-open" : ""}`}>
      <button className="fold-head" onClick={() => setOpen(!open)} aria-expanded={open}>
        <span className="fold-mark" aria-hidden="true">
          <i /><i />
        </span>
        <span className="fold-t">{title}</span>
        {note && <span className="fold-n">{note}</span>}
      </button>
      {open && <div className="fold-body">{children}</div>}
    </section>
  );
}

/* --- state ----------------------------------------------------------------- */

/** The cow is thinking. Three dots on a drawn baseline, nothing spinning. */
export function Working({ what = "Working" }: { what?: string }) {
  return (
    <div className="working" role="status">
      <img src={asset("brand/lccf-logo.png")} alt="" className="working-cow" />
      <span className="working-t">{what}</span>
      <span className="working-dots" aria-hidden="true"><i /><i /><i /></span>
    </div>
  );
}

/** Something the framework wants said out loud. */
export function Note({ tone = "plain", children }: {
  tone?: "plain" | "warn" | "bad" | "good"; children: React.ReactNode;
}) {
  return <div className={`note note-${tone}`}>{children}</div>;
}
