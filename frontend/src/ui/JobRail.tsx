/* The seven jobs, as a rail you push sideways.
 *
 * The section pins and the row of cards travels across it while the page
 * scrolls. The order matters, so making the reader move through it one card at
 * a time says more than a grid of eight tiles arranged four and four.
 *
 * Below the pinning breakpoint it is an ordinary scroll-snap row, which works
 * with a thumb and needs no pinning at all.
 */

import { useEffect, useRef } from "react";

import { ScrollTrigger, gsap, prefersReduced } from "../lib/scroll";
import { useTilt3D } from "../lib/fx";
import { Doodle, Mark } from "./Marks";
import JobMark from "./JobMark";
import { Peel } from "./Kit";

const JOBS: [string, string, string, string][] = [
  ["CG", "Core growth", "gold", "The spine. Broad, boring, held the whole way."],
  ["SG", "Satellite", "rose", "One researched bet, deliberately small."],
  ["ID", "International", "sage", "Everything that is not America."],
  ["LM", "Liability matcher", "paper", "Dated at one payment. Certainty beats yield."],
  ["LR", "Liquidity", "gold", "Short, liquid, boring on purpose."],
  ["LG", "Residual growth", "sage", "Money that stays invested past 2033."],
  ["DA", "Defensive", "rose", "Ballast. Should zig when equities zag."],
];

function JobCard({ code, name, tone, what, index }: {
  code: string; name: string; tone: string; what: string; index: number;
}) {
  const stage = useTilt3D<HTMLDivElement>(10);
  return (
    <div className="rail-cell" ref={stage}>
      <article className="jobcard" data-cursor={code} data-tone={tone}>
        <div className="jobcard-top">
          {/* The code, set at the size of the card. It is the thing you track
              as the rail goes past, and it reads before the name does. The
              mark behind it is the job's mechanism, drawn in the same ink. */}
          <JobMark name={code} size={118} className="jobcard-mark" />
          <b className="jobcard-code num" aria-hidden="true">{code}</b>
          <span className="jobcard-n num">{String(index + 1).padStart(2, "0")}</span>
        </div>
        <div className="jobcard-body">
          <Peel tone={tone} rotate={0} className="jobcard-peel"><b className="num">{code}</b></Peel>
          <h3>{name}</h3>
          <p>{what}</p>
        </div>
      </article>
    </div>
  );
}

export default function JobRail() {
  const root = useRef<HTMLElement>(null);
  const track = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const section = root.current;
    const row = track.current;
    if (!section || !row) return;

    // Pinning a horizontal rail needs room to travel. On a narrow screen there
    // is none, and a thumb already swipes sideways perfectly well.
    const mm = gsap.matchMedia();
    mm.add("(min-width: 1000px) and (prefers-reduced-motion: no-preference)", () => {
      const distance = () => Math.max(0, row.scrollWidth - section.clientWidth + 120);

      const tween = gsap.to(row, {
        x: () => -distance(),
        ease: "none",
        scrollTrigger: {
          trigger: section,
          start: "top top",
          end: () => `+=${distance() + window.innerHeight * 0.4}`,
          pin: true,
          scrub: 1,
          anticipatePin: 1,
          invalidateOnRefresh: true,
        },
      });

      // The progress rule under the rail reports how far through you are.
      const bar = gsap.to(section.querySelector(".rail-bar i"), {
        scaleX: 1, ease: "none",
        scrollTrigger: {
          trigger: section, start: "top top",
          end: () => `+=${distance() + window.innerHeight * 0.4}`, scrub: true,
        },
      });

      return () => { tween.scrollTrigger?.kill(); tween.kill(); bar.scrollTrigger?.kill(); bar.kill(); };
    });

    return () => mm.revert();
  }, []);

  return (
    <section className="band band-paper jobrail" ref={root}>
      <div className="jobrail-in">
        <header className="wrap rail-head">
          <div>
            <span className="tag">Before any number</span>
            <h2>Everything gets a <Mark color="var(--sage-hi)">job</Mark> first</h2>
          </div>
          <p className="fine">
            A Treasury dated to 2034 and a growth stock are never measured against the same
            objective. The job picks the model and the weights. Without one, the whole thing
            collapses into a single league table.
          </p>
        </header>

        <div className="rail">
          <div className="rail-track" ref={track}>
            {JOBS.map(([code, name, tone, what], i) => (
              <JobCard key={code} code={code} name={name} tone={tone} what={what} index={i} />
            ))}
            <div className="rail-cell">
              <article className="jobcard jobcard-rule" data-tone="ink">
                <div className="jobcard-top">
                  <JobMark name="NO" size={118} className="jobcard-mark" />
                  <b className="jobcard-code num" aria-hidden="true">00</b>
                </div>
                <div className="jobcard-body">
                  <h3>No job, no score</h3>
                  <p>The engine refuses a ticker it has not been told the purpose of.</p>
                </div>
              </article>
            </div>
          </div>
        </div>

        <div className="wrap rail-foot">
          <span className="rail-bar" aria-hidden="true"><i /></span>
          <span className="rail-hint">Seven jobs, and one rule</span>
        </div>
      </div>
    </section>
  );
}
