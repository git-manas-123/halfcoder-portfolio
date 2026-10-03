(() => {
  const $ = i => document.getElementById(i), reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  let tt;
  const toast = m => {
    let t = $("toast");
    if (!t) { t = document.createElement("div"); t.id = "toast"; t.setAttribute("role", "status"); document.body.appendChild(t); }
    t.textContent = m; t.classList.add("on"); clearTimeout(tt); tt = setTimeout(() => t.classList.remove("on"), 3400);
  };

  window.__toast = toast;
  // Chaos Monkey: knocks the page's pods over, then Kubernetes heals them.
  function chaos() {
    if (document.body.classList.contains("chaos")) return;
    if (reduce) { toast("Chaos Monkey is on break because reduced motion is on."); return; }
    const els = [...document.querySelectorAll("main .card,main .tile,main .proj,main .tl>div,main .hcopy,main .float,main .row,main .ph,main .term")].filter(e => e.offsetParent);
    document.body.classList.add("chaos");
    els.forEach(e => {
      e.style.setProperty("--r", (Math.random() * 70 - 35) + "deg");
      e.style.setProperty("--dx", (Math.random() * 200 - 100) + "px");
      e.style.setProperty("--d", (Math.random() * .6) + "s");
      e.classList.add("fall");
    });
    toast("Chaos Monkey killed " + els.length + " pods!");
    setTimeout(() => {
      els.forEach(e => { e.classList.remove("fall"); e.classList.add("heal"); });
      toast("kubectl rollout restart: all pods healthy. Self-healing works.");
      setTimeout(() => { els.forEach(e => e.classList.remove("heal")); document.body.classList.remove("chaos"); }, 1000);
    }, 2800);
  }
  const m = $("monkey"); if (m) m.onclick = chaos;

  const up = $("up"), t0 = Date.now();
  if (up) setInterval(() => {
    const s = Math.floor((Date.now() - t0) / 1000), p = n => String(n).padStart(2, "0");
    up.textContent = "Page uptime " + p(Math.floor(s / 60)) + ":" + p(s % 60);
  }, 1000);

  // Terminal
  const out = $("tout"), inp = $("tin");
  if (!out || !inp) return;
  const say = (lines) => { lines.forEach(l => { const d = document.createElement("div"); d.textContent = l; out.appendChild(d); }); out.scrollTop = out.scrollHeight; };
  const pages = () => [...document.querySelectorAll("header nav a[href]")];
  const C = {
    help: () => ["help, whoami, ls, cat skills, uptime, docker ps, kubectl get pods,", "ping, coffee, date, echo <text>, cd <page>, sudo, clear", "Danger zone: rm -rf /"],
    whoami: () => ["manas: system administrator, RHCSA, keeper of uptime"],
    ls: () => [pages().map(a => a.textContent.trim().toLowerCase()).join("   ")],
    "cat skills": () => ["linux  aws  docker  kubernetes  terraform  ansible  nginx  prometheus  grafana"],
    uptime: () => ["up 99.9%, 0 users complaining, load average: coffee"],
    "docker ps": () => ["NAMES       IMAGE           STATUS", "portfolio   flask:latest    Up 99.9%", "nginx       nginx:stable    Up", "coffee      dark-roast      Up (refilling)"],
    "kubectl get pods": () => ["NAME           READY  STATUS", "web-7d9f       1/1    Running", "api-4kxq       1/1    Running", "chaos-monkey   0/1    CrashLoopBackOff (it's fine)"],
    ping: () => ["PING localhost: 64 bytes, time=0.42 ms", "0% packet loss. Everything is fine."],
    coffee: () => ["Brewing... [##########] 100%", "Coffee deployed. Productivity +25%."],
    date: () => [new Date().toString()]
  };
  C["cat skills.txt"] = C["cat skills"];
  const hist = []; let hi = 0;
  say(["Welcome to Manas's terminal. Type help."]);
  inp.addEventListener("keydown", e => {
    if (e.key === "ArrowUp" && hist.length) { hi = Math.max(0, hi - 1); inp.value = hist[hi]; e.preventDefault(); return; }
    if (e.key === "ArrowDown") { hi = Math.min(hist.length, hi + 1); inp.value = hist[hi] || ""; return; }
    if (e.key !== "Enter") return;
    const v = inp.value.trim().replace(/\s+/g, " "); inp.value = ""; if (!v) return;
    hist.push(v); hi = hist.length; say(["$ " + v]);
    if (v === "clear") { out.textContent = ""; return; }
    if (/^(sudo )?rm -rf \/?\*?$/.test(v)) { say(["Nice try. Releasing the Chaos Monkey instead..."]); chaos(); return; }
    if (v.startsWith("sudo")) { say(["manas is not in the sudoers file. This incident will be reported."]); return; }
    if (v.startsWith("echo ")) { say([v.slice(5)]); return; }
    if (v.startsWith("cd ")) {
      const w = v.slice(3).toLowerCase(), a = pages().find(x => x.textContent.trim().toLowerCase() === w);
      if (a) { say(["Opening " + w + "..."]); location.href = a.href; } else say(["cd: " + w + ": no such page. Try ls."]);
      return;
    }
    say(C[v] ? C[v]() : ["bash: " + v.split(" ")[0] + ": command not found. Try help."]);
  });
})();
