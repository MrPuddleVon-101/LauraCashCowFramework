/* What you are actually looking at.
 *
 * The interface used to say "live prices" and "any US ticker" while serving a
 * file frozen weeks earlier, because the only thing it knew was whether a fetch
 * had failed. The engine now describes itself, and this turns that description
 * into one badge that is never wrong by omission.
 */

import { useEffect, useState } from "react";
import { engineIsLive, health, snapshotMeta, type Mode, type Snapshot } from "../api";

export type ModeState = {
  mode: Mode;
  /** False whenever the controls cannot produce a new score. */
  canRecalculate: boolean;
  version: string;
  snapshotDate: string | null;
  universe: number | null;
  degraded: string[];
  globalSearch: boolean;
  checked: boolean;
};

const IDLE: ModeState = {
  mode: "SNAPSHOT", canRecalculate: false, version: "LCCF",
  snapshotDate: null, universe: null, degraded: [], globalSearch: false, checked: false,
};

/** One answer for the whole interface, resolved once. */
export function useMode(): ModeState {
  const [state, setState] = useState<ModeState>(IDLE);

  useEffect(() => {
    let alive = true;
    engineIsLive().then(async (live) => {
      if (!alive) return;
      if (live) {
        const h = health();
        setState({
          mode: "LIVE",
          canRecalculate: true,
          version: h?.framework_version ?? "LCCF",
          snapshotDate: null,
          universe: null,
          degraded: h?.degraded ?? [],
          globalSearch: Boolean(h?.coverage?.global_search),
          checked: true,
        });
        return;
      }
      const snap: Snapshot | null = await snapshotMeta().catch(() => null);
      if (!alive) return;
      setState({
        mode: "SNAPSHOT",
        canRecalculate: false,
        version: snap?.framework_version ?? "LCCF",
        snapshotDate: snap?.generated_on ?? null,
        universe: snap?.tickers?.length ?? null,
        degraded: [],
        globalSearch: false,
        checked: true,
      });
    });
    return () => { alive = false; };
  }, []);

  return state;
}

const COPY: Record<Mode, { label: string; says: string }> = {
  LIVE: { label: "Live engine", says: "Scoring now, against current data." },
  CACHED: { label: "Cached", says: "Served from cache rather than refetched." },
  STALE: { label: "Stale", says: "The cache is past its refresh window." },
  SNAPSHOT: { label: "Historical snapshot", says: "A frozen result. Nothing here recalculates." },
};

/** The badge itself. Small, always present, never optimistic. */
export function ModeBadge({ state, className = "" }: { state: ModeState; className?: string }) {
  if (!state.checked) {
    return (
      <span className={`mode mode-wait ${className}`} role="status">
        <i className="mode-dot" />
        <b>Waking the engine</b>
        <span>It may have idled. This can take up to twenty seconds.</span>
      </span>
    );
  }
  const c = COPY[state.mode];
  return (
    <span className={`mode mode-${state.mode.toLowerCase()} ${className}`} role="status">
      <i className="mode-dot" />
      <b>{c.label}</b>
      <span>
        {c.says}
        {state.mode === "SNAPSHOT" && state.snapshotDate && ` Generated ${state.snapshotDate}.`}
        {state.mode === "SNAPSHOT" && state.universe && ` ${state.universe} saved securities.`}
        {state.mode === "LIVE" && state.degraded.length > 0 &&
          ` ${state.degraded.join(" and ")} unavailable, so global search is off.`}
      </span>
      <em className="mode-v">{state.version}</em>
    </span>
  );
}
