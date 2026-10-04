import { useEffect, useRef, useState } from "react";
import { api, type Evaluation } from "../api";
import { Btn, Note, Paper, Working } from "../ui/Kit";
import { Arrow, Spark } from "../ui/Marks";
import Verdict from "./Verdict";

const ROLES: [string, string, string][] = [
  ["", "Auto", "Let the engine pick the obvious job"],
  ["CG", "Core growth", "The spine of the growth sleeve"],
  ["SG", "Satellite", "One researched position, sized small"],
  ["ID", "International", "Exposure outside the United States"],
  ["LM", "Liability matcher", "Dedicated to one payment year"],
  ["LR", "Liquidity", "Short dated, covers timing"],
  ["LG", "Residual growth", "Capital that stays invested after 2033"],
  ["DA", "Defensive", "Ballast, behaves unlike equities"],
];

const PICKS: { t: string; r: string; y?: number; why: string }[] = [
  { t: "AVUS", r: "CG", why: "the core" },
  { t: "VXUS", r: "ID", why: "outside the US" },
  { t: "IBTM", r: "LM", y: 2033, why: "dated to 2033" },
  { t: "BND", r: "LM", y: 2033, why: "fails the gate" },
  { t: "NVDA", r: "SG", why: "a single name" },
  { t: "SGOV", r: "LR", why: "dry powder" },
  { t: "SMH", r: "SG", why: "one sector" },
  { t: "COST", r: "SG", why: "quality, priced" },
];

const STEPS: [string, string, string][] = [
  ["01", "Work out what it is", "A Treasury and a growth stock cannot share a scoring model."],
  ["02", "Go and check", "Filings from SEC EDGAR. Price and spread from the exchange. No estimates."],
  ["03", "Rank it honestly", "Against 1,613 registrants, not five companies somebody picked."],
  ["04", "Run the gate first", "Before any weighting. A hard failure cannot be outscored later."],
];

