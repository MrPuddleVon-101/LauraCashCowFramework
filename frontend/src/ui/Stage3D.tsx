/* The medallion.
 *
 * A struck gold coin, lit for real and turning in real space, with a ring of
 * smaller coins orbiting it and a field of dust catching the key light. The
 * framework stamps a verdict onto a candidate, so the cover should show the
 * stamp itself rather than a drawing of one.
 *
 * Everything here is built from geometry at runtime. No model files, no
 * loaders beyond the one logo texture, so the whole scene costs a few hundred
 * bytes of scene graph on top of three itself.
 *
 * It yields: no WebGL, or a reader who has asked for less motion, and the
 * canvas never mounts. The collage underneath is the fallback and stands on
 * its own.
 */

import { useEffect, useRef } from "react";
import * as THREE from "three";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";

import { asset } from "../lib/asset";
import { gsap, ScrollTrigger, prefersReduced } from "../lib/scroll";

const GOLD = 0xe2a014;
const GOLD_HI = 0xffd470;
const INK = 0x16120f;

function canWebGL() {
  try {
    const c = document.createElement("canvas");
    return !!(c.getContext("webgl2") || c.getContext("webgl"));
  } catch {
    return false;
  }
}

/** One coin: a gold blank with the mark printed on both faces. */
function makeCoin(radius: number, thickness: number, face: THREE.Texture | null) {
  const group = new THREE.Group();

  const metal = new THREE.MeshStandardMaterial({
    color: GOLD,
    metalness: 1,
    roughness: 0.28,
  });

  const blank = new THREE.Mesh(
    new THREE.CylinderGeometry(radius, radius, thickness, 72, 1),
    metal,
  );
  // Cylinders stand up the Y axis; a coin faces the reader.
  blank.rotation.x = Math.PI / 2;
  group.add(blank);

  // A milled edge. Cheap, and it is what sells the object as struck metal
  // the moment it turns.
  const knurl = new THREE.Mesh(
    new THREE.TorusGeometry(radius * 0.995, thickness * 0.46, 8, 96),
    new THREE.MeshStandardMaterial({ color: GOLD_HI, metalness: 1, roughness: 0.42 }),
  );
  group.add(knurl);

  // The raised field the mark sits in.
  const field = new THREE.MeshStandardMaterial({ color: GOLD_HI, metalness: 1, roughness: 0.5 });
  for (const side of [1, -1]) {
    const inset = new THREE.Mesh(
      new THREE.CylinderGeometry(radius * 0.86, radius * 0.86, thickness * 1.02, 64),
      field,
    );
    inset.rotation.x = Math.PI / 2;
    group.add(inset);

    if (face) {
      const print = new THREE.Mesh(
        new THREE.CircleGeometry(radius * 0.72, 64),
        new THREE.MeshStandardMaterial({
          map: face,
          transparent: true,
          metalness: 0.15,
          roughness: 0.62,
          side: THREE.DoubleSide,
        }),
      );
      print.position.z = side * (thickness * 0.52);
      print.rotation.y = side > 0 ? 0 : Math.PI;
      group.add(print);
    }
  }

  return group;
}

