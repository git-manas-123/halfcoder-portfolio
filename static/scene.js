(() => {
  // Background: a 3D data-centre aisle. Racks with blinking LEDs stream past; scroll to speed up.
  const c = document.getElementById("scene");
  if (!c || !window.THREE) return;
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const R = new THREE.WebGLRenderer({ canvas: c, alpha: true, antialias: true });
  R.setPixelRatio(Math.min(devicePixelRatio, 2));
  const S = new THREE.Scene(), cam = new THREE.PerspectiveCamera(60, 1, .1, 100), W = new THREE.Group();
  cam.position.set(0, .4, 6); S.add(W); S.fog = new THREE.Fog(0x000000, 6, 42);
  const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();

  const edge = new THREE.EdgesGeometry(new THREE.BoxGeometry(1.7, 3.4, 1.3));
  const lineMat = new THREE.LineBasicMaterial({ transparent: true, opacity: .4 });
  const ledMat = new THREE.PointsMaterial({ size: .11, vertexColors: true });
  const pal = ["#4cd08f", "#ffb347", "#ff6b6b", "#4cd08f"].map(h => new THREE.Color(h)), off = new THREE.Color();
  const N = 14, racks = [];
  for (let side = -1; side <= 1; side += 2) for (let i = -1; i < 12; i++) {
    const g = new THREE.Group(); g.position.set(side * 4.4, -.4, -i * 5);
    g.add(new THREE.LineSegments(edge, lineMat));
    const pos = new Float32Array(N * 3), col = new Float32Array(N * 3), geo = new THREE.BufferGeometry();
    for (let k = 0; k < N; k++) pos.set([-side * .88, -1.5 + Math.floor(k / 2) * .45, k % 2 ? .3 : -.3], k * 3);
    geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    geo.setAttribute("color", new THREE.BufferAttribute(col, 3));
    g.add(new THREE.Points(geo, ledMat)); W.add(g); racks.push({ col, geo });
  }
  const led = (r, k, on) => {
    const c = on ? pal[Math.floor(Math.random() * pal.length)] : off;
    r.col.set([c.r, c.g, c.b], k * 3); r.geo.attributes.color.needsUpdate = true;
  };

  const fp = [];
  for (let x = -12; x <= 12; x += 4) fp.push(new THREE.Vector3(x, -2.1, 6), new THREE.Vector3(x, -2.1, -62));
  for (let z = 6; z >= -62; z -= 5) fp.push(new THREE.Vector3(-12, -2.1, z), new THREE.Vector3(12, -2.1, z));
  const floorMat = new THREE.LineBasicMaterial({ transparent: true, opacity: .2 });
  W.add(new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(fp), floorMat));

  const theme = () => {
    S.fog.color.set(css("--bg")); lineMat.color.set(css("--acc2")); floorMat.color.set(css("--acc")); off.set(css("--line"));
    racks.forEach(r => { for (let k = 0; k < N; k++) led(r, k, Math.random() < .6); });
  };
  theme(); addEventListener("themechange", () => { theme(); if (reduce) R.render(S, cam); });

  let mx = 0, my = 0, boost = 0, last = scrollY;
  addEventListener("pointermove", e => { mx = e.clientX / innerWidth - .5; my = e.clientY / innerHeight - .5; });
  addEventListener("scroll", () => { boost = Math.min(boost + Math.abs(scrollY - last) * .004, .6); last = scrollY; }, { passive: true });
  const size = () => { R.setSize(innerWidth, innerHeight, false); cam.aspect = innerWidth / innerHeight; cam.updateProjectionMatrix(); };
  addEventListener("resize", () => { size(); if (reduce) R.render(S, cam); }); size();

  (function frame() {
    if (c.hidden) { if (!reduce) requestAnimationFrame(frame); return; }
    if (!reduce) {
      W.position.z += .035 + boost; boost *= .94; if (W.position.z >= 5) W.position.z -= 5;
      cam.position.x += (mx * 2 - cam.position.x) * .04;
      cam.position.y += (.4 - my * 1.2 - cam.position.y) * .04;
      cam.rotation.y = -cam.position.x * .05;
      racks.forEach(r => { if (Math.random() < .04) led(r, Math.floor(Math.random() * N), Math.random() < .55); });
      requestAnimationFrame(frame);
    }
    R.render(S, cam);
  })();
})();