export default function Score() {
  const [q, setQ] = useState("");
  const [role, setRole] = useState("");
  const [position, setPosition] = useState(8);
  const [year, setYear] = useState<number | "">("");
  const [sug, setSug] = useState<{ ticker: string; name: string | null; type: string }[]>([]);
  const [showSug, setShowSug] = useState(false);
  const [cursor, setCursor] = useState(-1);
  const [result, setResult] = useState<Evaluation | null>(null);
  const [need, setNeed] = useState({ sqs: 85, lpfs: 85, ccs: 85, dcs: 85 });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const box = useRef<HTMLDivElement>(null);
  const field = useRef<HTMLInputElement>(null);
  const out = useRef<HTMLDivElement>(null);

  useEffect(() => { field.current?.focus(); }, []);

  // The gate row quotes real thresholds, so it reads them from the locked
  // framework rather than hard coding numbers that could drift from policy.
  useEffect(() => {
    let live = true;
    api.framework().then((f) => {
      if (!live || !f?.policy) return;
      setNeed({
        sqs: f.policy.green_min_sqs, lpfs: f.policy.green_min_lpfs,
        ccs: f.policy.green_min_ccs, dcs: f.policy.green_min_dcs,
      });
    }).catch(() => { /* the defaults match the locked framework */ });
    return () => { live = false; };
  }, []);

  useEffect(() => {
    if (q.trim().length < 1) { setSug([]); return; }
    const id = setTimeout(async () => {
      try { setSug((await api.search(q.trim())).results); } catch { /* the field works without it */ }
    }, 150);
    return () => clearTimeout(id);
  }, [q]);

  useEffect(() => {
    const down = (e: MouseEvent) => {
      if (box.current && !box.current.contains(e.target as Node)) setShowSug(false);
    };
    document.addEventListener("mousedown", down);
    return () => document.removeEventListener("mousedown", down);
  }, []);

  async function run(ticker?: string, forcedRole?: string, forcedYear?: number) {
    const sym = (ticker ?? q).trim().toUpperCase();
    if (!sym) return;
    setShowSug(false);
    setBusy(true);
    setError(null);
    setQ(sym);
    try {
      const ev = await api.evaluate({
        ticker: sym,
        role: forcedRole ?? role ?? null,
        position_pct: position,
        target_payment_year: forcedYear ?? (year === "" ? null : Number(year)),
      });
      if (ev.error) {
        setError(ev.message ?? `We could not make sense of ${sym}.`);
        setResult(null);
      } else {
        setResult(ev);
        setRole(ev.role);
        requestAnimationFrame(() =>
          out.current?.scrollIntoView({ behavior: "smooth", block: "start" }));
      }
    } catch (e: any) {
      setError(`The engine did not answer. ${e?.message ?? ""}`);
      setResult(null);
    } finally {
      setBusy(false);
    }
  }

  function keys(e: React.KeyboardEvent<HTMLInputElement>) {
    if (!showSug || sug.length === 0) {
      if (e.key === "Enter") run();
      return;
    }
    if (e.key === "ArrowDown") { e.preventDefault(); setCursor((i) => Math.min(sug.length - 1, i + 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setCursor((i) => Math.max(-1, i - 1)); }
    else if (e.key === "Enter") { e.preventDefault(); run(cursor >= 0 ? sug[cursor].ticker : undefined); }
    else if (e.key === "Escape") setShowSug(false);
  }

  const wantsYear = role === "LM";

  return (
    <div className="band band-paper view">
      <div className="wrap">
        <header className="view-head">
          <div>
            <span className="tag">The desk</span>
            <h1 className="view-h">Throw a ticker at it</h1>
          </div>
          <p className="view-sub">
            Stocks, funds, Treasuries, cash. Tell it what the thing is for and it will
            tell you whether that is a good idea.
          </p>
        </header>

        <Paper seed={3} tilt={0.5} className="desk" anim="rise">
          <div className="desk-main" ref={box}>
            <label className="field">
              <span className="field-k">Symbol</span>
              <input
                ref={field}
                value={q}
                placeholder="AVUS"
                spellCheck={false}
                autoComplete="off"
                maxLength={8}
                onChange={(e) => { setQ(e.target.value.toUpperCase()); setShowSug(true); setCursor(-1); }}
                onFocus={() => setShowSug(true)}
                onKeyDown={keys}
              />
            </label>
            <Btn kind="go" size="lg" arrow onClick={() => run()} disabled={busy || !q.trim()}>
              {busy ? "Thinking" : "Run it"}
            </Btn>

            {showSug && sug.length > 0 && (
              <div className="sug">
                {sug.map((s, i) => (
                  <button key={s.ticker} data-on={i === cursor || undefined}
                          onPointerEnter={() => setCursor(i)} onClick={() => run(s.ticker)}>
                    <span className="sug-t num">{s.ticker}</span>
                    <span className="sug-n">{s.name ?? ""}</span>
                    <span className="sug-y">{s.type}</span>
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="desk-opts">
            <div className="opt">
              <span className="opt-k">What is it for</span>
              <div className="opt-chips">
                {ROLES.map(([k, label, hint]) => (
                  <button key={k || "auto"} className="rolechip" data-on={role === k || undefined}
                          title={hint} onClick={() => setRole(k)}>
                    {label}
                  </button>
                ))}
              </div>
            </div>

            <div className="opt opt-slide">
              <span className="opt-k">How big a slice</span>
              <div className="slide">
                <input type="range" min={0} max={30} step={0.5} value={position}
                       aria-label="Position size, percent of the portfolio"
                       onChange={(e) => setPosition(Number(e.target.value))} />
                <span className="slide-v num">{position.toFixed(1)}<small>%</small></span>
              </div>
            </div>

            {wantsYear && (
              <div className="opt opt-years">
                <span className="opt-k">Pointed at which payment</span>
                <div className="opt-chips">
                  <button className="rolechip" data-on={year === "" || undefined} onClick={() => setYear("")}>
                    None
                  </button>
                  {Array.from({ length: 10 }, (_, i) => 2033 + i).map((y) => (
                    <button key={y} className="rolechip num" data-on={year === y || undefined}
                            onClick={() => setYear(y)}>{y}</button>
                  ))}
                </div>
              </div>
            )}
          </div>

          <div className="desk-picks">
            <span className="tag">Or borrow one of ours</span>
            {PICKS.map((p, i) => (
              <button key={p.t} className="pick" style={{ ["--d" as string]: `${i * 40}ms` }}
                      onClick={() => { setRole(p.r); setYear(p.y ?? ""); run(p.t, p.r, p.y); }}>
                <b className="num">{p.t}</b>
                <i>{p.why}</i>
              </button>
            ))}
          </div>
        </Paper>

        <div ref={out} />

        {busy && <Working what={`Reading filings, prices and 1,613 peers for ${q}`} />}

        {error && !busy && <Note tone="bad">{error}</Note>}

        {!result && !busy && !error && (
          <div className="steps">
            {STEPS.map(([n, t, d], i) => (
              <div className="step" key={n} data-anim="rise" style={{ ["--delay" as string]: `${i * 90}ms` }}>
                <span className="step-n num">{n}</span>
                <span className="step-t">{t}</span>
                <span className="step-d">{d}</span>
                {i < 3 && <Arrow className="step-arrow" w={54} h={26} color="var(--ink-4)" />}
              </div>
            ))}
            <Spark size={20} className="steps-sp" />
          </div>
        )}
      </div>

      {result && !busy && <Verdict ev={result} need={need} />}
    </div>
  );
}
