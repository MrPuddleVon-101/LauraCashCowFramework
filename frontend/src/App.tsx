import { asset } from "./lib/asset";
import { useEffect, useState } from "react";
import { engineIsLive, snapshotMeta, type Snapshot } from "./api";
import { useRevealAll } from "./lib/motion";
import { Nav, Progress, type View } from "./ui/Nav";
import { Tear } from "./ui/Marks";
import Boot from "./ui/Boot";
import Cursor from "./ui/Cursor";
import Home from "./views/Home";
import Score from "./views/Score";

const FROM_HASH = (): View => (window.location.hash.replace("#", "") === "score" ? "score" : "home");

export default function App() {
  const [view, setView] = useState<View>(FROM_HASH);
  useRevealAll();
  const [snap, setSnap] = useState<Snapshot | null>(null);
  // A ticker handed over from the overview, so pressing score there lands on a
  // verdict rather than on an empty field you have to fill in a second time.
  const [seed, setSeed] = useState<string>("");
  // Every load, not once per session. Reduced motion still skips it outright.
  const [booting, setBooting] = useState(true);

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

  function go(v: View, ticker?: string) {
    setView(v);
    setSeed(v === "score" ? (ticker ?? "") : "");
    window.history.replaceState(null, "", v === "home" ? "#" : "#score");
    window.scrollTo({ top: 0 });
  }

  return (
    <>
      {booting && <Boot onDone={() => setBooting(false)} />}
      <Cursor />
      <Nav view={view} go={go} />
      <Progress />

      <main key={view} className="main">
        {view === "home" ? <Home go={go} /> : <Score seed={seed} />}
      </main>

      <Tear fill="var(--ink)" seed={77} />
      <footer className="band band-ink foot">
        <div className="wrap foot-in">
          <div className="foot-brand">
            <img src={asset("brand/lccf-logo.png")} alt="" />
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
              Hosted as plain files, so the engine is not running behind this build. Every
              figure is its own output, frozen {snap.generated_on} under {snap.framework_version}.
            </p>
          )}
          <p className="foot-src">
            SEC EDGAR for filings, Nasdaq for prices, the U.S. Treasury for the curve.
            Fund facts are typed up from issuer factsheets by hand, and marked tier 2 wherever
            they are used.
          </p>
        </div>
      </footer>
    </>
  );
}
