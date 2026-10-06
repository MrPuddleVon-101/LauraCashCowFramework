import { useState } from "react";
import { fmtNum, fmtPct, type Category, type Evaluation, type Metric } from "../api";
import { Breakdown, Gates, Meter, Stamp, Trace, TwoUp } from "../ui/Charts";
import { Fig, Fold, Note, Paper } from "../ui/Kit";
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
      {pi.before.positions?.length > 0 && (
        <section className="wrap vd-impact">
          <header className="sec-head">
            <span className="tag">Knock-on effects</span>
            <h2>What it does to everything else she holds</h2>
            <p className="lede">
              At {fmtPct(pi.candidate_weight_pct, 0)} of the book, against the{" "}
              {pi.before.positions.length} positions already open.
            </p>
          </header>

          <div className="impact">
            <div className="imp-col">
              <span className="tag bare">Crowding, before and after</span>
              {([
                ["Issuer", pi.before.issuer_hhi, pi.after.issuer_hhi, pi.delta.issuer_hhi],
                ["Sector", pi.before.sector_hhi, pi.after.sector_hhi, pi.delta.sector_hhi],
                ["Country", pi.before.country_hhi, pi.after.country_hhi, pi.delta.country_hhi],
              ] as [string, number, number, number][]).map(([label, b, a, dl], i) => {
                const max = Math.max(b, a) || 1;
                const dir = dl < 0 ? "down" : dl > 0 ? "up" : "flat";
                return (
                  <div className="cr" key={label} data-dir={dir} data-anim="rise"
                       style={{ ["--delay" as string]: `${i * 90}ms` }}>
                    <span className="cr-k">{label}</span>
                    <span className="cr-track">
                      <i className="cr-fill" style={{ width: `${(Math.min(b, a) / max) * 100}%` }} />
                      <i className="cr-move" style={{
                        left: `${(Math.min(b, a) / max) * 100}%`,
                        width: `${(Math.abs(a - b) / max) * 100}%`,
                      }} />
                    </span>
                    <span className="cr-v num">{fmtNum(b, 0)} <em>→</em> {fmtNum(a, 0)}</span>
                    <span className="cr-d num">{dl > 0 ? "+" : ""}{fmtNum(dl, 0)}</span>
                  </div>
                );
              })}
              <p className="fine">
                Herfindahl: how much of the money sits in how few names. Lower is safer.
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
                    <Fig value={v} dp={0} suffix="%" className="ov-v" />
                    <span className="ov-k">{k.toLowerCase()}</span>
                  </div>
                ))}
              </div>

              {pi.overlap.shared_issuers?.length > 0 ? (
                <>
                  <span className="tag bare">Bought twice</span>
                  <div className="shared">
                    {pi.overlap.shared_issuers.slice(0, 6).map((sh: any, i: number) => (
                      <div className="sh" key={sh.key} data-anim="rise"
                           style={{ ["--delay" as string]: `${i * 60}ms` }}>
                        <span className="sh-k num">{sh.key}</span>
                        <span className="sh-bar">
                          <i style={{ width: `${Math.min(100, sh.already_held_pct * 9)}%` }} />
                        </span>
                        <span className="sh-v num">{fmtPct(sh.already_held_pct, 2)}</span>
                      </div>
                    ))}
                  </div>
                  <p className="fine">As a share of the whole book.</p>
                </>
              ) : (
                <p className="fine">Nothing inside this is held anywhere else.</p>
              )}
            </div>
          </div>
        </section>
      )}

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

      {ev.registry_drift?.stale && (
        <section className="wrap vd-drift">
          <Note tone="warn">
            <b>The transcribed registry behind this fund has moved. </b>
            {ev.registry_drift.drifted_count} figure
            {ev.registry_drift.drifted_count === 1 ? "" : "s"} no longer match an
            independent read of the fund. The scores above are unchanged and do not
            use this check. It is a prompt to re-read the issuer factsheet. The
            comparison is in the audit trail below.
          </Note>
        </section>
      )}

      {/* ---- the audit trail ---- */}
      <section className="wrap vd-audit">
        <Fold title="Show me everything" note="Every metric, every source, every as-of date">
          <div className="audit">
            <h3>Is it any good, metric by metric</h3>
            <p className="fine">
              The structure the score is made of.
              {sqCat && " Filtered to the category you picked."}
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
                  size, covering {fmtPct(lt.coverage_pct, 0)} of the sampled weight. Non-filers
                  are skipped rather than guessed at, and the
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

            {ev.registry_drift && (
              <>
                <h3>Does the registry still match the fund</h3>
                <p className="fine">
                  The holdings and weights above are transcribed from the issuer
                  factsheet by hand. This compares that transcription against{" "}
                  {ev.registry_drift.against} (tier {ev.registry_drift.authority_tier}),
                  which is a second opinion, not a correction. Nothing here feeds any
                  score.
                </p>
                <table className="t drift-t">
                  <thead>
                    <tr>
                      <th>Figure</th>
                      <th className="r">Registry</th>
                      <th className="r">Observed</th>
                      <th className="r">Difference</th>
                      <th>Reading</th>
                    </tr>
                  </thead>
                  <tbody>
                    {ev.registry_drift.rows.map((r) => (
                      <tr key={r.field} data-status={r.status}>
                        <td>{r.field}</td>
                        <td className="r num">{r.registry}{typeof r.registry === "number" ? r.units : ""}</td>
                        <td className="r num">{r.observed}{typeof r.observed === "number" ? r.units : ""}</td>
                        <td className="r num">
                          {/* The gap between two percentages is percentage points. */}
                          {r.delta === null ? "·" : `${r.delta > 0 ? "+" : ""}${r.delta}${r.units === "%" ? "pp" : r.units}`}
                        </td>
                        <td>
                          <span className="drift-s" data-status={r.status}>{r.status}</span>
                          {r.note && <i className="drift-n">{r.note}</i>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <p className="fine">
                  {ev.registry_drift.note}
                  {ev.registry_drift.registry_as_of &&
                    ` Registry transcribed ${ev.registry_drift.registry_as_of}.`}
                </p>
              </>
            )}

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
