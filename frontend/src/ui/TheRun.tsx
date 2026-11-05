/* The run.
 *
 * Everywhere else the page describes the framework. Here it executes it: one
 * real candidate is pushed through the engine a stage at a time while the
 * section is pinned, and the reader's scroll is the clock.
 *
 * The depth is real depth. The stage holds a perspective and each stage of the
 * run arrives from far behind the screen and leaves past the reader's shoulder,
 * so the sequence is a corridor rather than a stack of cross-fades. Nothing is
 * decorative: the thing moving toward you is the candidate, and what changes on
 * it is what the engine just worked out.
 *
 * Every number is read out of the shipped snapshot rather than typed here, so
 * this cannot drift away from what the engine actually returned.
 */

import { useEffect, useRef, useState } from "react";

import { asset } from "../lib/asset";
import { gsap, prefersReduced } from "../lib/scroll";

type Run = {
  ticker: string;
  name: string;
  role_label: string;
  role_description: string;
  asset_type_label: string;
  scores: { security_quality: number; laura_fit: number; composite: number; data_confidence: number };
  signal: { label: string; meaning: string };
  red_gate: { status: string; summary: string };
  risk_state: { state: string; reason: string };
};

const STAGES = 5;

export default function TheRun() {
  const root = useRef<HTMLElement>(null);
  const [run, setRun] = useState<Run | null>(null);

  useEffect(() => {
    let alive = true;
    fetch(asset("data/eval/AVUS.json"))
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => { if (alive && d) setRun(d as Run); })
      .catch(() => {});
    return () => { alive = false; };
  }, []);

  useEffect(() => {
    const el = root.current;
    if (!el || !run) return;

    // Without the pin this is five short panels stacked in source order, which
    // is a readable fallback and the only sane thing to do on a thumb.
    const mm = gsap.matchMedia();

    mm.add("(min-width: 1000px) and (prefers-reduced-motion: no-preference)", () => {
      const slides = gsap.utils.toArray<HTMLElement>(".run-slide", el);
      const ticks = gsap.utils.toArray<HTMLElement>(".run-tick", el);

      const tl = gsap.timeline({
        scrollTrigger: {
          trigger: el,
          start: "top top",
          end: () => `+=${window.innerHeight * (STAGES - 0.2)}`,
          pin: ".run-sticky",
          scrub: 0.8,
          anticipatePin: 1,
          invalidateOnRefresh: true,
        },
      });

      slides.forEach((slide, i) => {
        const at = i;

        // Arriving: out of the dark, from a long way back.
        if (i > 0) {
          tl.fromTo(slide,
            { z: -1500, opacity: 0, rotateX: 14, filter: "blur(12px)" },
            { z: 0, opacity: 1, rotateX: 0, filter: "blur(0px)", duration: 0.55, ease: "power2.out" },
            at - 0.5);
        } else {
          tl.set(slide, { z: 0, opacity: 1, rotateX: 0, filter: "blur(0px)" }, 0);
        }

        // Leaving: past the reader, not fading on the spot.
        if (i < STAGES - 1) {
          tl.to(slide,
            { z: 760, opacity: 0, rotateX: -12, filter: "blur(14px)", duration: 0.55, ease: "power2.in" },
            at + 0.5);
        }
      });

      // The spine on the left reports which stage is live. Derived from the
      // timeline's own position on every update rather than from per-tick
      // callbacks: a scrubbed timeline can jump straight past a zero-length
      // tween without ever firing it, which left the spine showing every
      // stage lit at once.
      const lightSpine = () => {
        // Read off the slides themselves. Deriving the index from the
        // timeline's clock meant guessing how its duration maps to stages, and
        // the guess was two stages out; the brightest slide is by definition
        // the one the reader is looking at.
        let at = 0;
        let best = -1;
        slides.forEach((slide, i) => {
          const o = Number(gsap.getProperty(slide, "opacity"));
          if (o > best) { best = o; at = i; }
        });
        ticks.forEach((tick, i) => tick.classList.toggle("is-on", i === at));
      };
      tl.eventCallback("onUpdate", lightSpine);
      lightSpine();

      // The counters only run on the stage that shows them, and they are driven
      // by the same scrub, so dragging backwards counts back down.
      const counters = gsap.utils.toArray<HTMLElement>("[data-count]", el);
      counters.forEach((node) => {
        const to = Number(node.dataset.count);
        const stage = Number(node.dataset.stage ?? 3);
        const v = { n: 0 };
        tl.to(v, {
          n: to, duration: 0.5, ease: "power1.out",
          onUpdate: () => { node.textContent = v.n.toFixed(1); },
        }, stage - 0.35);
      });

      // The candidate's own card rides the whole run, turning as it goes.
      tl.fromTo(".run-chip",
        { rotateY: -24, z: -140 },
        { rotateY: 24, z: 40, ease: "none", duration: STAGES - 1 }, 0);

      return () => { tl.scrollTrigger?.kill(); tl.kill(); };
    });

    return () => mm.revert();
  }, [run]);

  if (!run) return <section className="band band-night run run-wait" aria-hidden="true" />;

  const sq = run.scores.security_quality;
  const fit = run.scores.laura_fit;
  const comp = run.scores.composite;

  return (
    <section className="band band-night run" ref={root} id="engine">
      <div className="run-sticky">
        <div className="run-wash" aria-hidden="true" />

        <ol className="run-spine" aria-hidden="true">
          {["Arrives", "Gets a job", "Red Gate", "Scored twice", "Combined"].map((s, i) => (
            <li key={s} className={`run-tick${i === 0 ? " is-on" : ""}`}>
              <i /><span>{s}</span>
            </li>
          ))}
        </ol>

        <div className="run-head">
          <span className="tag">The engine, running</span>
          <p className="run-sub">One real candidate, one stage at a time. Scroll.</p>
        </div>

        <div className="run-stage">
          {/* 1 */}
          <article className="run-slide">
            <span className="run-step num">01</span>
            <h3 className="run-h">A ticker arrives.</h3>
            <div className="run-chip">
              <b className="num">{run.ticker}</b>
              <span>{run.name}</span>
              <i>{run.asset_type_label}</i>
            </div>
            <p className="run-say">Nothing is known about it yet. Nothing is assumed.</p>
          </article>

          {/* 2 */}
          <article className="run-slide">
            <span className="run-step num">02</span>
            <h3 className="run-h">It is given a job.</h3>
            <div className="run-job">
              <b className="num">{run.role_label}</b>
              <p>{run.role_description}</p>
            </div>
            <p className="run-say">
              The job picks the model and the weights. Without one the engine refuses to score at all.
            </p>
          </article>

          {/* 3 */}
          <article className="run-slide">
            <span className="run-step num">03</span>
            <h3 className="run-h">The Red Gate runs first.</h3>
            <div className={`run-gate run-gate-${run.red_gate.status.toLowerCase()}`}>
              <b>{run.red_gate.status}</b>
            </div>
            <p className="run-say">{run.red_gate.summary}</p>
            <p className="run-fine">
              A single hard condition. It runs before any weight is applied, and failing it ends the
              run whatever the scores would have been.
            </p>
          </article>

          {/* 4 */}
          <article className="run-slide">
            <span className="run-step num">04</span>
            <h3 className="run-h">Then it is scored twice.</h3>
            <div className="run-pair">
              <div className="run-score run-score-q">
                <b className="num" data-count={sq} data-stage="3">0.0</b>
                <span>Is it any good</span>
                <i>45% of the composite</i>
              </div>
              <div className="run-score run-score-f">
                <b className="num" data-count={fit} data-stage="3">0.0</b>
                <span>Is it good for her</span>
                <i>55% of the composite</i>
              </div>
            </div>
            <p className="run-say">
              The same security, measured against two different questions. Neither answers the other.
            </p>
          </article>

          {/* 5 */}
          <article className="run-slide">
            <span className="run-step num">05</span>
            <h3 className="run-h">Combined, tilted toward her.</h3>
            <div className="run-out">
              <b className="num" data-count={comp} data-stage="4">0.0</b>
              <span className="run-sig">{run.signal.label}</span>
            </div>
            <p className="run-say">{run.signal.meaning}</p>
            <p className="run-fine">
              A geometric mean, not an average. A high quality score cannot buy its way out of a poor
              fit, because multiplying by a small number stays small.
            </p>
          </article>
        </div>
      </div>
    </section>
  );
}
