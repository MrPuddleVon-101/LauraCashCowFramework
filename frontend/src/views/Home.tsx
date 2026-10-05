import { asset } from "../lib/asset";
import { useEffect, useState } from "react";
import { api, fmtMoney } from "../api";
import { useDrift, useTilt } from "../lib/motion";
import { LadderChart } from "../ui/Charts";
import { Btn, Fig, Marquee, Note, Paper, Working } from "../ui/Kit";
import { Arrow, Cow, Halftone, Ring, Spark, Tear, Underline } from "../ui/Marks";
import Engine from "./Engine";
import type { View } from "../ui/Nav";

/* --- the four facts -------------------------------------------------------- */

type Card = {
  k: string;
  kind: "Case study" | "Our call";
  label: string;
  fig: string;
  figNote: string;
  title: string;
  lede: string;
  body: string[];
  rows: [string, string][];
  photo?: string;
  tint: string;
};

const CARDS: Card[] = [
  {
    k: "client", kind: "Case study", label: "Who", fig: "1", figNote: "person, and she is specific",
    title: "Laura Gao", tint: "#8e4f86",
    photo: asset("brand/laura-books.webp"),
    lede: "Cartoonist, entrepreneur, and the reason the second score exists at all.",
    body: [
      "Wuhan, then Texas, then Wharton in 2018 for Statistics and Information Decisions Management. She wrote The Wuhan I Know in 2020, then Messy Roots, a graphic memoir that sells well and gets taught in classrooms.",
      "None of that tells us a thing about what she should own. The framework scores the goals she actually stated, not her biography, which is why mission fit is capped at five points out of a hundred and sits at a neutral 50 unless she says otherwise.",
    ],
    rows: [["Wharton", "2018, Statistics"], ["Teaches", "California College of the Arts"], ["Mission fit", "capped at 5 points"]],
  },
  {
    k: "in", kind: "Case study", label: "In", fig: "$450k", figNote: "and then the tap closes",
    title: "Two cheques, six years", tint: "var(--sage-dk)",
    photo: asset("brand/laura-outdoor.webp"),
    lede: "$300,000 at the start of 2027. $150,000 at the start of 2028. That is the lot.",
    body: [
      "Nothing goes in after that and nothing comes out before 2033. Her living costs are paid from somewhere else entirely.",
      "Six years is the whole runway. Long enough that equity is worth owning, short enough that a bad run at the end cannot simply be waited out.",
    ],
    rows: [["2027", "$300,000"], ["2028", "$150,000"], ["Withdrawals before 2033", "none"]],
  },
  {
    k: "out", kind: "Case study", label: "Out", fig: "$500k", figNote: "ten payments, no wiggle room",
    title: "$50,000 a year, 2033 to 2042", tint: "var(--rose-dk)",
    lede: "Due at the start of every year. All ten of them have to land.",
    body: [
      "Half a million in cash terms, not inflation adjusted, because the case study fixes it. Co-sponsors, grants and programme fees are nice to have and cannot be counted on.",
      "This is the whole reason the framework keeps covered and matched apart. A healthy equity portfolio is not the same thing as a Treasury that matures on the morning the money is due.",
    ],
    rows: [["Every year", "$50,000"], ["First", "2033"], ["Last", "2042"], ["Matched so far", "2 of 10"]],
  },
  {
    k: "risk", kind: "Our call", label: "Nerve", fig: "95%", figNote: "the floor we will not go under",
    title: "Brave is not the same as able", tint: "#3b7390",
    lede: "Laura takes real risks with her career. The dollar owed in 2034 cannot.",
    body: [
      "Capacity is not one number. Growth money years from being spent can take a 30% hit and come back. A dollar already promised to the 2034 payment has almost no room at all.",
      "So the engine runs in three states. In protection mode every downside part of the fit score is weighted 1.35 times harder. The behaviour changes with arithmetic, not with a paragraph telling you it does.",
    ],
    rows: [["Willingness", "high"], ["Capacity", "depends on the dollar"], ["Protection mode", "downside × 1.35"]],
  },
];

/* --- what each score looks at ---------------------------------------------- */

const QUALITY: [string, string][] = [
  ["Is the business any good", "return on equity, free cash flow margin, how fast revenue actually grows"],
  ["Is it priced sanely", "earnings and cash flow multiples against its own sector, not against the market"],
  ["What does owning it cost", "expense ratio, bid to ask spread, turnover inside the fund"],
  ["Can you get out", "dollar volume, fund size, how wide the spread goes on a bad day"],
  ["How concentrated is it", "top ten weight, sector and country Herfindahl, effective holdings"],
  ["How has it behaved", "volatility, beta, worst drawdown, return per unit of risk"],
];

