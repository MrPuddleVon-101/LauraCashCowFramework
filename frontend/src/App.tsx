import { useEffect, useState } from "react";
import { engineIsLive, snapshotMeta, type Snapshot } from "./api";
import { useRevealAll } from "./lib/motion";
import { Nav, Progress, type View } from "./ui/Nav";
import { Tear } from "./ui/Marks";
import Home from "./views/Home";
import Score from "./views/Score";

const FROM_HASH = (): View => (window.location.hash.replace("#", "") === "score" ? "score" : "home");

export default function App() {
  const [view, setView] = useState<View>(FROM_HASH);
  useRevealAll();
  const [snap, setSnap] = useState<Snapshot | null>(null);

  useEffect(() => {
    let alive = true;
    engineIsLive().then((v) => {
      if (!v && alive) snapshotMeta().then((m) => alive && setSnap(m));
    });
    return () => { alive = false; };
  }, []);

  useEffect(() => {
    const onHash = () => setView(FROM_HASH());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  function go(v: View) {
    setView(v);
    window.history.replaceState(null, "", v === "home" ? "#" : "#score");
    window.scrollTo({ top: 0 });
  }

  return (
    <>
      <Nav view={view} go={go} />
      <Progress />

      <main key={view} className="main">
        {view === "home" ? <Home go={go} /> : <Score />}
      </main>

      <Tear fill="var(--ink)" seed={77} />
      <footer className="band band-ink foot">
        <div className="wrap foot-in">
          <div className="foot-brand">
            <img src="/brand/lccf-logo.png" alt="" />
            <div>
              <span className="foot-n">Stonky × Cash Cows</span>
              <span className="foot-s">The Laura Cash Cow Framework</span>
            </div>
          </div>

          <nav className="foot-nav" aria-label="Sections">
            <button onClick={() => go("home")} aria-current={view === "home"}>Start</button>
            <button onClick={() => go("score")} aria-current={view === "score"}>Score a ticker</button>
          </nav>

          {snap && (
            <p className="foot-snap">
              Hosted as plain files, so the scoring engine is not running behind this
              build. Every figure is the engine's own output, frozen on{" "}
              {snap.generated_on} under {snap.framework_version}.
            </p>
          )}
          <p className="foot-src">
            Company numbers come from SEC EDGAR, IFRS filers included. Prices and spreads from
            Nasdaq. The yield curve from the U.S. Treasury. Fund facts are typed up from issuer
            factsheets by hand, which is why they are marked tier 2 on every row that uses them.
          </p>
        </div>
      </footer>
    </>
  );
}
