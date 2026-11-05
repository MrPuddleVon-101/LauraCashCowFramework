/* Who we are scoring for.
 *
 * The brief further down states her position in numbers. This states her as a
 * person, because the second score is the whole argument of the framework and
 * it only makes sense once you believe there is somebody on the other end of
 * it.
 *
 * Four photographs on four planes, each leaving at its own rate, each cut in
 * from under a mask. A line of her own words runs behind them at scroll speed.
 * Nothing here is decoration: the section exists to make the 55% weighting
 * feel like a decision about a person rather than a parameter.
 */

import { useEffect, useRef } from "react";

import { asset } from "../lib/asset";
import { gsap, prefersReduced } from "../lib/scroll";
import { Doodle, Pin, Spark } from "./Marks";

type Shot = {
  src: string; alt: string; cap: string; note: string;
  depth: number;            // parallax rate, higher leaves faster
  rot: number;
};

const SHOTS: Shot[] = [
  {
    src: "brand/laura-hero.webp", alt: "Laura Gao",
    cap: "Laura Gao", note: "Wharton, 2018",
    depth: 1, rot: -2.4,
  },
  {
    src: "brand/laura-books.webp", alt: "Laura Gao with her books",
    cap: "Messy Roots", note: "taught in classrooms",
    depth: 2.1, rot: 3.1,
  },
  {
    src: "brand/laura-suit.png", alt: "Laura Gao",
    cap: "The day job", note: "and the one after it",
    depth: 1.5, rot: 2,
  },
  {
    src: "brand/laura-outdoor.webp", alt: "Laura Gao outdoors",
    cap: "2036", note: "the year that has to pay",
    depth: 2.6, rot: -3.4,
  },
];

export default function LauraFilm() {
  const root = useRef<HTMLElement>(null);

  useEffect(() => {
    const el = root.current;
    if (!el) return;
    if (prefersReduced()) return;

    const ctx = gsap.context(() => {
      // Each frame is cut in from under its own mask as it arrives, then keeps
      // drifting at its own rate for as long as the section is on screen.
      el.querySelectorAll<HTMLElement>(".film-shot").forEach((shot) => {
        const img = shot.querySelector<HTMLElement>(".film-img");
        const depth = Number(shot.dataset.depth || 1);

        gsap.fromTo(shot,
          { clipPath: "inset(0% 0% 100% 0%)", y: 70 },
          {
            clipPath: "inset(0% 0% 0% 0%)", y: 0,
            duration: 1.25, ease: "expo.out",
            scrollTrigger: { trigger: shot, start: "top 88%", once: true },
          });

        // The picture moves against its own frame, which is what sells it as a
        // window rather than a rectangle with a photo in it.
        if (img) {
          gsap.fromTo(img, { yPercent: -3.6 }, {
            yPercent: 3.6, ease: "none",
            scrollTrigger: { trigger: shot, start: "top bottom", end: "bottom top", scrub: true },
          });
        }

        gsap.to(shot, {
          yPercent: -6 * depth, ease: "none",
          scrollTrigger: { trigger: el, start: "top bottom", end: "bottom top", scrub: 1 },
        });
      });

      // Her sentence runs behind the frames, pulled along by the scroll.
      gsap.to(".film-bleed", {
        xPercent: -34, ease: "none",
        scrollTrigger: { trigger: el, start: "top bottom", end: "bottom top", scrub: 1.2 },
      });

      gsap.from(".film-h .ln span", {
        yPercent: 118, opacity: 0, duration: 1.1, stagger: 0.07, ease: "expo.out",
        scrollTrigger: { trigger: ".film-h", start: "top 86%", once: true },
      });

      gsap.from(".film-fact", {
        y: 26, opacity: 0, duration: 0.8, stagger: 0.09, ease: "expo.out",
        scrollTrigger: { trigger: ".film-facts", start: "top 86%", once: true },
      });
    }, el);

    return () => ctx.revert();
  }, []);

  return (
    <section className="band band-night film" ref={root} id="laura">
      <div className="film-bleed" aria-hidden="true">
        <span>she is one person</span>
        <span>she is one person</span>
        <span>she is one person</span>
      </div>

      <div className="wrap film-in">
        <header className="film-head">
          <span className="tag film-tag">The client</span>
          <h2 className="film-h">
            <span className="ln"><span>Everything here</span></span>
            <span className="ln"><span>is for <em>her</em>.</span></span>
          </h2>
          <p className="lede film-lede">
            A cartoonist with a lumpy income, one lump sum, and a bill that arrives
            every year from 2036. The second score exists because of her.
          </p>

          <dl className="film-facts">
            <div className="film-fact">
              <dt>In</dt>
              <dd><b className="num">$450k</b><i>once, then the tap closes</i></dd>
            </div>
            <div className="film-fact">
              <dt>Out</dt>
              <dd><b className="num">$50k</b><i>a year, from 2036</i></dd>
            </div>
            <div className="film-fact">
              <dt>Mission fit</dt>
              <dd><b className="num">5 pts</b><i>capped, and neutral by default</i></dd>
            </div>
          </dl>
        </header>

        <div className="film-wall">
          {SHOTS.map((s, i) => (
            <figure
              key={s.src}
              className={`film-shot film-shot-${i + 1}`}
              data-depth={s.depth}
              style={{ ["--rot" as string]: `${s.rot}deg` }}
            >
              <span className="film-img-w">
                <img className="film-img" src={asset(s.src)} alt={s.alt} loading="lazy" />
              </span>
              <figcaption>
                <b>{s.cap}</b>
                <i>{s.note}</i>
              </figcaption>
              {i === 0 && <Pin size={22} color="var(--gold)" style={{ top: -11, left: 18 }} />}
            </figure>
          ))}

          <Spark size={26} className="film-sp1 twinkle" color="var(--gold-hi)" />
          <Spark size={18} className="film-sp2 twinkle" color="var(--rose)" />
          <Doodle name="arrowCurl" size={44} color="var(--gold)" className="film-arrow" />
        </div>
      </div>
    </section>
  );
}
