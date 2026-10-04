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

async function get<T>(path: string): Promise<T> {
  const r = await fetch(`${BASE}${path}`);
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
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
  framework: () => get<any>("/framework"),
  client: () => get<any>("/client"),
  search: (q: string) => get<{ results: { ticker: string; name: string | null; type: string }[] }>(
    `/search?q=${encodeURIComponent(q)}`,
  ),
  evaluate: (body: {
    ticker: string;
    role?: string | null;
    position_pct?: number;
    target_payment_year?: number | null;
  }) => post<Evaluation>("/security/evaluate", body),
  liabilities: (asOf = 2027) => get<any>(`/liabilities?as_of_year=${asOf}`),
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
