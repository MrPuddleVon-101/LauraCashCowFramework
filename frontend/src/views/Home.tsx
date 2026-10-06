import { useEffect, useState } from "react";
import { api, snapshotMeta, type Snapshot } from "../api";
import { asset } from "../lib/asset";
import { useDrift, useTilt } from "../lib/motion";
import { Btn, Marquee, Odometer, Paper as Card, Peel, Stagger, Wobble } from "../ui/Kit";
import {
  Arrow, Cow, Doodle, Halftone, Mark, Note, Paper as Grid, Pin, Postmark,
  PriceTag, Ring, Rosette, Seam, Spark, Splat, Tear, Underline,
} from "../ui/Marks";
import Engine from "./Engine";
import type { View } from "../ui/Nav";

/* --- the four facts -------------------------------------------------------- */

type Card4 = {
  k: string; kind: "Case study" | "Our call"; label: string;
  fig: string; figNote: string; title: string; lede: string;
  body: string[]; rows: [string, string][]; photo?: string; tint: string; pin: string;
};

const CARDS: Card4[] = [
  {
    k: "client", kind: "Case study", label: "Who", fig: "1", figNote: "person, and she is specific",
    title: "Laura Gao", tint: "#8e4f86", pin: "var(--grape)",
    photo: asset("brand/laura-books.webp"),
    lede: "Cartoonist, entrepreneur, and the reason the second score exists at all.",
    body: [
      "Wuhan, then Texas, then Wharton in 2018 for Statistics and Information Decisions Management. She wrote The Wuhan I Know in 2020, then Messy Roots, a graphic memoir that sells well and gets taught in classrooms.",
      "None of that tells us a thing about what she should own. The framework scores the goals she actually stated, not her biography, which is why mission fit is capped at five points out of a hundred and sits neutral unless she says otherwise.",
    ],
    rows: [["Wharton", "2018, Statistics"], ["Teaches", "California College of the Arts"], ["Mission fit", "capped at 5 points"]],
  },
  {
    k: "in", kind: "Case study", label: "In", fig: "$450k", figNote: "and then the tap closes",
    title: "Two cheques, six years", tint: "var(--sage-dk)", pin: "var(--sage)",
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
    title: "$50,000 a year, 2033 to 2042", tint: "var(--rose-dk)", pin: "var(--red)",
    lede: "Due at the start of every year. All ten of them have to land.",
    body: [
      "Half a million in cash terms, not inflation adjusted, because the case study fixes it. Co-sponsors, grants and programme fees are nice to have and cannot be counted on.",
      "This is the whole reason the framework keeps covered and matched apart. A healthy equity portfolio is not the same thing as a Treasury that matures before the morning the money is due.",
    ],
    rows: [["Every year", "$50,000"], ["First", "2033"], ["Last", "2042"], ["Matched so far", "2 of 10"]],
  },
  {
    k: "risk", kind: "Our call", label: "Nerve", fig: "95%", figNote: "the floor we will not go under",
    title: "Brave is not the same as able", tint: "#3b7390", pin: "var(--sky)",
    lede: "Laura takes real risks with her career. The dollar owed in 2034 cannot.",
    body: [
      "Capacity is not one number. Growth money years from being spent can take a 30% hit and come back. A dollar already promised to the 2034 payment has almost no room at all.",
      "So the engine runs in three states. In protection mode the shortfall on every downside reading is scaled 1.35 times, so the same risky holding scores worse the less capacity she has for it.",
    ],
    rows: [["Willingness", "high"], ["Capacity", "depends on the dollar"], ["Protection mode", "shortfall × 1.35"]],
  },
];

/* --- the seven jobs -------------------------------------------------------- */

