import { useState } from "react";
import { fmtNum, fmtPct, type Category, type Evaluation, type Metric } from "../api";
import { Blocks, Breakdown, Gates, Meter, Stamp, Trace, TwoUp } from "../ui/Charts";
import { Fold, Note, Paper } from "../ui/Kit";
import { Spark } from "../ui/Marks";

/* Counts and index values are whole numbers. Printing 2,100.0 holdings is the
   kind of detail that quietly tells a reader nobody looked at the output. */
function cell(m: Metric) {
  if (m.value === null) return m.status === "MISSING" ? "not available" : "·";
  const v = m.value;
  const dp = Number.isInteger(v) || Math.abs(v) >= 1000 ? 0 : Math.abs(v) < 10 ? 2 : 1;
  return fmtNum(v, dp);
}

function Metrics({ categories, labels, only }: {
  categories: Category[]; labels: Record<string, string>; only: string | null;
}) {
  const rows = categories
    .filter((c) => !only || c.key === only)
    .flatMap((c) => c.metrics.map((m) => ({ m, cat: labels[c.key] ?? c.key })));

  return (
    <table className="tbl">
      <thead>
        <tr>
          <th>Metric</th>
          <th className="r">Reads</th>
          <th className="r" style={{ width: 150 }}>Scores</th>
          <th className="r">Carries</th>
          <th>Measured against</th>
        </tr>
      </thead>
      <tbody>
        {rows.map(({ m, cat }) => (
          <tr key={m.key + cat} data-status={m.status}>
            <td>
              <span className="t-label">{m.label}</span>
              <span className="t-note">
                {m.status === "MISSING" && <b className="t-flag t-missing">Could not verify it. </b>}
                {m.status === "NOT_APPLICABLE" && <b className="t-flag">Does not apply here. </b>}
                {m.interpretation || m.note}
              </span>
            </td>
            <td className="r num t-val">
              {cell(m)}
              {m.units && m.value !== null && <i className="t-u">{m.units}</i>}
            </td>
            <td className="r">
              {m.status === "NOT_APPLICABLE" ? <span className="t-dash">·</span> : (
                <span className="t-score">
                  <b className="num">{m.score.toFixed(0)}</b>
                  <Meter score={m.score} status={m.status} />
                </span>
              )}
            </td>
            <td className="r num t-w">{m.effective_weight.toFixed(1)}<small>pt</small></td>
            <td className="t-peer">
              {m.percentile !== null
                ? <>p{m.percentile.toFixed(0)}, {m.peer_group}</>
                : m.status === "OK" ? "threshold bands" : ""}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default function Verdict({ ev, need }: {
  ev: Evaluation;
  need: { sqs: number; lpfs: number; ccs: number; dcs: number };
}) {
  const [sqCat, setSqCat] = useState<string | null>(null);
  const [fitCat, setFitCat] = useState<string | null>(null);
  const sig = ev.signal.signal;
  const pi = ev.portfolio_impact;
  const lt = ev.security_quality.lookthrough;
  const d = ev.security_quality.derived ?? {};
  const dcs = ev.scores.data_confidence;

  return (
    <article className="verdict" data-signal={sig}>
      {/* ---- masthead ---- */}
      <header className="vd-top">
        <div className="wrap vd-top-in">
          <div className="vd-id">
            <h1 className="vd-tkr">{ev.ticker}</h1>
            <p className="vd-name">{ev.name}</p>
            <div className="vd-chips">
              <span className="chip">{ev.asset_type_label}</span>
              <span className="chip chip-gold">
                {ev.role_label}{ev.laura_fit.role_is_team_defined ? ", our label" : ""}
              </span>
              <span className="chip">at <b>{ev.position_pct.toFixed(1)}%</b></span>
              {ev.target_payment_year && <span className="chip chip-rose">aimed at <b>{ev.target_payment_year}</b></span>}
              <span className="chip chip-sage">{ev.risk_state.state.toLowerCase()} mode</span>
            </div>
          </div>

          <div className="vd-px">
            {ev.quote?.price != null && <div className="vd-px-v num">${fmtNum(ev.quote.price, 2)}</div>}
            {ev.quote?.change_pct && (
              <div className="vd-px-c num" data-up={!String(ev.quote.change_pct).startsWith("-") || undefined}>
                {ev.quote.change_pct} today
              </div>
            )}
            {ev.risk_profile?.sparkline && <Trace values={ev.risk_profile.sparkline} />}
            <div className="fine">
              {ev.risk_profile && <>{fmtPct(ev.risk_profile.price_return_pct)} over five years. </>}
              {ev.quote?.as_of && <>Priced {ev.quote.as_of}.</>}
            </div>
          </div>
        </div>
      </header>

      {/* ---- the call ---- */}
      <section className="wrap vd-call">
        <Stamp score={ev.scores.composite} signal={sig} label={ev.signal.label} size={316} />

        <div className="vd-say">
          <div className="vd-say-head">
            <h2 className="vd-word">{ev.signal.label}</h2>
            <span className={`chip chip-${ev.red_gate.status === "PASS" ? "green" : ev.red_gate.status === "FAIL" ? "red" : "amber"}`}>
              Red Gate {ev.red_gate.status.toLowerCase()}
            </span>
          </div>
          <p className="vd-mean">{ev.signal.meaning}</p>

          {ev.red_gate.failures.length > 0 && (
            <Note tone="bad"><b>This is why it cannot pass. </b>{ev.red_gate.failures[0].detail}</Note>
          )}
          {ev.red_gate.failures.length === 0 && ev.red_gate.reviews.length > 0 && (
            <Note tone="warn"><b>Worth a second look. </b>{ev.red_gate.reviews[0].detail}</Note>
          )}

          <Gates sqs={ev.scores.security_quality} lpfs={ev.scores.laura_fit}
                 ccs={ev.scores.composite} dcs={dcs} need={need} />

          <div className="vd-size">
            <span className="tag bare">How much we would actually buy</span>
            <b className="serif">{ev.position_sizing.suggested_pct.toFixed(1)}%</b>
            <i>of the sleeve, against a {ev.position_sizing.policy_cap_pct.toFixed(0)}% ceiling</i>
          </div>
        </div>
      </section>

      {/* ---- the two scores ---- */}
      <section className="wrap vd-two">
        <TwoUp sqs={ev.scores.security_quality} lpfs={ev.scores.laura_fit}
               ccs={ev.scores.composite} signal={sig} gate={need.ccs} />
      </section>

      {/* ---- best and worst ---- */}
      <section className="wrap vd-pull">
        <div className="pull pull-up">
          <h3>What is carrying it</h3>
          {ev.strengths.slice(0, 4).map((s) => (
            <div className="pl" key={s.label}>
              <span className="pl-l">{s.label}</span>
              <span className="pl-v num">{s.value}</span>
              <Meter score={s.score} status="OK" />
              <span className="pl-s num">{s.score.toFixed(0)}</span>
            </div>
          ))}
        </div>
        <div className="pull pull-down">
          <h3>What is dragging it down</h3>
          {ev.risks.slice(0, 4).map((s) => (
            <div className="pl" key={s.label}>
              <span className="pl-l">{s.label}</span>
              <span className="pl-v num">{s.value}</span>
              <Meter score={s.score} status="OK" />
              <span className="pl-s num">{s.score.toFixed(0)}</span>
            </div>
          ))}
        </div>
      </section>

      {/* ---- three takes ---- */}
      <section className="wrap takes">
        {([
          ["Why that number", ev.explanation.why_the_score_is_what_it_is, "up"],
          ["What could bite", ev.explanation.what_could_go_wrong, "down"],
          ["What it means for her", ev.explanation.why_laura_should_care, "client"],
        ] as const).map(([h, list, tone], i) => (
          <Paper key={h} seed={i * 11 + 5} tilt={1.1} className={`take take-${tone}`} delay={i * 80}>
            <h4>{h}</h4>
            <ul>{list.map((t, j) => <li key={j}>{t}</li>)}</ul>
          </Paper>
        ))}
      </section>

      {/* ---- where the points went ---- */}
      <section className="wrap vd-build">
        <header className="sec-head">
          <span className="tag">The breakdown</span>
          <h2>Where the hundred points went</h2>
        </header>

        <div className="builds">
          <div className="build">
            <div className="build-head">
              <span className="build-t">Is it any good?</span>
              <span className="build-v num">{ev.scores.security_quality.toFixed(0)}</span>
              <span className="build-m">{ev.security_quality.model}</span>
            </div>
            <Breakdown categories={ev.security_quality.categories}
                       labels={ev.security_quality.category_labels}
                       active={sqCat} onPick={setSqCat}
                       score={ev.scores.security_quality} kind="quality" gate={need.sqs} />
            {ev.security_quality.peer_group && (
              <p className="fine">
                Percentiles run against {ev.security_quality.peer_group.label},{" "}
                {ev.security_quality.peer_group.n} companies, built from{" "}
                {ev.security_quality.peer_group.source} on {ev.security_quality.peer_group.generated_at}.
                Where no peer distribution exists the metric falls back to documented threshold
                bands and says so on its own row.
              </p>
            )}
            {ev.security_quality.overlays.map((o, i) => <Note key={i}>{o}</Note>)}
          </div>

          <div className="build">
            <div className="build-head">
              <span className="build-t">Is it good for her?</span>
              <span className="build-v num">{ev.scores.laura_fit.toFixed(0)}</span>
              <span className="build-m">weighted for {ev.role_label}</span>
            </div>
            <Breakdown categories={ev.laura_fit.categories}
                       labels={ev.laura_fit.category_labels}
                       active={fitCat} onPick={setFitCat}
                       score={ev.scores.laura_fit} kind="fit" gate={need.lpfs} />
            {ev.laura_fit.risk_state && (
              <Note>
                <b>{ev.laura_fit.risk_state.state.toLowerCase()} mode.</b> {ev.laura_fit.risk_state.reason}{" "}
                Downside components weigh {ev.laura_fit.risk_state.downside_multiplier.toFixed(2)} times here.
              </Note>
            )}
          </div>
        </div>
      </section>

      {/* ---- what it does to the rest ---- */}
      <section className="wrap vd-impact">
        <header className="sec-head">
          <span className="tag">Knock-on effects</span>
          <h2>What it does to everything else she holds</h2>
        </header>

        <div className="impact">
          <div className="imp-col">
            <span className="tag bare">Crowding, before and after</span>
            {([
              ["Issuer", pi.before.issuer_hhi, pi.after.issuer_hhi, pi.delta.issuer_hhi],
              ["Sector", pi.before.sector_hhi, pi.after.sector_hhi, pi.delta.sector_hhi],
              ["Country", pi.before.country_hhi, pi.after.country_hhi, pi.delta.country_hhi],
            ] as [string, number, number, number][]).map(([label, b, a, dl]) => (
              <div className="hhi" key={label}>
                <span className="hhi-k">{label}</span>
                <span className="hhi-b num">{fmtNum(b, 0)}</span>
                <svg className="hhi-arrow" viewBox="0 0 30 12" aria-hidden="true">
                  <path d="M1 6h24M21 2l5 4-5 4" fill="none" stroke="currentColor"
                        strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
                <span className="hhi-a num">{fmtNum(a, 0)}</span>
                <span className="hhi-d num" data-dir={dl < 0 ? "down" : dl > 0 ? "up" : "flat"}>
                  {dl > 0 ? "+" : ""}{fmtNum(dl, 0)}
                </span>
              </div>
            ))}
            <p className="fine">
              A Herfindahl index counts how much of the money sits in how few names. Down
              is the good direction, so green points down here.
            </p>
          </div>

          <div className="imp-col">
            <span className="tag bare">How much of this she owns already</span>
            <div className="overlaps">
              {([
                ["Issuer", pi.overlap.issuer_overlap_pct],
                ["Sector", pi.overlap.sector_overlap_pct],
                ["Country", pi.overlap.country_overlap_pct],
              ] as [string, number][]).map(([k, v]) => (
                <div className="ov" key={k}>
                  <span className="ov-v num">{fmtPct(v, 0)}</span>
                  <span className="ov-k">{k.toLowerCase()} overlap</span>
                  <Blocks filled={Math.round((v / 100) * 10)} tone="rose" />
                </div>
              ))}
            </div>

            {pi.overlap.shared_issuers?.length > 0 ? (
              <>
                <span className="tag bare">Already hers, through other funds</span>
                <div className="shared">
                  {pi.overlap.shared_issuers.slice(0, 6).map((s: any) => (
                    <div className="sh" key={s.key}>
                      <span className="sh-k num">{s.key}</span>
                      <span className="sh-bar"><i style={{ width: `${Math.min(100, s.already_held_pct * 9)}%` }} /></span>
                      <span className="sh-v num">{fmtPct(s.already_held_pct, 2)}</span>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <p className="fine">Nothing named inside this is already held anywhere else.</p>
            )}
          </div>
        </div>
      </section>

      {/* ---- sizing, confidence, triggers ---- */}
      <section className="wrap vd-close">
        <div className="vc">
          <span className="tag bare">How much</span>
          <div className="vc-big">
            <span className="serif">{ev.position_sizing.suggested_pct.toFixed(1)}%</span>
            <i>ceiling {ev.position_sizing.policy_cap_pct.toFixed(0)}%</i>
          </div>
          <ul className="vc-list">
            {ev.position_sizing.constraints.map((c, i) => <li key={i}>{c}</li>)}
          </ul>
          <p className="fine">{ev.position_sizing.note}</p>
        </div>

        <div className="vc">
          <span className="tag bare">How sure we are</span>
          <div className="vc-big">
            <span className="serif" data-weak={dcs < 70 || undefined}>{dcs.toFixed(0)}</span>
            <i>under 70 and it refuses to call it at all</i>
          </div>
          <div className="dcs">
            {ev.data_confidence.components.map((c) => (
              <div className="dc" key={c.key}>
                <span className="dc-k">{c.label}</span>
                <Meter score={c.score} status="OK" />
                <span className="dc-v num">{c.score.toFixed(0)}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="vc">
          <span className="tag bare">Come back if any of this happens</span>
          <ul className="vc-list vc-triggers">
            {ev.review_triggers.map((t, i) => <li key={i}>{t}</li>)}
          </ul>
          <Spark size={18} className="vc-sp" />
        </div>
      </section>

      {/* ---- the audit trail ---- */}
      <section className="wrap vd-audit">
        <Fold title="Show me everything" note="Every metric, every source, every as-of date">
          <div className="audit">
            <h3>Is it any good, metric by metric</h3>
            <p className="fine">
              Not written up afterwards. This is the structure the score is made of.
              {sqCat && " Filtered to the category you picked above."}
            </p>
            <Metrics categories={ev.security_quality.categories}
                     labels={ev.security_quality.category_labels} only={sqCat} />

            <h3>Is it good for her, metric by metric</h3>
            <p className="fine">These weights change completely with the job.</p>
            <Metrics categories={ev.laura_fit.categories}
                     labels={ev.laura_fit.category_labels} only={fitCat} />

            {lt && lt.coverage_pct > 0 && (
              <>
                <h3>Looking through to the companies inside</h3>
                <p className="fine">
                  Each holding resolved against its own SEC filings and weighted by position
                  size, covering {fmtPct(lt.coverage_pct, 0)} of the sampled weight. Holdings
                  that do not file with the SEC are skipped rather than guessed at, and the
                  gap is charged to data confidence.
                </p>
                <table className="tbl">
                  <thead>
                    <tr>
                      <th>Holding</th><th className="r">Weight</th><th className="r">Return on equity</th>
                      <th className="r">Free cash flow margin</th><th className="r">3yr revenue CAGR</th>
                    </tr>
                  </thead>
                  <tbody>
                    {lt.holdings.map((h) => (
                      <tr key={h.ticker}>
                        <td><span className="t-label num">{h.ticker}</span><span className="t-note">{h.name}</span></td>
                        <td className="r num t-val">{fmtPct(h.weight, 2)}</td>
                        <td className="r num t-val">{fmtPct(h.roe)}</td>
                        <td className="r num t-val">{fmtPct(h.fcf_margin)}</td>
                        <td className="r num t-val">{fmtPct((h as any).revenue_cagr_3y)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </>
            )}

            <h3>Where every figure came from</h3>
            {d.market_cap_basis && (
              <p className="fine">Market capitalisation: {String(d.market_cap_basis).toLowerCase()}.</p>
            )}
            <div className="srcs">
              {ev.sources.map((s) => (
                <div className="src" key={s.name}>
                  <span className="src-t" data-t={s.authority_tier}>T{s.authority_tier}</span>
                  <div>
                    <div className="src-n">
                      {s.url ? <a href={s.url} target="_blank" rel="noreferrer noopener">{s.name}</a> : s.name}
                    </div>
                    <div className="src-s">
                      Behind {s.supports.length} metric{s.supports.length === 1 ? "" : "s"}, including{" "}
                      {s.supports.slice(0, 3).join(", ")}.
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {ev.details?.source_url && (
              <p className="fine">
                {ev.details.expense_ratio_source === "exchange"
                  ? <>Expense ratio and fund assets come live from the exchange
                      {ev.details.expense_ratio_registry != null &&
                       ev.details.expense_ratio_registry !== ev.details.expense_ratio
                        ? ` (our typed-up registry said ${ev.details.expense_ratio_registry}%, corrected to ${ev.details.expense_ratio}%)`
                        : null}. Holdings, sector and country weights and the maturity structure
                      still come from the registry, as of {ev.details.registry_as_of}. </>
                  : <>Fund facts are typed up from the issuer, as of {ev.details.registry_as_of}. </>}
                Check them against <a href={ev.details.source_url} target="_blank" rel="noreferrer noopener">the issuer page</a>{" "}
                before anyone signs anything.
              </p>
            )}

            {ev.decision_log_draft && (
              <>
                <h3>Decision log, ready to paste</h3>
                <p className="fine">
                  Snapshot {ev.snapshot_id} is frozen under {ev.framework_version}. If this
                  thing is up 25 percent next month, the reasoning recorded today does not change.
                </p>
                <table className="tbl tbl-log">
                  <tbody>
                    {Object.entries(ev.decision_log_draft).map(([k, v]) => (
                      <tr key={k}>
                        <td className="t-k">{k.replace(/_/g, " ")}</td>
                        <td>{Array.isArray(v) ? v.join("; ") : String(v)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </>
            )}
          </div>
        </Fold>
      </section>
    </article>
  );
}
