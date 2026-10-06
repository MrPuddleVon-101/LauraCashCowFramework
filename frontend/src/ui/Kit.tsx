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

/* --- more furniture --------------------------------------------------------- */

/**
 * A figure on split-flap boards: each digit rolls into place.
 *
 * Counting a number up is one gesture. Rolling each column separately is a
 * different one, and it suits a figure that is being read off a machine rather
 * than growing. Used for the headline statistics, not for scores.
 */
export function Odometer({ value, prefix = "", suffix = "", className = "" }: {
  value: string; prefix?: string; suffix?: string; className?: string;
}) {
  const { ref, inView } = useEnter<HTMLSpanElement>(0.4);
  const chars = value.split("");
  return (
    <span ref={ref} className={`odo ${className}`} aria-label={`${prefix}${value}${suffix}`}>
      {prefix && <i className="odo-fix">{prefix}</i>}
      {chars.map((c, i) => (
        <span key={i} className={/\d/.test(c) ? "odo-d" : "odo-sep"} aria-hidden="true">
          {/\d/.test(c) ? (
            <span className="odo-reel" style={{
              transform: inView ? `translateY(-${Number(c) * 10}%)` : "translateY(0)",
              transitionDelay: `${i * 70}ms`,
            }}>
              {"0123456789".split("").map((d) => <b key={d}>{d}</b>)}
            </span>
          ) : c}
        </span>
      ))}
      {suffix && <i className="odo-fix">{suffix}</i>}
    </span>
  );
}

/** A sticker whose corner lifts when you reach for it. */
export function Peel({ children, tone = "gold", rotate = -2, className = "", onClick }: {
  children: React.ReactNode; tone?: string; rotate?: number;
  className?: string; onClick?: () => void;
}) {
  const Tag: any = onClick ? "button" : "span";
  return (
    <Tag className={`peel peel-${tone} ${className}`} onClick={onClick}
         style={{ ["--rot" as string]: `${rotate}deg` }}>
      <span className="peel-face">{children}</span>
      <i className="peel-corner" aria-hidden="true" />
    </Tag>
  );
}

/** Nudges on hover, the way a pinned card does when you brush past it. */
export function Wobble({ children, className = "", amount = 1.6 }: {
  children: React.ReactNode; className?: string; amount?: number;
}) {
  return (
    <span className={`wobble ${className}`} style={{ ["--amt" as string]: `${amount}deg` }}>
      {children}
    </span>
  );
}

/** Two faces on one card. Clicking turns it over. */
export function Flip({ front, back, className = "" }: {
  front: React.ReactNode; back: React.ReactNode; className?: string;
}) {
  const [over, setOver] = useState(false);
  return (
    <button className={`flip${over ? " is-over" : ""} ${className}`}
            onClick={() => setOver(!over)} aria-pressed={over}>
      <span className="flip-in">
        <span className="flip-f">{front}</span>
        <span className="flip-b">{back}</span>
      </span>
    </button>
  );
}

/** A line of type that assembles itself word by word when it arrives. */
export function Stagger({ text, className = "", step = 55, as: As = "span" }: {
  text: string; className?: string; step?: number; as?: any;
}) {
  const { ref } = useEnter<HTMLElement>(0.3);
  return (
    <As ref={ref as any} className={`stag ${className}`} data-anim="stag">
      {text.split(" ").map((w, i) => (
        <span key={i} className="stag-w" style={{ ["--d" as string]: `${i * step}ms` }}>
          {w}{i < text.split(" ").length - 1 ? " " : ""}
        </span>
      ))}
    </As>
  );
}
