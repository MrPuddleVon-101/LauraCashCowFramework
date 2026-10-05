export type Signal = "GREEN" | "AMBER_PLUS" | "AMBER" | "RED" | "INSUFFICIENT_DATA";

export type Metric = {
  key: string;
  label: string;
  category: string;
  weight: number;
  effective_weight: number;
  score: number;
  band: string;
  value: number | null;
  units: string;
  status: "OK" | "MISSING" | "NOT_APPLICABLE";
  higher_is_better: boolean;
  percentile: number | null;
  peer_median: number | null;
  peer_group: string;
  as_of: string | null;
  source: { name: string; url: string; authority_tier: number; authority_label: string } | null;
  interpretation: string;
  note: string;
  contribution: number;
};

export type Category = {
  key: string;
  points_available: number;
  points_declared: number;
  points_earned: number;
  score: number;
  metrics: Metric[];
};

export type ScoreCard = {
  model: string;
  score: number;
  band: string;
  points_earned: number;
  points_available: number;
  missing_weight_share: number;
  categories: Category[];
  category_labels: Record<string, string>;
  overlays: string[];
  derived?: Record<string, any>;
  lookthrough?: {
    coverage_pct: number;
    holdings: { ticker: string; name: string; weight: number; roe: number | null; fcf_margin: number | null }[];
    weighted: Record<string, number | null>;
  };
  peer_group?: { label: string; n: number; generated_at: string; source: string; source_url: string };
  risk_state?: { state: string; reason: string; downside_multiplier: number };
  role_label?: string;
  role_is_team_defined?: boolean;
};

export type Evaluation = {
  ticker: string;
  name: string;
  asset_type: string;
  asset_type_label: string;
  role: string;
  role_label: string;
  role_description: string;
  bucket: string;
  valid_roles: string[];
  position_pct: number;
  target_payment_year: number | null;
  framework_version: string;
  evaluated_at: string;
  snapshot_id?: number;
  scores: { security_quality: number; laura_fit: number; composite: number; data_confidence: number };
  signal: { signal: Signal; label: string; meaning: string; reasons: string[] };
  red_gate: { status: "PASS" | "REVIEW" | "FAIL"; failures: any[]; reviews: any[]; summary: string };
  risk_state: { state: string; reason: string };
  security_quality: ScoreCard;
  laura_fit: ScoreCard;
  data_confidence: { score: number; components: { key: string; label: string; weight: number; score: number }[] };
  position_sizing: { policy_cap_pct: number; suggested_pct: number; constraints: string[]; note: string };
  quote: any;
  risk_profile: any;
  portfolio_impact: any;
  funding: any;
  sponsor_range: any;
  strengths: { label: string; value: string; score: number; band: string; detail: string; peer_group: string; percentile: number | null }[];
  risks: Evaluation["strengths"];
  explanation: {
    why_the_score_is_what_it_is: string[];
    what_could_go_wrong: string[];
    why_laura_should_care: string[];
  };
  review_triggers: string[];
  details: Record<string, any>;
  sources: { name: string; url: string; authority_tier: number; authority_label: string; supports: string[] }[];
  decision_log_draft?: Record<string, any>;
  error?: string;
  message?: string;
};

const BASE = "/api";

/* --- live engine, or a frozen snapshot of it --------------------------------
 *
 * The scoring engine is Python. A static host cannot run it, so the build also
 * ships the engine's own output for a fixed universe of tickers. We probe the
 * API once: if it answers we use it and everything is live, and if it does not
 * we read the snapshot and the interface says so on its face. The two paths
 * return the same shapes, because the snapshot is literally what the engine
 * wrote.
 */

const SNAP = `${import.meta.env.BASE_URL}data`;

export type Snapshot = {
  generated_on: string;
  framework_version: string;
  position_pct: number;
  tickers: string[];
  index: { ticker: string; name: string; type: string; signal: string; composite: number }[];
  note: string;
};

let probe: Promise<boolean> | null = null;
let snapshot: Promise<Snapshot | null> | null = null;

/** True when a real engine is answering, false when we are reading the snapshot. */
export function engineIsLive(): Promise<boolean> {
  if (!probe) {
    probe = fetch(`${BASE}/health`)
      .then((r) => r.ok)
      .catch(() => false);
  }
  return probe;
}

export function snapshotMeta(): Promise<Snapshot | null> {
  if (!snapshot) {
    snapshot = fetch(`${SNAP}/manifest.json`)
      .then((r) => (r.ok ? r.json() : null))
      .catch(() => null);
  }
  return snapshot;
}

async function frozen<T>(file: string): Promise<T> {
  const r = await fetch(`${SNAP}/${file}`);
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}

async function get<T>(path: string, fallback: string): Promise<T> {
  if (await engineIsLive()) {
    const r = await fetch(`${BASE}${path}`);
    if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
    return r.json();
  }
  return frozen<T>(fallback);
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}

export const api = {
  framework: () => get<any>("/framework", "framework.json"),
  client: () => get<any>("/client", "client.json"),
  liabilities: (asOf = 2027) =>
    get<any>(`/liabilities?as_of_year=${asOf}`, "liabilities.json"),

  search: async (q: string) => {
    if (await engineIsLive()) {
      const r = await fetch(`${BASE}/search?q=${encodeURIComponent(q)}`);
      if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
      return r.json() as Promise<{ results: { ticker: string; name: string | null; type: string }[] }>;
    }
    const snap = await snapshotMeta();
    const needle = q.trim().toUpperCase();
    const results = (snap?.index ?? [])
      .filter((x) => x.ticker.includes(needle) || x.name.toUpperCase().includes(needle))
      .slice(0, 12)
      .map((x) => ({ ticker: x.ticker, name: x.name, type: x.type }));
    return { results };
  },

  evaluate: async (body: {
    ticker: string;
    role?: string | null;
    position_pct?: number;
    target_payment_year?: number | null;
  }): Promise<Evaluation> => {
    if (await engineIsLive()) return post<Evaluation>("/security/evaluate", body);
    const sym = body.ticker.trim().toUpperCase();
    try {
      return await frozen<Evaluation>(`eval/${sym}.json`);
    } catch {
      const snap = await snapshotMeta();
      return {
        error: "not_in_snapshot",
        message:
          `${sym} is not in the saved set. This build has no scoring engine behind it, ` +
          `so it can only show tickers that were scored in advance` +
          (snap ? ` on ${snap.generated_on}` : "") +
          `. Run the API locally and it will score anything.`,
      } as Evaluation;
    }
  },
};

export const fmtMoney = (n: number | null | undefined, dp = 0) =>
  n === null || n === undefined || Number.isNaN(n)
    ? "·"
    : `$${n.toLocaleString("en-US", { minimumFractionDigits: dp, maximumFractionDigits: dp })}`;

export const fmtNum = (n: number | null | undefined, dp = 2) =>
  n === null || n === undefined || Number.isNaN(n) ? "·" : n.toLocaleString("en-US", {
    minimumFractionDigits: dp, maximumFractionDigits: dp,
  });

export const fmtPct = (n: number | null | undefined, dp = 1) =>
  n === null || n === undefined || Number.isNaN(n) ? "·" : `${n.toFixed(dp)}%`;