const FIT: [string, string][] = [
  ["Can it pay a dated bill", "does it mature when the money is due, or is its 2034 price a guess"],
  ["Does it survive her runway", "six years to 2033, and a bad sequence at the end cannot be waited out"],
  ["What does it add", "look through to the companies inside, then check what she already owns"],
  ["What happens when it breaks", "drawdown behaviour, weighted harder the closer the money is to being spent"],
  ["Could she sell it fast", "if the ladder needs repairing in a hurry"],
  ["Does it clash with her", "capped at five points, and neutral unless she has told us something"],
];

const REFUSES: string[] = [
  "Score anything before it has been given a job to do.",
  "Let a big composite talk its way past the Red Gate.",
  "Call a perpetual bond fund a liability matcher. Its 2034 price is a guess.",
  "Quietly hand a missing metric's weight to the metrics next to it.",
  "Guess at Laura's politics, ethics or taste.",
  "Discount a 2042 payment at the same rate as a 2033 one.",
  "Rewrite last month's evaluation because the price went up.",
];

const SOURCES: [string, string, string, string][] = [
  ["1,613", "registrants", "SEC EDGAR XBRL, US GAAP and IFRS. Every percentile runs against the whole universe above $1bn revenue, not a hand picked set of five lookalikes.", "1"],
  ["Live", "prices and spreads", "Nasdaq market data. Quote, bid, ask and the spread in basis points, with the as-of stamped on the row.", "1"],
  ["Daily", "yield curve", "U.S. Treasury par yields. Every payment is discounted at the rate for its own maturity.", "1"],
  ["By hand", "fund factsheets", "Holdings, fees and maturity structure typed up from the issuer. Tier 2 on purpose, and every row carries the URL to check it against.", "2"],
  ["None", "analyst estimates", "Not wired in. Anything that would need them reads as missing and is charged to data confidence rather than quietly filled in.", "0"],
];

type Policy = {
  green_min_sqs: number; green_min_ccs: number; green_min_dcs: number;
  amber_plus_min_ccs: number; amber_plus_min_component: number;
  amber_min_ccs: number; red_max_sqs: number; insufficient_data_dcs: number;
};

/** Quoted live from the locked framework, so the page cannot drift from the engine. */
function ladderKey(p: Policy | null): [string, string, string, string][] {
  const n = (v: number | undefined, fallback: number) => (v ?? fallback).toFixed(0);
  return [
    ["Green", "green",
      `Gate clear, and quality, fit and composite all reach ${n(p?.green_min_ccs, 85)}`,
      "We would actually buy this."],
    ["Amber plus", "amberplus",
      `Composite over ${n(p?.amber_plus_min_ccs, 78)} with both scores above ${n(p?.amber_plus_min_component, 72)}`,
      "Strong. Someone has to argue for it."],
    ["Amber", "amber",
      `Clears the floor but not the bar`,
      "Useful, with weaknesses we can name."],
    ["Red", "red",
      `Any gate failure, or either score under ${n(p?.red_max_sqs, 60)}`,
      "No. Not under these conditions."],
    ["No call", "none",
      `Data confidence under ${n(p?.insufficient_data_dcs, 70)}`,
      "We do not know enough to have an opinion."],
  ];
}

/* --- page ------------------------------------------------------------------ */

