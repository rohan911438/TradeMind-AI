// Landing page: live hero card, ticker, stats, scroll reveals.
(() => {
  const $ = (s) => document.querySelector(s);
  const inr = (v) => Number(v).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  // reveal on scroll
  const io = new IntersectionObserver((entries) => entries.forEach((e) => e.isIntersecting && e.target.classList.add("in")), { threshold: 0.12 });
  document.querySelectorAll(".reveal").forEach((el) => io.observe(el));

  // sparkline
  const canvas = $("#h-spark");
  const ctx = canvas.getContext("2d");
  let series = [];
  function drawSpark() {
    const dpr = window.devicePixelRatio || 1;
    const w = canvas.clientWidth, h = 170;
    canvas.width = w * dpr; canvas.height = h * dpr; ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);
    if (series.length < 2) return;
    const min = Math.min(...series), max = Math.max(...series), pad = (max - min) * 0.1 || 1;
    const x = (i) => (i / (series.length - 1)) * w;
    const y = (v) => h - ((v - (min - pad)) / (max - min + 2 * pad)) * h;
    const up = series[series.length - 1] >= series[0];
    const col = up ? "92,255,176" : "255,92,122";
    const grad = ctx.createLinearGradient(0, 0, 0, h);
    grad.addColorStop(0, `rgba(${col},.28)`); grad.addColorStop(1, `rgba(${col},0)`);
    ctx.beginPath(); series.forEach((v, i) => (i ? ctx.lineTo(x(i), y(v)) : ctx.moveTo(x(i), y(v))));
    ctx.lineTo(w, h); ctx.lineTo(0, h); ctx.closePath(); ctx.fillStyle = grad; ctx.fill();
    ctx.beginPath(); series.forEach((v, i) => (i ? ctx.lineTo(x(i), y(v)) : ctx.moveTo(x(i), y(v))));
    ctx.strokeStyle = `rgb(${col})`; ctx.lineWidth = 2; ctx.stroke();
    const lx = x(series.length - 1), ly = y(series[series.length - 1]);
    ctx.beginPath(); ctx.arc(lx - 3, ly, 4, 0, Math.PI * 2); ctx.fillStyle = `rgb(${col})`; ctx.fill();
  }
  window.addEventListener("resize", drawSpark);

  async function loadCandles() {
    try {
      const c = await (await fetch("/api/market/RELIANCE/candles?limit=120")).json();
      series = c.map((b) => b.close); drawSpark();
    } catch (_) {}
  }

  async function loadSignal() {
    try {
      const s = await (await fetch("/api/predict/RELIANCE")).json();
      const colors = { BUY: "var(--up)", SELL: "var(--down)", HOLD: "var(--amber)", NO_TRADE: "var(--muted)" };
      const box = $("#h-signal");
      box.querySelector(".font-display").textContent = s.signal.replace("_", " ");
      box.querySelector(".font-display").style.color = colors[s.signal];
      box.style.borderColor = colors[s.signal];
      $("#h-conf").textContent = Math.round(s.confidence * 100) + "%";
      $("#h-press").textContent = s.market_pressure;
      $("#h-press").className = "text-lg mt-1 " + (s.market_pressure === "Positive" ? "up" : s.market_pressure === "Negative" ? "down" : "");
      $("#h-expl").textContent = s.explanation;
    } catch (_) {}
  }

  async function loadMonitor() {
    try {
      const m = await (await fetch("/api/monitor/metrics")).json();
      $("#s-eps").textContent = Math.round(m.events_per_sec).toLocaleString("en-IN");
      const p = m.processing_latency_us || {};
      $("#s-p50").textContent = p.p50 != null ? p.p50 + " µs" : "—";
      $("#h-lat").textContent = p.p99 != null ? p.p99 + " µs" : "—";
    } catch (_) {}
  }

  // live ticker via WebSocket
  let lastPrice = null;
  function connect() {
    const ws = new WebSocket((location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws/market");
    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data);
      const syms = Object.values(msg.symbols);
      const items = syms.map((s) => `<span class="flex items-center gap-3"><span class="text-white font-semibold">${s.symbol}</span><span>₹${inr(s.last)}</span><span class="${s.change_pct >= 0 ? "up" : "down"}">${s.change_pct >= 0 ? "▲" : "▼"} ${Math.abs(s.change_pct).toFixed(2)}%</span><span class="dim">imb ${s.imbalance >= 0 ? "+" : ""}${s.imbalance.toFixed(2)}</span></span>`).join("");
      $("#ticker").innerHTML = items + items;  // two copies give a seamless loop
      $("#ticker").style.animationDuration = Math.max(30, syms.length * 5) + "s";  // constant speed for any list size
      const r = msg.symbols.RELIANCE;
      if (r) {
        $("#h-price").textContent = "₹" + inr(r.last);
        $("#h-chg").textContent = (r.change_pct >= 0 ? "+" : "") + r.change_pct.toFixed(2) + "%";
        $("#h-chg").className = "num text-sm " + (r.change_pct >= 0 ? "up" : "down");
        if (series.length && r.candle) { series[series.length - 1] = r.last; if (lastPrice !== r.candle.time) { series.push(r.last); series = series.slice(-120); lastPrice = r.candle.time; } drawSpark(); }
      }
    };
    ws.onclose = () => setTimeout(connect, 2000);
  }

  loadCandles().then(connect);
  loadSignal(); loadMonitor();
  setInterval(loadSignal, 8000);
  setInterval(loadMonitor, 2000);
})();
