/* The cover.
 *
 * Built as a stack of planes that move at different rates, so the collage has
 * depth instead of being a picture of depth: paper and texture at the back,
 * the orbit and the seal in the middle, the type and the field at the front.
 * Scrolling separates them, which is the whole effect.
 *
 * The headline arrives line by line from under a mask, because the sentence is
 * the argument and it should land like one.
 */

import { useEffect, useRef } from "react";

import { asset } from "../lib/asset";
import { gsap, prefersReduced, scrollTo } from "../lib/scroll";
import { useMagnetic } from "../lib/fx";
import { Cow, Doodle, Halftone, Mark, Paper as Grid, Pin, Ring, Rosette, Spark, Splat } from "./Marks";
import { Peel } from "./Kit";
import type { View } from "./Nav";

/** Four we would hand somebody first. Each is in the snapshot. */
const TRY: [string, string][] = [
  ["AVUS", "the core"],
  ["IBTM", "dated 2033"],
  ["NVDA", "one name"],
  ["SGOV", "dry powder"],
];

export default function Hero({
  go, hunt, setHunt, version,
}: {
  go: (v: View, ticker?: string) => void;
  hunt: string;
  setHunt: (v: string) => void;
  version: string;
}) {
  const root = useRef<HTMLElement>(null);
  const goBtn = useMagnetic<HTMLButtonElement>(0.4);

  useEffect(() => {
    const el = root.current;
    if (!el) return;

    const ctx = gsap.context(() => {
      const lines = el.querySelectorAll<HTMLElement>(".hero-h .ln span");

      if (prefersReduced()) {
        gsap.set([".hero-h .ln span", ".hero-rise"], { yPercent: 0, opacity: 1, y: 0 });
        el.querySelector(".hero-h")?.classList.add("is-shown");
        return;
      }

      // The opening. Everything is already in place behind the loader, so this
      // plays into a page the reader is looking at rather than at a blank one.
      const intro = gsap.timeline({
        delay: 0.15,
        // The line windows stay closed only while the words are climbing into
        // them. Left closed, they crop the drawn ring that overhangs the type.
        onComplete: () => el.querySelector(".hero-h")?.classList.add("is-shown"),
      });
      intro
        .from(".hero-cred > *", {
          y: 24, opacity: 0, duration: 0.8, stagger: 0.08, ease: "expo.out",
        })
        .fromTo(lines,
          { yPercent: 115, opacity: 0, rotate: 2.5 },
          { yPercent: 0, opacity: 1, rotate: 0, duration: 1.25, stagger: 0.085, ease: "expo.out" },
          "-=0.5")
        .from(".hero-rise", {
          y: 36, opacity: 0, duration: 1, stagger: 0.09, ease: "expo.out",
        }, "-=0.85")
        .from(".hero-stage", {
          scale: 0.86, opacity: 0, duration: 1.5, ease: "expo.out",
        }, "-=1.5")
        .from(".hero-orbit", {
          scale: 0.4, opacity: 0, rotate: -40, duration: 1.8, ease: "expo.out",
        }, "-=1.3")
        .from(".hero-pol", {
          y: -40, rotate: -14, opacity: 0, duration: 1.1, ease: "back.out(1.5)",
        }, "-=1.1")
        .from(".hero-seal", {
          scale: 0, rotate: -90, duration: 1.1, ease: "back.out(2)",
        }, "-=0.9");

      // Depth. Each plane leaves at its own rate, which is what makes the
      // collage read as layers rather than as one flat picture.
      const depth = gsap.timeline({
        scrollTrigger: { trigger: el, start: "top top", end: "bottom top", scrub: 1 },
      });
      depth
        .to(".hero-bg", { yPercent: 14, ease: "none" }, 0)
        .to(".hero-stage", { yPercent: -18, scale: 1.08, ease: "none" }, 0)
        .to(".hero-pol", { yPercent: -52, rotate: 9, ease: "none" }, 0)
        .to(".hero-seal", { yPercent: -82, rotate: 38, ease: "none" }, 0)
        .to(".hero-copy", { yPercent: -8, opacity: 0.25, ease: "none" }, 0)
        .to(".hero-orbit svg", { rotate: 55, ease: "none" }, 0);
    }, el);

    return () => ctx.revert();
  }, []);

  return (
    <section className="band band-paper hero" ref={root}>
      <div className="hero-bg" aria-hidden="true">
        <Grid kind="dot" size={26} color="rgba(193,84,61,0.14)" className="hero-grid" />
        <Halftone className="hero-dots" color="var(--rose-dk)" opacity={0.16} size={11} />
        <Splat size={190} seed={7} color="var(--gold)" opacity={0.13} style={{ top: "4%", left: "-6%" }} />
        <Splat size={120} seed={19} color="var(--sage)" opacity={0.11} style={{ bottom: "8%", right: "2%" }} />
        <Splat size={90} seed={31} color="var(--rose)" opacity={0.1} style={{ top: "52%", left: "38%" }} />
      </div>

      <div className="wrap hero-in">
        <div className="hero-copy">
          <div className="hero-cred">
            <Peel tone="paper" rotate={-2.4}>Wharton GHSIC · 2026 / 27</Peel>
            <Peel tone="gold" rotate={1.8}>{version}</Peel>
          </div>

          <h1 className="hero-h">
            <span className="ln"><span>The cow</span></span>
            <span className="ln"><span>doesn't care</span></span>
            <span className="ln">
              <span>
                how <i className="ring-host"><em>good</em><Ring seed={4} /></i> it is.
              </span>
            </span>
          </h1>

          <p className="lede hero-lede hero-rise">
            It cares whether it still pays her <Mark color="var(--gold-hi)">$50,000 in 2036.</Mark>{" "}
            So everything is scored twice, and her half weighs more.
          </p>

          <form
            className="hunt hero-rise"
            onSubmit={(e) => { e.preventDefault(); if (hunt.trim()) go("score", hunt.trim().toUpperCase()); }}
          >
            <label className="hunt-f">
              <span className="hunt-k">Ticker</span>
              <input
                value={hunt}
                onChange={(e) => setHunt(e.target.value.toUpperCase())}
                placeholder="AVUS"
                spellCheck={false}
                autoComplete="off"
                maxLength={24}
                aria-label="Ticker to score"
              />
            </label>
            <button className="hunt-go" type="submit" ref={goBtn} data-cursor="score it">
              <span>Score it</span>
              <svg viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="2.4" aria-hidden="true">
                <path d="M2.5 9h12M10 4l5 5-5 5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
          </form>

          <div className="tries hero-rise">
            <span className="tries-k">Or one of ours</span>
            {TRY.map(([t, why], i) => (
              <button key={t} className="tryk" data-cursor={t} onClick={() => go("score", t)}
                      style={{ ["--rot" as string]: `${(i % 2 ? 1 : -1) * 1.4}deg` }}>
                <b className="num">{t}</b>
                <i>{why}</i>
              </button>
            ))}
          </div>

          <button className="cover-alt hero-rise" onClick={() => scrollTo("#client")}>
            <Doodle name="arrowCurl" size={22} color="var(--ink-4)" />
            Meet Laura first
          </button>
        </div>

        <div className="hero-stage">
          <div className="hero-orbit" aria-hidden="true">
            <svg viewBox="0 0 400 400">
              <ellipse cx="200" cy="200" rx="188" ry="74" fill="none" stroke="var(--gold)" strokeWidth="2.5" />
            </svg>
          </div>
          <div className="hero-orbit hero-orbit-2" aria-hidden="true">
            <svg viewBox="0 0 400 400">
              <ellipse cx="200" cy="200" rx="172" ry="58" fill="none" stroke="var(--rose-dk)"
                       strokeWidth="1.6" strokeDasharray="5 9" />
            </svg>
          </div>

          <div className="hero-cow"><Cow size={340} /></div>

          <div className="hero-pol">
            <img src={asset("brand/laura-cutout.png")} alt="Laura Gao" />
            <span className="pol-cap">the client</span>
            <Pin size={24} color="var(--red)" style={{ top: -14, left: "50%", marginLeft: -12 }} />
          </div>

          <div className="hero-seal">
            <Rosette size={126} fill="var(--gold)">
              <span className="rz-1">NO</span>
              <span className="rz-2">VIBES</span>
            </Rosette>
          </div>

          <Spark size={32} className="hero-sp1 twinkle" />
          <Spark size={20} className="hero-sp2 twinkle" color="var(--rose-dk)" />
          <Spark size={24} className="hero-sp3 twinkle" color="var(--sage-dk)" />
        </div>
      </div>

      <button className="hero-scroll" onClick={() => scrollTo("#client")} aria-label="Keep reading">
        <span className="hero-scroll-r"><i /></span>
        <em>scroll</em>
      </button>
    </section>
  );
}
