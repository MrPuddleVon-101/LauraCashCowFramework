# Running and deploying LCCF 2.0.0

## What changed in 2.0.0, and why scores are not comparable with 1.x

Three conceptual corrections, each of which moves numbers:

1. **A missing metric is no longer scored.** It used to be held at a neutral 62,
   which is above many real medians, so a security could be made to look better
   by failing to report. It is now excluded from the score, charged to data
   confidence, and the coverage is printed next to the result.
2. **A broad U.S. fund is no longer judged for being American.** It was scored on
   country Herfindahl, where being wholly U.S. scores 10 out of 100. Country
   breadth is not that fund's mandate; what it adds to Laura's country mix is
   asked incrementally by the fit model, where it already was. The slot now
   measures mandate adherence instead.
3. **The candidate trade actually moves the funding projection.** The gate was
   handed the pre-trade probability as the post-trade probability, so a trade
   could never fail on its own effect. Both are now projected.

Thresholds were re-set against the new distribution rather than carried over.
See `backend/calibration-report.json`.

## Environment

Copy `.env.example` to `.env`. Everything in it is optional: the application
starts without any key, `/api/health` names what is missing, and the interface
disables what it cannot do.

| Variable | What it unlocks | Without it |
|---|---|---|
| `FMP_API_KEY` | Global search, profiles, statements | No global search; registry and SEC filers only |
| `TWELVE_DATA_API_KEY` | Global quotes, history, exchange data | No non-US quotes |
| `OPENFIGI_API_KEY` | Higher identifier rate limit | Still works, anonymously |
| `SEC_USER_AGENT` | US filings | EDGAR returns 403; US fundamentals unavailable |
| `VITE_API_BASE_URL` | Frontend to backend | Frontend runs on the frozen snapshot |

Nothing here is read by the browser except `VITE_API_BASE_URL`, which is a URL.
No key is referenced in frontend source, and `tests/test_v2.py` scans the built
bundle to keep it that way.

## Local

```bash
./start.sh                   # API on 8077, interface on 5173
```

```bash
cd backend
./.venv/bin/python -m tests.test_audit     # 1.x regressions
./.venv/bin/python -m tests.test_v2        # 2.0.0 regressions
./.venv/bin/python -m scripts.calibrate    # panel, distribution, relationships
./.venv/bin/python -m scripts.build_snapshot
```

## Deploying the backend

The engine is Python, so Pages cannot run it. `render.yaml` builds the Docker
image and serves the API and the interface from one origin.

1. Create the Render service from the blueprint.
2. Set `SEC_USER_AGENT`, and any provider keys you hold, in the service
   environment.
3. Confirm `https://<service>.onrender.com/api/health` reports
   `"status": "ok"` and lists your providers.

CORS already names `https://mrpuddlevon-101.github.io` exactly. Add any preview
origin through `ALLOWED_ORIGINS`, comma separated.

## Pointing GitHub Pages at the live engine

Pages serves the interface; the engine lives on Render.

1. Repository → Settings → Secrets and variables → Actions → **Variables**.
2. Add `VITE_API_BASE_URL` = `https://<service>.onrender.com` (no trailing slash).
3. Re-run **Deploy to Pages**.

Until that variable is set the published interface runs on the frozen snapshot
and says so on its face. That is the designed fallback, not a failure.

## Keeping the fallback fresh

`.github/workflows/snapshot.yml` rebuilds the snapshot daily at 06:20 UTC and on
manual dispatch. It runs both test suites first, and
`scripts/build_snapshot.py` stages into a temporary directory and refuses to
publish if any ticker fails, so an outage leaves the last complete snapshot in
place rather than committing a partial one.

Provider keys come from repository **secrets** of the same names.

## Coverage

| Capability | Source | Needs a key | Status without keys |
|---|---|---|---|
| US fundamentals | SEC EDGAR | `SEC_USER_AGENT` only | Working |
| Treasury curve | U.S. Treasury | No | Working |
| US quotes and spreads | Nasdaq | No | Working |
| Identifier resolution | OpenFIGI | Optional | Working, anonymous rate limit |
| Fixed-income maths | Instrument terms | No | Working, no provider involved |
| Fund corroboration | Yahoo via yfinance | No | Working, tier 2 |
| Global search | FMP | Yes | **Unavailable** |
| Global quotes | Twelve Data | Yes | **Unavailable** |
| Non-US fundamentals | FMP | Yes | **Unavailable** |

Exchange coverage is whatever the connected providers reach. The engine does not
claim to cover every listed security, and `/api/health` reports the truth.

## Limitations

- Without `FMP_API_KEY` and `TWELVE_DATA_API_KEY`, non-US securities can be
  *identified* (OpenFIGI) but not *scored*: there is no fundamentals or quote
  source for them. The interface reports this rather than guessing.
- Peer percentiles are SEC-derived and therefore US. A non-US stock scored
  against them would be mislabelled, so that path is closed rather than
  approximated.
- Every fund takes a flat 10/100 on peer-group adequacy because funds are scored
  against absolute bands, not peers. This is a deliberate confidence cost, not a
  quality judgement, and it does not prevent a fund reaching green.
- The portfolio in `backend/data/portfolios.json` is a fixture. Confirm it
  against the real book before trusting incremental diversification or sizing.
