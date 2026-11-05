/* The world.
 *
 * One WebGL scene behind the entire page, not a decoration inside one section.
 * It is a chart, built as real geometry in real space, and scrolling flies the
 * camera up it: the reader starts at the medallion on the floor of the thing
 * and climbs the line from 2027 to 2036, which is exactly the span the
 * framework is arguing about.
 *
 * The line is a seeded random walk with upward drift, so it is honest about
 * being an illustration rather than pretending to be a price series. The
 * candles hanging off it, the grid it floats over and the fog it fades into
 * are all there to give the climb a sense of distance; without them the camera
 * move is invisible.
 *
 * Content sits on top. Some bands are opaque and some are glass, so the page
 * surfaces for air and then dives again rather than running one effect flat
 * from top to bottom.
 *
 * It yields completely: no WebGL, or a reader who asked for less motion, and
 * nothing mounts. Every band has its own background and the page reads fine.
 */

import { useEffect, useRef } from "react";
import * as THREE from "three";

import { asset } from "../lib/asset";
import { ScrollTrigger, gsap, prefersReduced } from "../lib/scroll";

const GOLD = 0xeba618;
const GOLD_HI = 0xffcf55;
const NIGHT = 0x0c0908;
const ROSE = 0xef9179;

/** Deterministic noise, so the chart is the same shape on every load. */
function makeWalk(n: number) {
  let s = 20361107;
  const rnd = () => ((s = (s * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff);
  const pts: THREE.Vector3[] = [];
  let y = 0;
  let v = 0;
  for (let i = 0; i < n; i++) {
    const t = i / (n - 1);
    // Drift up, with the volatility easing off as the run goes on: the early
    // years are the ones that can go wrong.
    v += (rnd() - 0.47) * (0.9 - t * 0.5);
    v *= 0.84;
    y += v + 0.2;
    pts.push(new THREE.Vector3(
      Math.sin(t * Math.PI * 1.4) * 13 + (rnd() - 0.5) * 2.4,  // wander sideways
      y,
      -t * 780,
    ));
  }
  return pts;
}

function canWebGL() {
  try {
    const c = document.createElement("canvas");
    return !!(c.getContext("webgl2") || c.getContext("webgl"));
  } catch { return false; }
}

export default function ChartWorld() {
  const host = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = host.current;
    if (!el) return;
    if (prefersReduced() || !canWebGL()) return;

    let raf = 0;
    let visible = true;

    const scene = new THREE.Scene();
    scene.fog = new THREE.Fog(NIGHT, 90, 430);

    const camera = new THREE.PerspectiveCamera(46, 1, 0.1, 600);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: "high-performance" });
    // A phone is doing enough work already, and the scene is heavily washed
    // there, so detail it will never show is not worth the fill rate.
    const dpr = () => Math.min(window.devicePixelRatio, window.innerWidth < 760 ? 1.25 : 1.75);
    renderer.setPixelRatio(dpr());
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.45;
    el.appendChild(renderer.domElement);
    renderer.domElement.classList.add("world-c");

    /* --- the line ------------------------------------------------------- */

    const pts = makeWalk(170);
    const curve = new THREE.CatmullRomCurve3(pts, false, "catmullrom", 0.4);

    const tube = new THREE.Mesh(
      new THREE.TubeGeometry(curve, 620, 0.85, 10, false),
      new THREE.MeshStandardMaterial({
        color: GOLD_HI, emissive: GOLD_HI, emissiveIntensity: 3.4,
        metalness: 0.4, roughness: 0.3,
      }),
    );
    scene.add(tube);

    // A soft halo around the line, so it reads as lit rather than painted.
    const halo = new THREE.Mesh(
      new THREE.TubeGeometry(curve, 320, 2.4, 8, false),
      new THREE.MeshBasicMaterial({
        color: GOLD_HI, transparent: true, opacity: 0.22,
        blending: THREE.AdditiveBlending, depthWrite: false,
      }),
    );
    scene.add(halo);

    /* --- the candles ---------------------------------------------------- */

    const FLOOR = -7;
    const candleGeo = new THREE.BoxGeometry(1, 1, 1);
    const upMat = new THREE.MeshStandardMaterial({ color: GOLD_HI, metalness: 0.3, roughness: 0.6, transparent: true, opacity: 0.72 });
    const dnMat = new THREE.MeshStandardMaterial({ color: ROSE, metalness: 0.3, roughness: 0.6, transparent: true, opacity: 0.72 });

    const COUNT = 128;
    const up = new THREE.InstancedMesh(candleGeo, upMat, COUNT);
    const dn = new THREE.InstancedMesh(candleGeo, dnMat, COUNT);
    const m = new THREE.Matrix4();
    let ui = 0;
    let di = 0;
    for (let i = 0; i < COUNT; i++) {
      const t = i / (COUNT - 1);
      const p = curve.getPointAt(Math.min(0.999, t));
      const prev = curve.getPointAt(Math.max(0, t - 0.01));
      const h = p.y - FLOOR;
      m.makeScale(2.8, h, 2.8);
      m.setPosition(p.x, FLOOR + h / 2, p.z);
      if (p.y >= prev.y) { up.setMatrixAt(ui++, m); } else { dn.setMatrixAt(di++, m); }
    }
    up.count = ui;
    dn.count = di;
    up.instanceMatrix.needsUpdate = true;
    dn.instanceMatrix.needsUpdate = true;
    scene.add(up, dn);

    /* --- the floor ------------------------------------------------------ */

    const grid = new THREE.GridHelper(900, 90, GOLD, 0x3a2c18);
    grid.position.y = FLOOR - 10;
    grid.position.z = -280;
    (grid.material as THREE.Material).transparent = true;
    (grid.material as THREE.Material).opacity = 0.14;
    scene.add(grid);

    /* --- the medallion you start on ------------------------------------- */

    const tex = new THREE.TextureLoader().load(asset("brand/lccf-logo.png"));
    tex.colorSpace = THREE.SRGBColorSpace;

    const coin = new THREE.Group();
    const blank = new THREE.Mesh(
      new THREE.CylinderGeometry(7, 7, 0.9, 64),
      new THREE.MeshStandardMaterial({ color: GOLD, metalness: 1, roughness: 0.3 }),
    );
    blank.rotation.x = Math.PI / 2;
    coin.add(blank);
    for (const side of [1, -1]) {
      const face = new THREE.Mesh(
        new THREE.CircleGeometry(5.6, 64),
        new THREE.MeshStandardMaterial({ map: tex, transparent: true, metalness: 0.2, roughness: 0.6, side: THREE.DoubleSide }),
      );
      face.position.z = side * 0.48;
      face.rotation.y = side > 0 ? 0 : Math.PI;
      coin.add(face);
    }
    coin.position.set(pts[0].x, pts[0].y + 1, 30);
    scene.add(coin);

    /* --- dust ----------------------------------------------------------- */

    const N = 700;
    const pos = new Float32Array(N * 3);
    for (let i = 0; i < N; i++) {
      pos[i * 3] = (Math.random() - 0.5) * 180;
      pos[i * 3 + 1] = (Math.random() - 0.5) * 220 + 40;
      pos[i * 3 + 2] = -Math.random() * 600 + 40;
    }
    const dustGeo = new THREE.BufferGeometry();
    dustGeo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    const dust = new THREE.Points(dustGeo, new THREE.PointsMaterial({
      color: GOLD_HI, size: 0.5, transparent: true, opacity: 0.5,
      depthWrite: false, blending: THREE.AdditiveBlending, sizeAttenuation: true,
    }));
    scene.add(dust);

    /* --- light ----------------------------------------------------------- */

    scene.add(new THREE.AmbientLight(0xffe3b0, 0.9));
    const key = new THREE.DirectionalLight(0xfff0d0, 2.2);
    key.position.set(20, 60, 30);
    scene.add(key);
    const warm = new THREE.PointLight(GOLD, 900, 260);
    warm.position.set(0, 20, -120);
    scene.add(warm);

    /* --- the flight ------------------------------------------------------ */

    // Progress along the page drives progress along the curve. The camera sits
    // behind and above the line looking a little further up it, so the reader
    // is always climbing toward something.
    const prog = { t: 0 };
    const aim = { x: 0, y: 0 };
    const look = new THREE.Vector3();
    const here = new THREE.Vector3();

    const place = () => {
      const t = Math.min(0.995, Math.max(0, prog.t));
      curve.getPointAt(t, here);
      curve.getPointAt(Math.min(0.999, t + 0.1), look);

      camera.position.set(
        here.x + 34 + aim.x * 10,
        here.y + 15 + aim.y * 6,
        here.z + 52,
      );
      camera.lookAt(look.x - 6, look.y - 1, look.z);
      // A slow roll, so the horizon is never dead level.
      camera.rotation.z = Math.sin(t * 7) * 0.035 + aim.x * 0.03;
    };

    const st = ScrollTrigger.create({
      trigger: document.documentElement,
      start: 0,
      end: () => document.documentElement.scrollHeight - window.innerHeight,
      scrub: 1.1,
      onUpdate: (self) => { prog.t = self.progress; },
      invalidateOnRefresh: true,
    });

    const intro = gsap.from(prog, { t: -0.06, duration: 2.4, ease: "expo.out" });

    const onMove = (e: PointerEvent) => {
      aim.x = (e.clientX / window.innerWidth - 0.5) * 1.1;
      aim.y = (e.clientY / window.innerHeight - 0.5) * -1;
    };
    window.addEventListener("pointermove", onMove, { passive: true });

    const io = new IntersectionObserver(([e]) => { visible = e.isIntersecting; }, { threshold: 0 });
    io.observe(el);

    const clock = new THREE.Clock();
    const frame = () => {
      raf = requestAnimationFrame(frame);
      if (!visible) return;
      const d = clock.getDelta();
      const t = clock.getElapsedTime();
      place();
      coin.rotation.y = t * 0.3;
      dust.rotation.y = t * 0.008;
      grid.position.z = -280 + ((t * 2) % 10);
      void d;
      renderer.render(scene, camera);
    };

    const resize = () => {
      const w = window.innerWidth;
      const h = window.innerHeight;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setPixelRatio(dpr());
      renderer.setSize(w, h, false);
    };
    window.addEventListener("resize", resize);
    resize();
    frame();

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("resize", resize);
      io.disconnect();
      st.kill();
      intro.kill();
      scene.traverse((o) => {
        const mesh = o as THREE.Mesh;
        mesh.geometry?.dispose?.();
        const mat = mesh.material as THREE.Material | THREE.Material[] | undefined;
        if (Array.isArray(mat)) mat.forEach((x) => x.dispose());
        else mat?.dispose();
      });
      tex.dispose();
      renderer.dispose();
      renderer.domElement.remove();
    };
  }, []);

  return <div className="world" ref={host} aria-hidden="true" />;
}