export default function Stage3D() {
  const host = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = host.current;
    if (!el) return;
    if (prefersReduced() || !canWebGL()) return;

    let raf = 0;
    let alive = true;
    let visible = true;

    const scene = new THREE.Scene();

    const camera = new THREE.PerspectiveCamera(34, 1, 0.1, 100);
    // On a narrow screen the canvas sits behind the whole cover rather than
    // beside it, so the object has to stand back and sit high: the headline
    // owns the lower half and has to stay readable over it.
    // Matched to the stylesheet's own breakpoint, not to the canvas box: below
    // it the canvas is the backdrop for the whole cover rather than one column
    // of it, and measuring the box gets that wrong whenever the window is
    // narrow but the canvas is full width.
    const narrow = () => window.innerWidth < 960;
    let dolly = 15.5;
    camera.position.set(0, 0, dolly);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: "high-performance" });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.15;
    el.appendChild(renderer.domElement);
    renderer.domElement.classList.add("stage3d-c");

    // A room gives the metal something to reflect. Without it gold reads as
    // flat mustard no matter how the lights are arranged.
    const pmrem = new THREE.PMREMGenerator(renderer);
    const env = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
    scene.environment = env;

    const tex = new THREE.TextureLoader().load(asset("brand/lccf-logo.png"));
    tex.colorSpace = THREE.SRGBColorSpace;
    tex.anisotropy = renderer.capabilities.getMaxAnisotropy();

    /* --- the object ------------------------------------------------------ */

    const rig = new THREE.Group();           // mouse tilt
    const spin = new THREE.Group();          // scroll + idle turn
    rig.add(spin);
    scene.add(rig);

    const medallion = makeCoin(1.95, 0.3, tex);
    spin.add(medallion);

    // The orbit. Two rings at different radii and tilts, turning against each
    // other, so the silhouette never settles into a pattern.
    const orbits: THREE.Group[] = [];
    const RINGS = [
      { n: 9, r: 3.2, tilt: 0.42, size: 0.38, speed: 0.16 },
      { n: 6, r: 4.2, tilt: -0.62, size: 0.26, speed: -0.1 },
    ];
    for (const ring of RINGS) {
      const g = new THREE.Group();
      g.rotation.x = ring.tilt;
      g.userData.speed = ring.speed;
      for (let i = 0; i < ring.n; i++) {
        const a = (i / ring.n) * Math.PI * 2;
        const coin = makeCoin(ring.size, 0.07, null);
        coin.position.set(Math.cos(a) * ring.r, Math.sin(a) * ring.r * 0.42, Math.sin(a) * ring.r * 0.7);
        coin.rotation.set(Math.random() * 3, Math.random() * 3, Math.random() * 3);
        coin.userData.tumble = 0.4 + Math.random() * 0.7;
        g.add(coin);
      }
      orbits.push(g);
      rig.add(g);
    }

    // Dust in the key light.
    const COUNT = 260;
    const pos = new Float32Array(COUNT * 3);
    for (let i = 0; i < COUNT; i++) {
      pos[i * 3] = (Math.random() - 0.5) * 16;
      pos[i * 3 + 1] = (Math.random() - 0.5) * 11;
      pos[i * 3 + 2] = (Math.random() - 0.5) * 9 - 2;
    }
    const dustGeo = new THREE.BufferGeometry();
    dustGeo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    const dustMat = new THREE.PointsMaterial({
      color: GOLD_HI, size: 0.045, transparent: true, opacity: 0.55,
      depthWrite: false, blending: THREE.AdditiveBlending,
    });
    const dust = new THREE.Points(dustGeo, dustMat);
    scene.add(dust);

    /* --- light ----------------------------------------------------------- */

    const key = new THREE.DirectionalLight(0xfff0d0, 3.1);
    key.position.set(4, 6, 7);
    scene.add(key);

    const rim = new THREE.DirectionalLight(0xffb13d, 2.6);
    rim.position.set(-6, -2, -4);
    scene.add(rim);

    const bounce = new THREE.PointLight(0xef9179, 14, 24);
    bounce.position.set(-3.5, -3, 3);
    scene.add(bounce);

    scene.add(new THREE.AmbientLight(INK, 1.4));

    /* --- motion ---------------------------------------------------------- */

    const tilt = { x: 0, y: 0 };
    const aim = { x: 0, y: 0 };

    const onMove = (e: PointerEvent) => {
      aim.y = (e.clientX / window.innerWidth - 0.5) * 0.72;
      aim.x = (e.clientY / window.innerHeight - 0.5) * 0.44;
    };
    window.addEventListener("pointermove", onMove, { passive: true });

    // Scroll drives the coin over: it turns away from the reader and sinks as
    // the cover leaves, which is what hands the page to the section below.
    const st = ScrollTrigger.create({
      trigger: el.closest(".hero") ?? el,
      start: "top top",
      end: "bottom top",
      scrub: 1,
      onUpdate: (self) => {
        spin.rotation.y = self.progress * Math.PI * 1.65;
        spin.position.y = -self.progress * 2.4;
        spin.scale.setScalar(1 - self.progress * 0.25);
        camera.position.z = dolly + self.progress * 4.5;
      },
    });

    const intro = gsap.from(spin.rotation, {
      y: -Math.PI * 1.4, duration: 2.4, ease: "expo.out", delay: 0.2,
    });
    const introScale = gsap.from(spin.scale, {
      x: 0.2, y: 0.2, z: 0.2, duration: 1.8, ease: "expo.out", delay: 0.2,
    });

    const io = new IntersectionObserver(([e]) => { visible = e.isIntersecting; }, { threshold: 0 });
    io.observe(el);

    const clock = new THREE.Clock();

    const frame = () => {
      raf = requestAnimationFrame(frame);
      if (!visible) return;

      const t = clock.getElapsedTime();
      const d = clock.getDelta();

      tilt.x += (aim.x - tilt.x) * 0.055;
      tilt.y += (aim.y - tilt.y) * 0.055;
      rig.rotation.x = tilt.x;
      rig.rotation.y = tilt.y;

      // An idle turn under the scroll value, so the object is alive even when
      // the page is still.
      medallion.rotation.y = t * 0.22;
      medallion.position.y = Math.sin(t * 0.8) * 0.12;

      for (const g of orbits) {
        g.rotation.z += (g.userData.speed as number) * d;
        for (const c of g.children) {
          c.rotation.y += (c.userData.tumble as number) * d;
          c.rotation.x += (c.userData.tumble as number) * d * 0.4;
        }
      }

      dust.rotation.y = t * 0.02;
      renderer.render(scene, camera);
    };

    const resize = () => {
      const w = el.clientWidth;
      const h = el.clientHeight;
      if (!w || !h) return;
      dolly = narrow() ? 26.5 : 15.5;
      camera.position.z = dolly + (st?.progress ?? 0) * 4.5;
      rig.position.y = narrow() ? 5.6 : 0;
      // Off centre on desktop, so the outer orbit clears the headline column.
      rig.position.x = narrow() ? 0 : 1.25;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h, false);
    };

    const ro = new ResizeObserver(resize);
    ro.observe(el);
    resize();
    frame();

    return () => {
      alive = false;
      void alive;
      cancelAnimationFrame(raf);
      window.removeEventListener("pointermove", onMove);
      io.disconnect();
      ro.disconnect();
      st.kill();
      intro.kill();
      introScale.kill();
      scene.traverse((o) => {
        const m = o as THREE.Mesh;
        if (m.geometry) m.geometry.dispose();
        const mat = m.material as THREE.Material | THREE.Material[] | undefined;
        if (Array.isArray(mat)) mat.forEach((x) => x.dispose());
        else mat?.dispose();
      });
      tex.dispose();
      env.dispose();
      pmrem.dispose();
      renderer.dispose();
      renderer.domElement.remove();
    };
  }, []);

  return <div className="stage3d" ref={host} aria-hidden="true" />;
}
