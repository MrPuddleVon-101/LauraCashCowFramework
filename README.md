# Stonky x Cash Cows

The Laura Cash Cow Framework (LCCF), built for the Wharton Global High School Investment
Competition 2026-2027.

Every candidate investment gets two independent scores. The Security Quality Score asks
whether the investment is good. The Laura Portfolio Fit Score asks whether it is good
**for Laura Gao**, given her liabilities, her timeline and what she already owns. They
combine through a weighted geometric mean, so a superb security with a poor client fit
cannot hide behind an average.

```
CCS = 100 × (SQS/100)^0.45 × (LPFS/100)^0.55
```

A green signal needs the Red Gate to pass and all four scores to clear their thresholds.
Green is meant to be rare, and over a 52 name test sweep nothing reached it.

## Running it

Two processes. Start the API first.

```bash
cd backend && ./.venv/bin/python -m uvicorn app.main:app --port 8077 --reload
```

```bash
cd frontend && npm run dev
```

Then open http://localhost:5173. Vite proxies `/api` to the backend.

First-time setup, if the virtual environment is missing:

```bash
cd backend && python3 -m venv .venv && ./.venv/bin/pip install fastapi "uvicorn[standard]" numpy httpx pydantic
```

```bash
cd frontend && npm install
```

## Where the numbers come from

Nothing on screen is invented. Each figure carries its source, its as-of date and a
confidence flag, and a figure that could not be verified is reported as missing rather
than filled in.

| Data | Source | Tier |
| --- | --- | --- |
| Company fundamentals | SEC EDGAR XBRL company facts, 10-K and 20-F | 1 |
| Peer distributions | SEC XBRL frames, 1,608 registrants above $1bn revenue | 1 |
| Prices, quotes, bid-ask | Nasdaq market data | 1 |
| Treasury yield curve | U.S. Treasury daily par yield curve | 1 |
| Fund holdings, fees, maturities | Issuer factsheets, transcribed to `backend/data/etf_registry.json` | 2 |
| Analyst estimates | Not wired in. Metrics that need them are reported missing. | n/a |

Foreign private issuers file under IFRS rather than US GAAP, so the EDGAR adapter reads
both namespaces. Without that, every non-US holding inside an international fund would
read as missing and the look-through engine would have nothing to work with.

The fund registry is the one place facts are transcribed by hand. It is deliberately
treated as tier 2 rather than tier 1, every row carries the issuer URL it should be
checked against, and the interface says so. Refresh it before a committee decision.

## Rebuilding the peer data

Peer percentiles come from the whole registrant universe, not a hand-picked comparison
set. To regenerate after a new fiscal year closes:

```bash
cd backend && ./.venv/bin/python -m scripts.build_peers
```

That writes `backend/data/peers.json` with distributions by sector and by revenue band.
Where a sector group is too thin, scoring falls back to documented threshold bands and
names the fallback on the metric.

## Layout

```
backend/
  app/
    config.py            Client facts and team policy, kept strictly apart
    main.py              FastAPI routes
    store.py             SQLite: snapshots, decisions, framework versions
    providers/
      sec.py             EDGAR adapter, US GAAP and IFRS
      market.py          Prices, quotes, risk statistics
      treasury.py        Par yield curve
    engine/
      normalize.py       Percentile engine, evidence objects, data confidence
      peers.py           Peer-group resolution
      stock.py           Stock SQS, 100 points
      funds.py           Broad, international, thematic, bond and cash models
      fit.py             LPFS, weighted by role
      composite.py       Red Gate, composite, signal, position sizing
      lookthrough.py     Issuer, sector and country resolution, overlap, HHI
      liability.py       The ten payments, funding states, present values
      simulate.py        Monte Carlo, stress tests, facility capacity
      evaluate.py        The pipeline that ties it together
  data/                  Peer distributions, fund registry, sectors, portfolios
  scripts/build_peers.py
frontend/
  src/
    api.ts                 The one place the backend contract lives
    lib/motion.ts          One scroll clock, one entrance observer, counters
    lib/draw.ts            Seeded hand drawn geometry, and the palettes
    ui/Marks.tsx           Drawn rings, arrows, sparkles, torn seams, the cow
    ui/Kit.tsx             Buttons, pasted paper, the marquee, folds
    ui/Charts.tsx          Every chart, drawn by hand on a canvas we control
    ui/Nav.tsx             Sections and the scroll indicator
    views/                 Home and Engine (the one page overview),
                           Score and Verdict (the research desk)
    styles/                base.css for the material, views.css for the pages
docs/
  DESIGN-RULES.md        What is banned from this interface, and what we do instead
```

## The interface

The logo is an ink and gouache drawing on cream, so the site is built out of the same
material: paper, ink, tape, and marks made by a hand that does not use a compass. Every
circle, underline, arrow and torn seam is generated from a seed in `lib/draw.ts`, which
means a given mark is identical on every render and nothing twitches when React re-runs a
component.

