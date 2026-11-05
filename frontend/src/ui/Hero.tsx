/* The cover.
 *
 * Dark, because the rest of the page is cream and a cover has to be the thing
 * you remember. The medallion turning at the centre is real geometry under
 * real light, so the depth is actual depth: the collage planes in front of it
 * and the bloom behind it move at their own rates and the object sits inside
 * that space rather than on top of a picture of it.
 *
 * The headline arrives line by line from under a mask, because the sentence is
 * the argument and it should land like one.
 */

import { Suspense, lazy, useEffect, useRef } from "react";

import { asset } from "../lib/asset";
import { gsap, prefersReduced, scrollTo } from "../lib/scroll";
import { useMagnetic } from "../lib/fx";
import { Doodle, Halftone, Mark, Pin, Ring, Rosette, Spark } from "./Marks";
import { Peel } from "./Kit";
// three is around half a megabyte and nothing on the page depends on it, so
// it is fetched after the cover has already painted. Until it lands the hero
// is the collage and the bloom, which is a finished picture on its own.
const Stage3D = lazy(() => import("./Stage3D"));
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
        .from(".hero-glow", { scale: 0.4, opacity: 0, duration: 2.2, ease: "expo.out" }, 0)
        .from(".hero-cred > *", {
          y: 24, opacity: 0, duration: 0.8, stagger: 0.08, ease: "expo.out",
        }, 0.1)
        .fromTo(lines,
          { yPercent: 115, opacity: 0, rotate: 2.5 },
          { yPercent: 0, opacity: 1, rotate: 0, duration: 1.25, stagger: 0.085, ease: "expo.out" },
          "-=0.5")
        .from(".hero-rise", {
          y: 36, opacity: 0, duration: 1, stagger: 0.09, ease: "expo.out",
        }, "-=0.85")
        .from(".hero-pol", {
          y: -50, rotate: -14, opacity: 0, duration: 1.2, ease: "back.out(1.5)",
        }, "-=1.1")
        .from(".hero-seal", {
          scale: 0, rotate: -90, duration: 1.1, ease: "back.out(2)",
        }, "-=0.9")
        .from(".hero-rule i", {
          scaleX: 0, duration: 1.1, stagger: 0.06, ease: "expo.out", transformOrigin: "left",
        }, "-=1");

      // Depth. Each plane leaves at its own rate, which is what makes the
      // cover read as layers rather than as one flat picture.
      const depth = gsap.timeline({
        scrollTrigger: { trigger: el, start: "top top", end: "bottom top", scrub: 1 },
      });
      depth
        .to(".hero-grain", { yPercent: 16, ease: "none" }, 0)
        .to(".hero-glow", { scale: 1.5, opacity: 0.35, ease: "none" }, 0)
        .to(".hero-pol", { yPercent: -92, rotate: 11, ease: "none" }, 0)
        .to(".hero-seal", { yPercent: -140, rotate: 52, ease: "none" }, 0)
        .to(".hero-copy", { yPercent: -12, opacity: 0.12, ease: "none" }, 0);
    }, el);

    return () => ctx.revert();
  }, []);

  return (
    <section className="band band-night hero" ref={root}>
      <div className="hero-bg" aria-hidden="true">
        <div className="hero-glow" />
        <div className="hero-glow hero-glow-2" />
        <Halftone className="hero-grain" color="var(--gold)" opacity={0.1} size={13} />
        <div className="hero-vig" />
      </div>

      <Suspense fallback={null}><Stage3D /></Suspense>

      <div className="wrap hero-in">
        <div className="hero-copy">
          <div className="hero-cred">
            <Peel tone="night" rotate={-2.4}>Wharton GHSIC · 2026 / 27</Peel>
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
            It cares whether it still pays her <Mark color="var(--gold)">$50,000 in 2036.</Mark>{" "}
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
            <Doodle name="arrowCurl" size={22} color="var(--gold)" />
            Meet Laura first
          </button>
        </div>

        <div className="hero-stage">
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

          <Spark size={32} className="hero-sp1 twinkle" color="var(--gold-hi)" />
          <Spark size={20} className="hero-sp2 twinkle" color="var(--rose)" />
          <Spark size={24} className="hero-sp3 twinkle" color="var(--gold)" />
        </div>
      </div>

      <div className="hero-rule" aria-hidden="true">
        <i /><i /><i /><i /><i /><i /><i /><i />
      </div>

      <button className="hero-scroll" onClick={() => scrollTo("#client")} aria-label="Keep reading">
        <span className="hero-scroll-r"><i /></span>
        <em>scroll</em>
      </button>
    </section>
  );
}