const JOBS: [string, string, string, string][] = [
  ["CG", "Core growth", "gold", "The spine. Broad, boring, held the whole way."],
  ["SG", "Satellite", "rose", "One researched bet, deliberately small."],
  ["ID", "International", "sage", "Everything that is not America."],
  ["LM", "Liability matcher", "paper", "Dated at one payment. Certainty beats yield."],
  ["LR", "Liquidity", "gold", "Short, liquid, boring on purpose."],
  ["LG", "Residual growth", "sage", "Money that stays invested past 2033."],
  ["DA", "Defensive", "rose", "Ballast. Should zig when equities zag."],
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
  ["Can it pay a dated bill", "does the cash actually land before the payment, on real dates"],
  ["Does it survive her runway", "six years to 2033, and a bad sequence at the end cannot be waited out"],
  ["What does it add", "look through to the companies inside, then check what she already owns"],
  ["What happens when it breaks", "drawdown behaviour, scaled harder the closer the money is to being spent"],
  ["Could she sell it fast", "if the ladder needs repairing in a hurry"],
  ["Does it clash with her", "capped at five points, and neutral unless she has told us something"],
];

const REFUSES: [string, string][] = [
  ["Score anything before it has been given a job to do.", "check"],
  ["Let a big composite talk its way past the Red Gate.", "bolt"],
  ["Call a perpetual bond fund a liability matcher.", "cross"],
  ["Quietly hand a missing metric's weight to its neighbours.", "eye"],
  ["Guess at Laura's politics, ethics or taste.", "heart"],
  ["Discount a 2042 payment at the same rate as a 2033 one.", "coin"],
  ["Rewrite last month's evaluation because the price went up.", "spiral"],
];

const SOURCES: [string, string, string, string][] = [
  ["1,608", "registrants", "SEC EDGAR XBRL, US GAAP and IFRS. Percentiles run against the whole universe above $1bn revenue, not a hand picked set of five lookalikes.", "1"],
  ["Live", "prices and spreads", "Nasdaq market data. Quote, bid, ask and the spread in basis points, with the as-of stamped on the row.", "1"],
  ["Daily", "yield curve", "U.S. Treasury par yields. Every payment is discounted at the rate for its own maturity.", "1"],
  ["By hand", "fund factsheets", "Holdings, fees and maturity structure typed up from the issuer. Tier 2 on purpose, and every row carries the URL to check it against.", "2"],
  ["None", "analyst estimates", "Not wired in. Anything that would need them reads as missing and is charged to data confidence rather than quietly filled in.", "0"],
];

const LADDER_FALLBACK = { green: 85, ap: 78, apc: 72, red: 60, dcs: 70 };

type Policy = {
  green_min_ccs: number; amber_plus_min_ccs: number; amber_plus_min_component: number;
  red_max_sqs: number; insufficient_data_dcs: number;
};

function ladderKey(p: Policy | null): [string, string, string, string][] {
  const n = (v: number | undefined, f: number) => (v ?? f).toFixed(0);
  return [
    ["Green", "green", `Gate clear, and all three scores reach ${n(p?.green_min_ccs, LADDER_FALLBACK.green)}`, "We would actually buy this."],
    ["Amber plus", "amberplus", `Composite over ${n(p?.amber_plus_min_ccs, LADDER_FALLBACK.ap)}, both scores above ${n(p?.amber_plus_min_component, LADDER_FALLBACK.apc)}`, "Strong. Someone has to argue for it."],
    ["Amber", "amber", "Clears the floor but not the bar", "Useful, with weaknesses we can name."],
    ["Red", "red", `Any gate failure, or either score under ${n(p?.red_max_sqs, LADDER_FALLBACK.red)}`, "No. Not under these conditions."],
    ["No call", "none", `Data confidence under ${n(p?.insufficient_data_dcs, LADDER_FALLBACK.dcs)}`, "We do not know enough to have an opinion."],
  ];
}

const SIGNAL_TONE: Record<string, string> = {
  GREEN: "green", AMBER_PLUS: "amberplus", AMBER: "amber", RED: "red", INSUFFICIENT_DATA: "none",
};

/* --- page ------------------------------------------------------------------ */