export default function Home({ go }: { go: (v: View) => void }) {
  const [open, setOpen] = useState<Card | null>(null);
  const [liab, setLiab] = useState<any>(null);
  const [policy, setPolicy] = useState<Policy | null>(null);
  const [liabErr, setLiabErr] = useState(false);
  const stage = useTilt<HTMLDivElement>(1);
  const polaroid = useDrift<HTMLDivElement>(0.18, { rotate: 2 });

  useEffect(() => {
    const k = (e: KeyboardEvent) => e.key === "Escape" && setOpen(null);
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, []);

  useEffect(() => {
    let live = true;
    api.liabilities(2027)
      .then((d) => live && setLiab(d))
      .catch(() => live && setLiabErr(true));
    api.framework()
      .then((f) => live && setPolicy(f?.policy ?? null))
      .catch(() => { /* the fallbacks match the locked framework */ });
    return () => { live = false; };
  }, []);

  return (
    <>
      {/* ---- cover ---- */}
      <section className="band band-paper cover">
        <Halftone className="cover-dots" color="var(--rose-dk)" opacity={0.2} size={11} />
        <div className="wrap cover-in">
          <div className="cover-copy">
            <span className="tag">Wharton Global High School Investment Competition,{" "}2026{" "}/{" "}27</span>

            <h1 className="cover-h">
              <span className="l1">The cow doesn't care</span>
              <span className="l2">how <span className="ring-host"><em>good</em><Ring seed={4} /></span> it is.</span>
            </h1>

            <p className="lede cover-lede">
              It cares whether the thing still pays Laura $50,000 in 2036. So every
              candidate gets scored twice, and her half counts for more.
            </p>

            <div className="cover-cta">
              <Btn kind="go" size="lg" arrow onClick={() => go("score")}>Score a ticker</Btn>
              <Btn size="lg" onClick={() => document.getElementById("client")?.scrollIntoView({ behavior: "smooth" })}>
                Meet Laura first
              </Btn>
            </div>

            <span className="cover-hint">
              <Arrow w={76} h={34} color="var(--ink-3)" rotate={-152} />
              type a ticker, get a verdict
            </span>
          </div>

          <div className="cover-stage" ref={stage}>
            <div className="cover-orbit" aria-hidden="true">
              <svg viewBox="0 0 400 400">
                <ellipse cx="200" cy="200" rx="188" ry="74" fill="none" stroke="var(--gold)" strokeWidth="2.5" />
              </svg>
            </div>
            <div className="cover-orbit cover-orbit-2" aria-hidden="true">
              <svg viewBox="0 0 400 400">
                <ellipse cx="200" cy="200" rx="172" ry="58" fill="none" stroke="var(--rose-dk)"
                         strokeWidth="1.6" strokeDasharray="5 9" />
              </svg>
            </div>

            <div className="cover-stack" ref={polaroid}>
              <div className="pol pol-back"><img src={asset("brand/laura-books.webp")} alt="" /></div>
              <div className="pol pol-front">
                <img src={asset("brand/laura-cutout.png")} alt="Laura Gao" />
                <span className="pol-cap">the client</span>
                <i className="tape tape-left" aria-hidden="true" />
              </div>
            </div>

            <div className="cover-cow"><Cow size={300} /></div>
            <Spark size={30} className="cover-sp1 twinkle" />
            <Spark size={19} className="cover-sp2 twinkle" color="var(--rose-dk)" />
            <Spark size={23} className="cover-sp3 twinkle" color="var(--sage-dk)" />
            <Spark size={15} className="cover-sp4 twinkle" color="#8e4f86" />
          </div>
        </div>

        <div className="wrap figstrip">
          {([
            [450000, "$", "", "she puts in", "two cheques, 2027 and 2028, then nothing"],
            [500000, "$", "", "she owes", "ten payments, 2033 through 2042"],
            [1613, "", "", "companies to beat", "the whole SEC universe, not five lookalikes"],
            [95, "", "%", "certainty, minimum", "the funding floor we will not go under"],
          ] as [number, string, string, string, string][]).map(([v, pre, suf, l, s2], i) => (
            <div className="fs" key={l} data-anim="rise" style={{ ["--delay" as string]: `${i * 90}ms` }}>
              <Fig className="fs-f" value={v} prefix={pre} suffix={suf} ms={1300 + i * 120} />
              <span className="fs-l">{l}</span>
              <span className="fs-s">{s2}</span>
            </div>
          ))}
        </div>
      </section>

      <Tear fill="var(--ink)" seed={41} />

      {/* ---- ticker ---- */}
      <section className="band band-ink strip">
        <Marquee speed={42}>
          {["Scored twice", "Green is rare", "The gate cannot be outscored", "Sources or it doesn't ship",
            "AVUS", "VXUS", "IBTM", "SGOV", "NVDA", "SCHD", "A job before a number"].map((t, i) => (
            <span className="strip-i" key={t + i}>
              {t}
              <Spark size={13} color="var(--gold)" />
            </span>
          ))}
        </Marquee>
      </section>

      <Tear fill="var(--rose)" seed={17} />

      {/* ---- the client ---- */}
      <section className="band band-rose brief" id="client">
        <div className="wrap">
          <header className="sec-head">
            <span className="tag">The client</span>
            <h2>Meet Laura. She has a deadline.</h2>
            <p className="lede">Four facts, and everything else follows from them. Pick one up.</p>
          </header>

          <div className="cards">
            {CARDS.map((c, i) => (
              <Paper key={c.k} seed={i * 7 + 2} className="card" delay={i * 70} onClick={() => setOpen(c)}
                     tape={i % 2 ? "right" : "left"}>
                <span className="card-k">{c.label}</span>
                <span className="card-f serif" style={{ color: c.tint }}>{c.fig}</span>
                <span className="card-fn">{c.figNote}</span>
                <span className="card-t">{c.title}</span>
                <span className="card-l">{c.lede}</span>
                <span className="card-go">
                  Read it
                  <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M2 8h11M9 4l4 4-4 4" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </span>
              </Paper>
            ))}
          </div>
        </div>
      </section>

      <Tear fill="var(--paper)" seed={53} />

      {/* ---- the ten payments ---- */}
      <section className="band band-paper payments">
        <div className="wrap">
          <header className="sec-head sec-head-row">
            <div>
              <span className="tag">The deadline, drawn out</span>
              <h2>Ten bills, and what they cost today</h2>
            </div>
            <p className="fine">
              Every payment is discounted at the Treasury yield for its own maturity. Later
              bills are cheaper to lock in, which is exactly why you buy the back of the
              ladder first.
            </p>
          </header>

          {liabErr && <Note tone="warn">The engine is not answering, so the live figures are missing here. The ten payments are still $50,000 each from 2033 to 2042.</Note>}
          {!liab && !liabErr && <Working what="Pricing ten payments off the live curve" />}

          {liab && (
            <>
              <LadderChart payments={liab.payments} />

              <div className="pay-figs">
                <div className="pf">
                  <span className="pf-v serif">{fmtMoney(liab.cost_to_secure_remaining)}</span>
                  <span className="pf-k">locks in everything still unmatched</span>
                </div>
                <div className="pf">
                  <span className="pf-v serif">{liab.matched_count}<i> of 10</i></span>
                  <span className="pf-k">already sitting on a dated instrument</span>
                </div>
                <div className="pf">
                  <span className="pf-v serif num">{liab.curve.as_of ?? "·"}</span>
                  <span className="pf-k">the curve those prices came off</span>
                </div>
              </div>

              {liab.coverage?.finding && (
                <div className="gapblock">
                  <div className="gap-head">
                    <Spark size={22} color="var(--red)" />
                    <h3>And there is a hole after 2035</h3>
                  </div>
                  <p>{liab.coverage.finding}</p>
                  <div className="gap-years">
                    {Array.from({ length: 10 }, (_, i) => 2033 + i).map((y) => (
                      <span key={y} className="gy num"
                            data-gap={(liab.coverage.years_requiring_direct_treasuries ?? []).includes(y) || undefined}>
                        {y}
                      </span>
                    ))}
                  </div>
                  <p className="fine">
                    Solid years can be matched with a dated fund that already exists today.
                    The hatched ones need individual Treasuries or STRIPS, bought direct.
                  </p>
                </div>
              )}
            </>
          )}
        </div>
      </section>

      <Tear fill="var(--paper-lo)" seed={29} />

      {/* ---- the two scores ---- */}
      <section className="band band-deep scores" id="scores">
        <div className="wrap">
          <header className="sec-head">
            <span className="tag">The two scores</span>
            <h2>Two questions. Neither one gets to answer the other.</h2>
            <p className="lede">
              Most screens ask the first and stop. That is how you end up holding a
              magnificent company that cannot pay a bill in 2036.
            </p>
          </header>

          <div className="duo">
            <article className="duo-card duo-q" data-anim="rise">
              <span className="duo-n num">01</span>
              <h3>Is it any good?</h3>
              <p className="duo-l">
                Security quality. The same question you would ask about anything, answered
                against 1,613 SEC registrants rather than five companies somebody chose.
              </p>
              <ul className="duo-list">
                {QUALITY.map(([k, v]) => (
                  <li key={k}><b>{k}</b><span>{v}</span></li>
                ))}
              </ul>
              <span className="duo-w num">45% of the composite</span>
            </article>

            <article className="duo-card duo-f" data-anim="rise" style={{ ["--delay" as string]: "120ms" }}>
              <span className="duo-n num">02</span>
              <h3>Is it good for her?</h3>
              <p className="duo-l">
                Laura fit. The same security scores differently depending on the job it is
                being asked to do, because the job is what it has to survive.
              </p>
              <ul className="duo-list">
                {FIT.map(([k, v]) => (
                  <li key={k}><b>{k}</b><span>{v}</span></li>
                ))}
              </ul>
              <span className="duo-w num">55% of the composite</span>
            </article>
          </div>

          <div className="formula" data-anim="stamp">
            <span className="tag bare">How they combine</span>
            <p className="formula-eq num">
              composite = 100 × (<em>quality</em>/100)<sup>0.45</sup> × (<em>fit</em>/100)<sup>0.55</sup>
            </p>
            <p className="formula-say">
              A geometric mean, not an average, and tilted toward her. The difference
              matters: a 96 that suits her badly cannot buy its way out of a 60, because
              multiplying by a small number stays small. An average would have let it.
            </p>
          </div>
        </div>
      </section>

      <Tear fill="var(--ink)" seed={61} />

      {/* ---- the engine ---- */}
      <section className="band band-ink" id="engine">
        <Engine />
      </section>

      <Tear fill="var(--paper)" seed={9} />

      {/* ---- what it is allowed to say ---- */}
      <section className="band band-paper signals">
        <div className="wrap">
          <header className="sec-head">
            <span className="tag">The verdict</span>
            <h2>
              Five answers. One of them is <span className="ul-host">rare<Underline /></span>.
            </h2>
            <p className="lede">Green needs every gate at once. That is the entire point of it.</p>
          </header>

          <div className="swatches">
            {ladderKey(policy).map(([name, tone, cond, mean], i) => (
              <div className="sw" key={name} data-tone={tone} data-anim="stamp"
                   style={{ ["--delay" as string]: `${i * 80}ms`, ["--rot" as string]: `${(i % 2 ? 1 : -1) * 1.1}deg` }}>
                <span className="sw-chip" />
                <span className="sw-n">{name}</span>
                <span className="sw-c">{cond}</span>
                <span className="sw-m">{mean}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      <Tear fill="var(--paper-lo)" seed={71} />

      {/* ---- the rules ---- */}
      <section className="band band-deep rules" id="rules">
        <div className="wrap">
          <header className="sec-head">
            <span className="tag">The rules</span>
            <h2>Locked before anything was scored</h2>
            <p className="lede">
              Change a weight and you get a new version number and a full rescore. That is
              what stops a weight being nudged until a favourite wins.
            </p>
          </header>

          <div className="rules-grid">
            <div className="refuses">
              <h3>Seven things it flat out refuses to do</h3>
              <ul className="refuse-list">
                {REFUSES.map((t, i) => (
                  <li key={t} data-anim="rise" style={{ ["--delay" as string]: `${i * 55}ms` }}>
                    <svg viewBox="0 0 20 20" aria-hidden="true">
                      <path d="M4 4l12 12M16 4L4 16" fill="none" stroke="var(--red)" strokeWidth="2.8" strokeLinecap="round" />
                    </svg>
                    {t}
                  </li>
                ))}
              </ul>
            </div>

            <div className="prov">
              <h3>Where every number comes from</h3>
              {SOURCES.map(([fig, kind, note, tier], i) => (
                <div className="pv" key={kind} data-anim="rise" style={{ ["--delay" as string]: `${i * 60}ms` }}>
                  <span className="pv-v serif">{fig}</span>
                  <div>
                    <span className="pv-k">
                      {kind}
                      <i className="pv-t" data-t={tier}>{tier === "0" ? "not used" : `tier ${tier}`}</i>
                    </span>
                    <span className="pv-s">{note}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <Tear fill="var(--gold)" seed={33} />

      {/* ---- closer ---- */}
      <section className="band band-gold closer">
        <Halftone className="closer-dots" color="var(--ink)" opacity={0.11} size={10} />
        <div className="wrap closer-in">
          <h2>Go on. Throw something at it.</h2>
          <p className="lede">
            A ticker and a job. You get a verdict, the reasoning, and every source it leaned on.
          </p>
          <div className="closer-cta">
            <Btn kind="ink" size="lg" arrow onClick={() => go("score")}>Score a ticker</Btn>
          </div>
          <Cow size={150} />
        </div>
      </section>

      {/* ---- dossier ---- */}
      {open && (
        <>
          <button className="scrim" onClick={() => setOpen(null)} aria-label="Close" />
          <aside className="dossier" role="dialog" aria-label={open.title}>
            <button className="dossier-x" onClick={() => setOpen(null)} aria-label="Close">
              <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2.4">
                <path d="M5 5l10 10M15 5L5 15" strokeLinecap="round" />
              </svg>
            </button>
            <span className={`chip ${open.kind === "Case study" ? "chip-gold" : ""}`}>{open.kind}</span>
            <h2>{open.title}</h2>
            <p className="dossier-lede">{open.lede}</p>
            {open.photo && (
              <div className="dossier-pic">
                <img src={open.photo} alt="" />
              </div>
            )}
            {open.body.map((t, i) => <p key={i}>{t}</p>)}
            <dl className="dossier-rows">
              {open.rows.map(([k, v]) => (
                <div key={k}><dt>{k}</dt><dd className="num">{v}</dd></div>
              ))}
            </dl>
            <p className="fine">
              {open.kind === "Case study"
                ? "Straight from the Wharton case study. Not ours to edit."
                : "Cash Cows team policy. Editable, and editing it mints a new framework version."}
            </p>
          </aside>
        </>
      )}
    </>
  );
}