Colour does one job each. Gold belongs to Laura. Green, amber and red belong to the signal
ladder and appear nowhere else, so a green mark always means the same thing. Rose carries
the liability calendar, sage carries the portfolio. The page is laid out as bands of flat
colour meeting on torn edges, so it changes temperature as you move down it.

The overview explains the pipeline by making you operate it. A candidate rides a belt
through four stations, and the scroll is what moves it: classify, gate, score twice,
combine. The order is the argument, so the reader performs the order rather than reading
about it. One rAF loop drives the whole page and one IntersectionObserver at the root
marks entrances, so nothing attaches its own scroll listener.

Charts are drawn rather than configured. The composite is a rubber stamp. The two scores
are two bars sized to the exponent each carries, 45 and 55, so the weighting is visible
before a word of it is read. Each model is a polar area chart whose wedge widths are its
own weights. The ten payments are ten columns, look-through exposure is a treemap, and ten
thousand simulated outcomes are a range of hills. The full audit trail, every metric with
its source and as-of date, sits behind one disclosure at the bottom of a verdict.

## How the scores are calibrated

A percentile is a rank. A score is a judgement about that rank, and the two are not
the same number.

The engine originally mapped rank straight onto score, so the median company on a
metric read 50. That looks neutral and is not, because a scorecard weighs twenty or
more metrics together and a weighted mean of twenty percentiles regresses hard to the
middle. Nothing real ever reached 70, let alone the 90 the green threshold asked for.
Measured over a 52 name sweep of funds, Treasuries, mega caps and genuinely weak
businesses, 87% of everything came out RED, including AVUS and VTI, which are the
portfolio's own core holdings. A ladder where almost every rung is the bottom rung
carries no information.

`normalize.PERCENTILE_CURVE` now maps rank to score along documented anchors:

| Percentile | Score | Band |
| --- | --- | --- |
| 10th | 30 | Weak |
| 25th | 46 | Weak |
| 50th | 62 | Neutral |
| 75th | 77 | Above average |
| 90th | 88 | Strong |
| 95th | 93 | Exceptional |

The curve is strictly monotone, so nothing is reordered: a company that ranked above
another still scores above it. The raw percentile is still printed on every metric
row, so the audit trail shows the rank as well as the reading of it. It also puts the
two kinds of metric on one scale. Metrics scored against documented threshold bands
were always written in this register, where a 16x earnings multiple reads as 74.
Mixing those with raw ranks inside one weighted card was adding up two different
scales.

Thresholds moved with the scale. Green needs 85 on security quality, Laura fit and
the composite, with data confidence at 85. Red is anything below 60 on either score,
which is to say below a median company. Over the same 52 name sweep that gives
roughly 10% amber plus, 56% amber and 35% red, with the dated Treasury funds at the
top, the broad core ETFs behind them, and Intel, Boeing, Tesla and Pfizer at the
bottom. The best candidate in the sweep reaches 85.8 composite on 83.7 security
quality, so green remains live but unclaimed.

Three scoring faults were fixed alongside the curve:

- A Treasury was fed a literal zero into the credit spread metric and scored 60 for
  having no credit risk. It is now marked not applicable, and under the PRD 60 rule
  the weight returns to the other yield measures.
- Position in the 52 week price range was being used as a valuation measure. That is
  momentum in a valuation costume: a company that has just raised guidance can sit at
  95% of its range and be cheaper than it was a year ago. The earnings multiple
  against its own filed five year range is now preferred, and the price range is a
  labelled fallback on a gentler band.
- The fit model read the growth category out of the quality card by list position
  rather than by name. It happened to be correct, and would have silently started
  scoring Laura's growth contribution off the cash flow category the first time
  anybody reordered that dict.

## What the framework refuses to do

- Score a security without a proposed portfolio role.
- Let a high composite override a Red Gate failure.
- Treat a perpetual bond fund as a liability matcher. Its value on a given future date
  is unknown, so it cannot carry a dated payment.
- Redistribute the weight of a missing metric. Not applicable gives its weight back to
  its category; missing keeps it at a neutral 50 and is charged to data confidence.
- Infer Laura's political, social or ethical preferences. With no explicit exclusion on
  file, mission fit scores 50, and it is capped at five points regardless.
- Use one discount rate forever. Each payment is discounted at the Treasury yield for
  its own maturity.
- Rewrite a past evaluation. Snapshots are frozen under the framework version that
  produced them.

## One finding worth reading

At the Treasury yields on file, securing all ten payments costs about $295,000 from
2027, less than the first contribution on its own. The team's planning work assumed 4%.
The curve is closer to 5%, which makes the ladder materially cheaper and leaves more for
the facility than the $100,000 provisional cap allows. The engine surfaces this rather
than quietly quoting a larger number: the cap is now the binding constraint, not the
portfolio, and that is a committee decision.

Separately, the defined-maturity Treasury funds in the registry reach 2035. The seven
payments from 2036 to 2042 cannot be matched with a dated fund and need individual
Treasuries or STRIPS bought directly. The ladder view says so on its face.