export default function Home({ go }: { go: (v: View) => void }) {
  const [open, setOpen] = useState<Card4 | null>(null);
  const [policy, setPolicy] = useState<Policy | null>(null);
  const [board, setBoard] = useState<Snapshot | null>(null);
  const stage = useTilt<HTMLDivElement>(1);
  const stack = useDrift<HTMLDivElement>(0.18, { rotate: 2 });
  const badge = useDrift<HTMLDivElement>(-0.1);

  useEffect(() => {
    const k = (e: KeyboardEvent) => e.key === "Escape" && setOpen(null);
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, []);

  useEffect(() => {
    let live = true;
    api.framework().then((f) => live && setPolicy(f?.policy ?? null)).catch(() => {});
    snapshotMeta().then((m) => live && setBoard(m)).catch(() => {});
    return () => { live = false; };
  }, []);

  return (
    <>
      {/* ================= COVER ================= */}
      <section className="band band-paper cover">
        <Grid kind="dot" size={24} color="rgba(193,84,61,0.16)" className="cover-grid" />
        <Halftone className="cover-dots" color="var(--rose-dk)" opacity={0.18} size={11} />
        <Splat size={120} seed={7} color="var(--gold)" opacity={0.16} style={{ top: "6%", left: "-3%" }} />
        <Splat size={70} seed={19} color="var(--sage)" opacity={0.14} style={{ bottom: "12%", right: "4%" }} />

        <div className="wrap cover-in">
          <div className="cover-copy">
            <div className="cover-cred">
              <Peel tone="paper" rotate={-2.4}>Wharton GHSIC · 2026 / 27</Peel>
              <Peel tone="gold" rotate={1.8}>LCCF v1.2</Peel>
            </div>

            <h1 className="cover-h">
              <Stagger as="span" className="l1" text="The cow doesn't care" />
              <span className="l2">
                how <span className="ring-host"><em>good</em><Ring seed={4} /></span> it is.
              </span>
            </h1>

            <p className="lede cover-lede">
              It cares whether the thing still pays Laura <Mark color="var(--gold-hi)">$50,000 in 2036</Mark>.
              So every candidate gets scored twice, and her half counts for more.
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
              <svg viewBox="0 0 400 400"><ellipse cx="200" cy="200" rx="188" ry="74" fill="none" stroke="var(--gold)" strokeWidth="2.5" /></svg>
            </div>
            <div className="cover-orbit cover-orbit-2" aria-hidden="true">
              <svg viewBox="0 0 400 400"><ellipse cx="200" cy="200" rx="172" ry="58" fill="none" stroke="var(--rose-dk)" strokeWidth="1.6" strokeDasharray="5 9" /></svg>
            </div>

            <div className="cover-stack" ref={stack}>
              <div className="pol pol-back"><img src={asset("brand/laura-books.webp")} alt="" /></div>
              <div className="pol pol-front">
                <img src={asset("brand/laura-cutout.png")} alt="Laura Gao" />
                <span className="pol-cap">the client</span>
                <Pin size={24} color="var(--red)" style={{ top: -14, left: "50%", marginLeft: -12 }} />
              </div>
            </div>

            <div className="cover-cow"><Cow size={300} /></div>

            <div className="cover-badge" ref={badge}>
              <Rosette size={116} fill="var(--gold)">
                <span className="rz-1">NO</span>
                <span className="rz-2">VIBES</span>
              </Rosette>
            </div>

            <Postmark top="SCORED TWICE" bottom="GREEN IS RARE" size={96}
                      className="cover-pm" color="var(--rose-dk)" />

            <Spark size={30} className="cover-sp1 twinkle" />
            <Spark size={19} className="cover-sp2 twinkle" color="var(--rose-dk)" />
            <Spark size={23} className="cover-sp3 twinkle" color="var(--sage-dk)" />
            <Spark size={15} className="cover-sp4 twinkle" color="#8e4f86" />
            <Doodle name="spiral" size={30} color="var(--ink-4)" className="cover-dd1" />
            <Doodle name="coin" size={24} color="var(--gold-dk)" className="cover-dd2" />
          </div>
        </div>

        <div className="wrap figstrip">
          {([
            ["450,000", "$", "", "she puts in", "two cheques, 2027 and 2028, then nothing", "coin"],
            ["500,000", "$", "", "she owes", "ten payments, 2033 through 2042", "exclaim"],
            ["1,608", "", "", "companies to beat", "the whole SEC universe, not five lookalikes", "eye"],
            ["95", "", "%", "certainty, minimum", "the funding floor we will not go under", "check"],
          ] as [string, string, string, string, string, string][]).map(([v, pre, suf, l, s2, dd], i) => (
            <div className="fs" key={l} data-anim="rise" style={{ ["--delay" as string]: `${i * 90}ms` }}>
              <Doodle name={dd} size={20} color="var(--ink-4)" className="fs-dd" />
              <Odometer className="fs-f" value={v} prefix={pre} suffix={suf} />
              <span className="fs-l">{l}</span>
              <span className="fs-s">{s2}</span>
            </div>
          ))}
        </div>
      </section>

      <Tear fill="var(--ink)" seed={41} />

      {/* ================= TICKER ================= */}
      <section className="band band-ink strip">
        <Marquee speed={42}>
          {["Scored twice", "Green is rare", "The gate cannot be outscored", "Sources or it doesn't ship",
            "AVUS", "VXUS", "IBTM", "SGOV", "NVDA", "SCHD", "A job before a number"].map((t, i) => (
            <span className="strip-i" key={t + i}>{t}<Spark size={13} color="var(--gold)" /></span>
          ))}
        </Marquee>
        <Marquee speed={-28} className="strip-under">
          {["1,608 peers", "SEC EDGAR", "Nasdaq", "U.S. Treasury curve", "no analyst estimates",
            "every figure dated", "every figure sourced"].map((t, i) => (
            <span className="strip-j" key={t + i}>{t}<i>✦</i></span>
          ))}
        </Marquee>
      </section>

      <Seam kind="zig" fill="var(--rose)" />

      {/* ================= THE CLIENT ================= */}
      <section className="band band-rose brief" id="client">
        <Grid kind="grid" size={32} color="rgba(22,18,15,0.055)" />
        <div className="wrap">
          <header className="sec-head">
            <span className="tag">The client</span>
            <h2><Stagger text="Meet Laura. She has a deadline." /></h2>
            <p className="lede">Four facts. Everything else follows from them.</p>
            <Note side="right" rotate={-4} className="brief-note">pick any card up</Note>
          </header>

          <div className="cards">
            {CARDS.map((c, i) => (
              <Card key={c.k} seed={i * 7 + 2} className="card" delay={i * 70} onClick={() => setOpen(c)}
                    tape={i % 2 ? "right" : false}>
                {i % 2 === 0 && <Pin size={22} color={c.pin} style={{ top: -12, left: 22 }} />}
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
              </Card>
            ))}
          </div>
        </div>
      </section>

      <Seam kind="zig" fill="var(--paper)" flip />

      {/* ================= THE SEVEN JOBS ================= */}
      <section className="band band-paper jobs">
        <Grid kind="dot" size={30} color="rgba(22,18,15,0.06)" />
        <div className="wrap">
          <header className="sec-head sec-head-row">
            <div>
              <span className="tag">Before any number</span>
              <h2>Everything gets a <Mark color="var(--sage-hi)">job</Mark> first</h2>
            </div>
            <p className="fine">
              A Treasury dated to 2034 and a growth stock are never measured against the same
              objective. The job decides which model runs and how it is weighted, which is what
              stops the whole thing collapsing into one league table.
            </p>
          </header>

          <div className="jobsheet">
            {JOBS.map(([code, name, tone, what], i) => (
              <Wobble key={code} amount={i % 2 ? 1.8 : -1.8}>
                <span className="job" data-anim="pop" style={{ ["--delay" as string]: `${i * 55}ms`, ["--rot" as string]: `${(i % 3 - 1) * 1.6}deg` }}>
                  <Peel tone={tone} rotate={0} className="job-peel">
                    <b className="num">{code}</b>
                  </Peel>
                  <span className="job-n">{name}</span>
                  <span className="job-w">{what}</span>
                </span>
              </Wobble>
            ))}
          </div>
        </div>
      </section>

      <Tear fill="var(--paper-lo)" seed={29} />

      {/* ================= THE TWO SCORES ================= */}
      <section className="band band-deep scores" id="scores">
        <Grid kind="rule" size={34} color="rgba(22,18,15,0.05)" />
        <div className="wrap">
          <header className="sec-head">
            <span className="tag">The two scores</span>
            <h2>Two questions. Neither one answers the other.</h2>
            <p className="lede">
              Most screens ask the first and stop. That is how you end up holding a magnificent
              company that cannot pay a bill in 2036.
            </p>
          </header>

          <div className="duo">
            <article className="duo-card duo-q" data-anim="rise">
              <span className="duo-n num">01</span>
              <h3>Is it any good?</h3>
              <p className="duo-l">
                Security quality. The same question you would ask about anything, answered against
                1,608 SEC registrants rather than five companies somebody chose.
              </p>
              <ul className="duo-list">
                {QUALITY.map(([k, v]) => (<li key={k}><b>{k}</b><span>{v}</span></li>))}
              </ul>
              <span className="duo-w num">45% of the composite</span>
            </article>

            <span className="duo-vs" aria-hidden="true">
              <Doodle name="bolt" size={30} color="var(--ink)" fill />
              <i>and</i>
            </span>

            <article className="duo-card duo-f" data-anim="rise" style={{ ["--delay" as string]: "120ms" }}>
              <span className="duo-n num">02</span>
              <h3>Is it good for her?</h3>
              <p className="duo-l">
                Laura fit. The same security scores differently depending on the job it is being
                asked to do, because the job is what it has to survive.
              </p>
              <ul className="duo-list">
                {FIT.map(([k, v]) => (<li key={k}><b>{k}</b><span>{v}</span></li>))}
              </ul>
              <span className="duo-w num">55% of the composite</span>
            </article>
          </div>

          <div className="formula" data-anim="stamp">
            <PriceTag className="formula-tag" color="var(--rose-hi)">45 / 55</PriceTag>
            <span className="tag bare">How they combine</span>
            <p className="formula-eq num">
              composite = 100 × (<em>quality</em>/100)<sup>0.45</sup> × (<em>fit</em>/100)<sup>0.55</sup>
            </p>
            <p className="formula-say">
              A geometric mean, not an average, and tilted toward her. The difference matters: a 96
              that suits her badly cannot buy its way out of a 60, because multiplying by a small
              number stays small. An average would have let it.
            </p>
            <Doodle name="arrowCurl" size={34} color="var(--ink-4)" className="formula-dd" />
          </div>
        </div>
      </section>

      <Tear fill="var(--ink)" seed={61} />

      {/* ================= THE ENGINE ================= */}
      <section className="band band-ink" id="engine"><Engine /></section>

      <Tear fill="var(--paper)" seed={9} />

      {/* ================= THE VERDICT LADDER ================= */}
      <section className="band band-paper signals">
        <Grid kind="dot" size={28} color="rgba(22,18,15,0.05)" />
        <div className="wrap">
          <header className="sec-head">
            <span className="tag">The verdict</span>
            <h2>Five answers. One of them is <span className="ul-host">rare<Underline /></span>.</h2>
            <p className="lede">Green needs every gate at once. That is the entire point of it.</p>
          </header>

          <div className="swatches">
            {ladderKey(policy).map(([name, tone, cond, mean], i) => (
              <div className="sw" key={name} data-tone={tone} data-anim="swing"
                   style={{ ["--delay" as string]: `${i * 80}ms`, ["--rot" as string]: `${(i % 2 ? 1 : -1) * 1.1}deg` }}>
                <span className="sw-chip" />
                <span className="sw-n">{name}</span>
                <span className="sw-c">{cond}</span>
                <span className="sw-m">{mean}</span>
                {tone === "green" && (
                  <Rosette size={54} fill="var(--green)" className="sw-seal">
                    <span className="rz-s">RARE</span>
                  </Rosette>
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ================= THE BOARD ================= */}
      {board && board.index?.length > 0 && (
        <>
          <Seam kind="stitch" fill="var(--ink-4)" />
          <section className="band band-paper boardsec">
            <div className="wrap">
              <header className="sec-head sec-head-row">
                <div>
                  <span className="tag">Already run through it</span>
                  <h2>The board, as it stands</h2>
                </div>
                <p className="fine">
                  Every one of these is the engine's own output, scored on {board.generated_on} under{" "}
                  {board.framework_version}. Nothing here is illustrative.
                </p>
              </header>

              <div className="board">
                {board.index.slice(0, 10).map((r, i) => (
                  <button key={r.ticker + i} className="bd-card" data-tone={SIGNAL_TONE[r.signal] ?? "amber"}
                          data-anim="pop" style={{ ["--delay" as string]: `${i * 45}ms`, ["--rot" as string]: `${(i % 3 - 1) * 1.1}deg` }}
                          onClick={() => go("score")}>
                    <span className="bd-t num">{r.ticker}</span>
                    <span className="bd-s num">{r.composite.toFixed(0)}</span>
                    <span className="bd-sig">{r.signal.replace("_", " ").toLowerCase()}</span>
                    <span className="bd-n">{r.name}</span>
                  </button>
                ))}
              </div>
              <p className="caption">
                The three dated Treasuries sit at the top because they are the only things that can
                actually pay a bill on a date. That is the framework working, not a coincidence.
              </p>
            </div>
          </section>
        </>
      )}

      <Seam kind="zig" fill="var(--paper-lo)" />

      {/* ================= THE RULES ================= */}
      <section className="band band-deep rules" id="rules">
        <Grid kind="grid" size={30} color="rgba(22,18,15,0.05)" />
        <div className="wrap">
          <header className="sec-head">
            <span className="tag">The rules</span>
            <h2>Locked before anything was scored</h2>
            <p className="lede">
              Change a weight and you get a new version number and a full rescore. That is what
              stops a weight being nudged until a favourite wins.
            </p>
          </header>

          <div className="rules-grid">
            <div className="refuses">
              <h3>Seven things it flat out refuses to do</h3>
              <ul className="refuse-list">
                {REFUSES.map(([t, dd], i) => (
                  <li key={t} data-anim="rise" style={{ ["--delay" as string]: `${i * 55}ms` }}>
                    <Doodle name={dd} size={19} color="var(--red)" />
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
                    <span className="pv-k">{kind}<i className="pv-t" data-t={tier}>{tier === "0" ? "not used" : `tier ${tier}`}</i></span>
                    <span className="pv-s">{note}</span>
                  </div>
                </div>
              ))}
              <Postmark top="SOURCED OR IT" bottom="DOES NOT SHIP" size={92} className="prov-pm" color="var(--sage-dk)" />
            </div>
          </div>
        </div>
      </section>

      <Tear fill="var(--gold)" seed={33} />

      {/* ================= CLOSER ================= */}
      <section className="band band-gold closer">
        <Halftone className="closer-dots" color="var(--ink)" opacity={0.11} size={10} />
        <Splat size={110} seed={3} color="var(--rose-dk)" opacity={0.18} style={{ top: "8%", left: "6%" }} />
        <Splat size={80} seed={27} color="var(--sage-dk)" opacity={0.16} style={{ bottom: "10%", right: "8%" }} />
        <div className="wrap closer-in">
          <h2><Stagger text="Go on. Throw something at it." /></h2>
          <p className="lede">A ticker and a job. You get a verdict, the reasoning, and every source it leaned on.</p>
          <div className="closer-cta">
            <Btn kind="ink" size="lg" arrow onClick={() => go("score")}>Score a ticker</Btn>
          </div>
          <Cow size={150} />
          <Doodle name="star" size={26} color="var(--ink)" className="closer-dd1" />
          <Doodle name="star" size={18} color="var(--ink)" className="closer-dd2" />
        </div>
      </section>

      {/* ================= DOSSIER ================= */}
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
            {open.photo && <div className="dossier-pic"><img src={open.photo} alt="" /></div>}
            {open.body.map((t, i) => <p key={i}>{t}</p>)}
            <dl className="dossier-rows">
              {open.rows.map(([k, v]) => (<div key={k}><dt>{k}</dt><dd className="num">{v}</dd></div>))}
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
