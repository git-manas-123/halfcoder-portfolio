(() => {
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const names = { rain: "Code rain", stars: "Constellation", aurora: "Aurora", racks: "Data centre" };
  const modes = reduce ? ["racks", "aurora"] : ["racks", "rain", "stars", "aurora"];
  let mode = null; try { mode = localStorage.getItem("bg"); } catch (e) {}
  if (!modes.includes(mode)) mode = modes[0];
  const cv = document.getElementById("bg2"), sc = document.getElementById("scene"), au = document.getElementById("aurora"), btn = document.getElementById("bgbtn");
  if (!cv || !btn) return;
  const x = cv.getContext("2d"), css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
  let W, H, cols, drops, pts, c1, c2, mx = -999, my = -999;
  const CH = "01{}[]<>/$#=+~;:ABCDEF", FS = 18;
  const colors = () => { c1 = css("--acc2"); c2 = css("--acc"); };
  function size() {
    W = cv.width = innerWidth; H = cv.height = innerHeight; cols = Math.ceil(W / FS);
    drops = Array.from({ length: cols }, () => Math.random() * H / FS);
    pts = Array.from({ length: Math.min(100, Math.floor(W * H / 15000)) }, () => ({ x: Math.random() * W, y: Math.random() * H, vx: (Math.random() - .5) * .5, vy: (Math.random() - .5) * .5 }));
  }
  function rain() {
    x.globalCompositeOperation = "destination-out"; x.fillStyle = "rgba(0,0,0,.09)"; x.fillRect(0, 0, W, H);
    x.globalCompositeOperation = "source-over"; x.font = FS + "px ui-monospace,Menlo,monospace";
    for (let i = 0; i < cols; i++) {
      const py = Math.floor(drops[i]); drops[i] += .28;
      if (Math.floor(drops[i]) === py) continue;
      const ch = CH[Math.floor(Math.random() * CH.length)];
      x.fillStyle = c1; x.fillText(ch, i * FS, py * FS);
      x.fillStyle = c2; x.fillText(ch, i * FS, (py + 1) * FS);
      if (drops[i] * FS > H && Math.random() > .975) drops[i] = 0;
    }
  }
  function stars() {
    x.clearRect(0, 0, W, H); x.fillStyle = c1; x.strokeStyle = c1;
    for (const p of pts) {
      p.x += p.vx; p.y += p.vy;
      if (p.x < 0 || p.x > W) p.vx *= -1; if (p.y < 0 || p.y > H) p.vy *= -1;
      x.globalAlpha = 1; x.beginPath(); x.arc(p.x, p.y, 2, 0, 6.283); x.fill();
    }
    for (let i = 0; i < pts.length; i++) {
      for (let j = i + 1; j < pts.length; j++) {
        const d = Math.hypot(pts[i].x - pts[j].x, pts[i].y - pts[j].y);
        if (d < 130) { x.globalAlpha = (1 - d / 130) * .7; x.beginPath(); x.moveTo(pts[i].x, pts[i].y); x.lineTo(pts[j].x, pts[j].y); x.stroke(); }
      }
      const m = Math.hypot(pts[i].x - mx, pts[i].y - my);
      if (m < 180) { x.strokeStyle = c2; x.globalAlpha = (1 - m / 180); x.beginPath(); x.moveTo(pts[i].x, pts[i].y); x.lineTo(mx, my); x.stroke(); x.strokeStyle = c1; }
    }
    x.globalAlpha = 1;
  }
  function apply(say) {
    sc.hidden = mode !== "racks"; au.hidden = mode !== "aurora"; cv.hidden = !(mode === "rain" || mode === "stars");
    x.clearRect(0, 0, W, H); btn.title = "Background: " + names[mode];
    btn.setAttribute("aria-label", "Change background. Now: " + names[mode]);
    if (mode === "racks") dispatchEvent(new Event("themechange"));
    if (say && window.__toast) window.__toast("Background: " + names[mode]);
  }
  btn.onclick = () => { mode = modes[(modes.indexOf(mode) + 1) % modes.length]; try { localStorage.setItem("bg", mode); } catch (e) {} apply(true); };
  addEventListener("pointermove", e => { mx = e.clientX; my = e.clientY; });
  addEventListener("resize", size); addEventListener("themechange", colors);
  colors(); size(); apply(false);
  if (!reduce) (function loop() { if (mode === "rain") rain(); else if (mode === "stars") stars(); requestAnimationFrame(loop); })();
})();
