// TradeMind AI - trading terminal (vanilla JS, no build step)
(() => {
  "use strict";
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];
  const inr = (v, d = 2) => (v == null || isNaN(v)) ? "—" : "₹" + Number(v).toLocaleString("en-IN", { minimumFractionDigits: d, maximumFractionDigits: d });
  const num = (v, d = 2) => (v == null || isNaN(v)) ? "—" : Number(v).toLocaleString("en-IN", { minimumFractionDigits: d, maximumFractionDigits: d });
  const pct = (v, d = 1) => (v == null || isNaN(v)) ? "—" : (v * 100).toFixed(d) + "%";
  const signed = (v, d = 2) => (v >= 0 ? "+" : "") + num(v, d);
  const cls = (v) => (v > 0 ? "up" : v < 0 ? "down" : "");
  const SIG_COLOR = { BUY: "var(--up)", SELL: "var(--down)", HOLD: "var(--amber)", NO_TRADE: "var(--muted)" };
  const sigText = (s) => (s || "").replace("_", " ");

  const S = { symbol: "RELIANCE", page: "dashboard", market: {}, user: null, side: "BUY", lastVerdict: null, signals: {}, modelInfo: null };

  async function api(path, opts = {}) {
    const r = await fetch(path, { credentials: "same-origin", headers: { "Content-Type": "application/json" }, ...opts });
    if (r.status === 401) { showAuth(); throw new Error("Not signed in"); }
    if (!r.ok) { let m = r.statusText; try { m = (await r.json()).detail || m; } catch (_) {} throw new Error(m); }
    return r.json();
  }
  const post = (path, body) => api(path, { method: "POST", body: JSON.stringify(body || {}) });

  function toast(msg, kind = "info") {
    const c = { info: "border-white/10", ok: "border-[rgba(34,213,139,.5)]", err: "border-[rgba(255,92,122,.5)]" }[kind];
    const el = document.createElement("div");
    el.className = `toast glass rounded-xl px-4 py-3 text-sm max-w-sm border ${c}`;
    el.textContent = msg;
    $("#toasts").appendChild(el);
    setTimeout(() => el.remove(), 4000);
  }

  // ======================= AUTH =======================
  let authCfg = null;
  async function initAuth() {
    authCfg = await (await fetch("/api/auth/config")).json();
    try {
      const r = await fetch("/api/auth/me", { credentials: "same-origin" });
      if (r.ok) return onSignedIn(await r.json());
    } catch (_) {}
    showAuth();
  }

  function showAuth() {
    $("#auth").classList.remove("hidden");
    if (authCfg && authCfg.google_client_id) {
      const tryRender = () => {
        if (!window.google || !google.accounts) return setTimeout(tryRender, 200);
        google.accounts.id.initialize({ client_id: authCfg.google_client_id, callback: onGoogleCredential, auto_select: false });
        google.accounts.id.renderButton($("#g-btn-wrap"), { theme: "filled_black", size: "large", shape: "pill", text: "continue_with", width: 320 });
      };
      tryRender();
    } else {
      $("#g-missing").classList.remove("hidden");
    }
  }

  async function onGoogleCredential(resp) {
    try { onSignedIn(await post("/api/auth/google", { credential: resp.credential })); }
    catch (e) { toast("Google sign-in failed: " + e.message, "err"); }
  }

  $("#guest-btn").onclick = async () => {
    try { onSignedIn(await post("/api/auth/guest")); } catch (e) { toast(e.message, "err"); }
  };

  function onSignedIn(user) {
    S.user = user;
    $("#auth").classList.add("hidden");
    $("#user-name").textContent = user.name || "Trader";
    $("#user-email").textContent = user.email || (user.provider === "guest" ? "Guest session" : "");
    if (user.picture) { $("#user-pic").src = user.picture; $("#user-pic").classList.remove("hidden"); $("#user-initial").classList.add("hidden"); }
    else $("#user-initial").textContent = (user.name || "G")[0].toUpperCase();
    refreshAccount();
  }

  $("#user-btn").onclick = () => $("#user-menu").classList.toggle("hidden");
  $("#logout-btn").onclick = async () => {
    await post("/api/auth/logout");
    if (window.google && google.accounts) google.accounts.id.disableAutoSelect();
    location.reload();
  };

  // ======================= NAV =======================
  const TITLES = { dashboard: "Market", signals: "AI Signals", trade: "Paper Trade", portfolio: "Portfolio & Risk", monitor: "StreamX Monitor", about: "Architecture" };
  function go(page) {
    S.page = page;
    $$(".page").forEach((p) => p.classList.toggle("active", p.id === "page-" + page));
    $$(".nav-btn").forEach((b) => b.classList.toggle("active", b.dataset.page === page));
    $("#mobile-nav").value = page;
    $("#page-title").textContent = TITLES[page];
    if (page === "signals") { loadSignal(S.symbol, true); loadModelInfo(); }
    if (page === "trade") { syncTicket(); refreshAccount(); }
    if (page === "portfolio") refreshRisk();
    if (page === "dashboard" && chart) setTimeout(() => chart.timeScale().scrollToRealTime(), 50);
    history.replaceState(null, "", "#" + page);
    window.scrollTo(0, 0);
  }
  $$(".nav-btn").forEach((b) => (b.onclick = () => go(b.dataset.page)));
  $("#mobile-nav").onchange = (e) => go(e.target.value);
  document.addEventListener("click", (e) => {
    const g = e.target.closest("[data-goto]"); if (g) go(g.dataset.goto);
    if (!e.target.closest("#user-btn") && !e.target.closest("#user-menu")) $("#user-menu").classList.add("hidden");
  });

  setInterval(() => { $("#clock").textContent = new Date().toLocaleTimeString("en-IN", { hour12: false }) + " IST"; }, 1000);

  // ======================= MARKET =======================
  let chart, candleSeries, volSeries;
  function initChart() {
    chart = LightweightCharts.createChart($("#chart"), {
      autoSize: true,
      layout: { background: { type: "solid", color: "transparent" }, textColor: "#8b95a7", fontFamily: "JetBrains Mono, monospace", fontSize: 11 },
      grid: { vertLines: { color: "rgba(255,255,255,.04)" }, horzLines: { color: "rgba(255,255,255,.04)" } },
      rightPriceScale: { borderColor: "rgba(255,255,255,.08)" },
      timeScale: { borderColor: "rgba(255,255,255,.08)", timeVisible: true, secondsVisible: false, rightOffset: 6 },
      crosshair: { mode: 0 },
    });
    candleSeries = chart.addCandlestickSeries({ upColor: "#22d58b", downColor: "#ff5c7a", borderVisible: false, wickUpColor: "#22d58b", wickDownColor: "#ff5c7a" });
    volSeries = chart.addHistogramSeries({ priceFormat: { type: "volume" }, priceScaleId: "vol", color: "rgba(139,123,255,.35)" });
    chart.priceScale("vol").applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });
  }

  let lastCandleTime = 0;
  async function loadCandles(sym) {
    const c = await api(`/api/market/${enc(sym)}/candles?limit=400`);
    candleSeries.setData(c.map((b) => ({ time: b.time, open: b.open, high: b.high, low: b.low, close: b.close })));
    volSeries.setData(c.map((b) => ({ time: b.time, value: b.volume, color: b.close >= b.open ? "rgba(34,213,139,.3)" : "rgba(255,92,122,.3)" })));
    lastCandleTime = c.length ? c[c.length - 1].time : 0;
    chart.timeScale().scrollToRealTime();
  }

  function selectSymbol(sym) {
    if (!sym || !S.market[sym]) return;  // ignore empty / unknown selections
    S.symbol = sym;
    $("#chart-sym-label").textContent = sym + " · NSE";
    renderWatchlist();
    loadCandles(sym);
    refreshMiniSignal();
    if (S.page === "signals") loadSignal(sym, true);
    $("#t-sym").value = sym; syncTicket();
    renderSigSyms();
  }

  const prevPrice = {};
  const enc = encodeURIComponent;  // tickers such as M&M and BAJAJ-AUTO
  function renderWatchlist() {
    const wl = $("#watchlist");
    const syms = Object.values(S.market);
    if (!wl.children.length || wl.children.length !== syms.length) {
      wl.innerHTML = syms.map((s) => `
        <button class="sym-card card card-hover px-3 py-2.5 text-left" data-sym="${s.symbol}">
          <div class="flex items-center justify-between gap-2"><span class="font-display font-semibold text-sm truncate">${s.symbol}</span><span class="num text-[11px]" data-f="chg"></span></div>
          <div class="mt-1"><span class="num text-base font-semibold" data-f="last"></span></div>
          <div class="bar-track mt-2 !h-1"><div data-f="imb" class="h-full rounded-full transition-all duration-300"></div></div>
        </button>`).join("");
      $$(".sym-card", wl).forEach((b) => (b.onclick = () => selectSymbol(b.dataset.sym)));
      $("#wl-count").textContent = syms.length;
      filterWatchlist();
    }
    const q = $("#wl-search").value.trim().toUpperCase();
    syms.forEach((s) => {
      const card = $(`.sym-card[data-sym="${s.symbol}"]`, wl);
      card.classList.toggle("active", s.symbol === S.symbol);
      if (q && !s.symbol.includes(q)) return;  // hidden by the search filter: skip the DOM work
      const last = $('[data-f="last"]', card);
      if (prevPrice[s.symbol] != null && s.last !== prevPrice[s.symbol]) {
        last.classList.remove("flash-up", "flash-down"); void last.offsetWidth;
        last.classList.add(s.last > prevPrice[s.symbol] ? "flash-up" : "flash-down");
      }
      prevPrice[s.symbol] = s.last;
      last.textContent = inr(s.last);
      const chg = $('[data-f="chg"]', card);
      chg.textContent = (s.change_pct >= 0 ? "▲ " : "▼ ") + Math.abs(s.change_pct).toFixed(2) + "%";
      chg.className = "num text-[11px] " + cls(s.change_pct);
      const imb = $('[data-f="imb"]', card);
      imb.style.width = Math.abs(s.imbalance) * 50 + "%";
      imb.style.marginLeft = s.imbalance >= 0 ? "50%" : 50 - Math.abs(s.imbalance) * 50 + "%";
      imb.style.background = s.imbalance >= 0 ? "var(--up)" : "var(--down)";
    });
  }

  function filterWatchlist() {
    const q = $("#wl-search").value.trim().toUpperCase();
    $$(".sym-card", $("#watchlist")).forEach((c) => c.classList.toggle("hidden", !!q && !c.dataset.sym.includes(q)));
  }
  $("#wl-search").oninput = filterWatchlist;
  $("#wl-search").onkeydown = (e) => {
    if (e.key !== "Enter") return;
    const first = $$(".sym-card:not(.hidden)", $("#watchlist"))[0];
    if (first) selectSymbol(first.dataset.sym);
  };

  function renderBook(s) {
    const maxQ = Math.max(...s.bids.map((b) => b[1]), ...s.asks.map((a) => a[1]), 1);
    const row = (p, q, side) => `
      <div class="relative flex justify-between px-2 py-1 rounded">
        <div class="absolute inset-y-0 ${side === "bid" ? "right-0" : "right-0"} rounded" style="width:${(q / maxQ) * 100}%;background:${side === "bid" ? "rgba(34,213,139,.12)" : "rgba(255,92,122,.12)"}"></div>
        <span class="relative ${side === "bid" ? "up" : "down"}">${num(p)}</span><span class="relative muted">${q.toLocaleString("en-IN")}</span>
      </div>`;
    $("#orderbook").innerHTML =
      [...s.asks].reverse().map((a) => row(a[0], a[1], "ask")).join("") +
      `<div class="flex justify-between px-2 py-2 my-1 border-y border-white/5 text-xs"><span class="dim">Spread</span><span>${num(s.spread)}</span></div>` +
      s.bids.map((b) => row(b[0], b[1], "bid")).join("");
    $("#book-imb").textContent = "imbalance " + signed(s.imbalance, 2);
    $("#book-imb").className = "num text-xs " + cls(s.imbalance);
    $("#imb-marker").style.left = `calc(${(s.imbalance + 1) * 50}% - 3px)`;
  }

  function onMarket(msg) {
    S.market = msg.symbols;
    renderWatchlist();
    const s = S.market[S.symbol];
    if (!s) return;
    $("#chart-price").textContent = inr(s.last);
    $("#chart-chg").textContent = (s.change_pct >= 0 ? "+" : "") + s.change_pct.toFixed(2) + "%";
    $("#chart-chg").className = "num text-sm " + cls(s.change_pct);
    $("#chart-bid").textContent = num(s.bid); $("#chart-ask").textContent = num(s.ask); $("#chart-spread").textContent = num(s.spread);
    renderBook(s);
    if (s.candle && candleSeries && s.candle.time >= lastCandleTime) {
      candleSeries.update({ time: s.candle.time, open: s.candle.open, high: s.candle.high, low: s.candle.low, close: s.candle.close });
      volSeries.update({ time: s.candle.time, value: s.candle.volume, color: s.candle.close >= s.candle.open ? "rgba(34,213,139,.3)" : "rgba(255,92,122,.3)" });
      lastCandleTime = s.candle.time;
    }
    if (S.page === "trade") updateTicketPrice();
  }

  function connectWS(path, onMsg) {
    const open = () => {
      const ws = new WebSocket((location.protocol === "https:" ? "wss://" : "ws://") + location.host + path);
      ws.onopen = () => { $("#conn-dot").style.background = "var(--mint)"; };
      ws.onmessage = (e) => onMsg(JSON.parse(e.data));
      ws.onclose = () => { $("#conn-dot").style.background = "var(--down)"; setTimeout(open, 1500); };
    };
    open();
  }

  // ======================= SIGNALS =======================
  async function getSignal(sym) { const s = await api("/api/predict/" + enc(sym)); S.signals[sym] = s; return s; }

  async function refreshMiniSignal() {
    try {
      const s = await getSignal(S.symbol);
      $("#mini-signal").textContent = sigText(s.signal);
      $("#mini-signal").style.color = SIG_COLOR[s.signal];
      $("#mini-conf").textContent = pct(s.confidence, 0);
      $("#mini-expl").textContent = s.explanation;
      $("#chart-vol").textContent = pct(s.annualised_volatility, 1);
    } catch (_) {}
  }

  function renderSigSyms() {
    const sel = $("#sig-syms");
    if (sel.options.length !== Object.keys(S.market).length)
      sel.innerHTML = Object.keys(S.market).map((s) => `<option>${s}</option>`).join("");
    sel.value = S.symbol;
  }
  $("#sig-syms").onchange = (e) => selectSymbol(e.target.value);

  async function loadSignal(sym, withSentiment) {
    try {
      const [s, sent] = await Promise.all([getSignal(sym), withSentiment ? api("/api/sentiment/" + enc(sym)) : Promise.resolve(null)]);
      renderSigSyms();
      $("#sig-scope").textContent = s.in_training_set ? "Model trained and tested on this stock"
        : "Model applied out of sample: this stock was not in the training set";
      $("#sig-sym").textContent = sym + " · NSE · " + s.model_version;
      $("#sig-signal").textContent = sigText(s.signal);
      $("#sig-signal").style.color = SIG_COLOR[s.signal];
      $("#sig-card").style.borderColor = SIG_COLOR[s.signal];
      $("#sig-horizon").textContent = `Horizon: ${s.horizon} · model view: ${s.model_view} · threshold ${pct(s.threshold, 0)}`;
      $("#sig-conf").textContent = pct(s.confidence, 0);
      $("#sig-press").textContent = s.market_pressure; $("#sig-press").className = "text-lg mt-1 " + (s.market_pressure === "Positive" ? "up" : s.market_pressure === "Negative" ? "down" : "");
      $("#sig-sent").textContent = s.sentiment.label; $("#sig-sent").className = "text-lg mt-1 " + (s.sentiment.label === "Positive" ? "up" : s.sentiment.label === "Negative" ? "down" : "");
      const v = s.annualised_volatility;
      $("#sig-risk").textContent = v < 0.2 ? "LOW" : v < 0.4 ? "MODERATE" : "HIGH";
      const p = s.probabilities || {};
      $("#sig-probs").innerHTML = ["SELL", "HOLD", "BUY"].map((k) => `<div style="width:${(p[k] || 0) * 100}%;background:${SIG_COLOR[k]};opacity:${k === s.model_view ? 1 : .45}"></div>`).join("");
      $("#sig-probs-txt").innerHTML = ["SELL", "HOLD", "BUY"].map((k) => `<span style="color:${SIG_COLOR[k]}">${pct(p[k] || 0, 0)}</span>`).join("");
      $("#sig-expl").textContent = s.explanation;
      $("#sig-disclaimer").textContent = s.disclaimer;
      $("#sig-updated").textContent = "updated " + new Date().toLocaleTimeString("en-IN", { hour12: false });
      const maxC = Math.max(...s.top_factors.map((f) => Math.abs(f.contribution)), 0.0001);
      $("#sig-factors").innerHTML = s.top_factors.map((f) => `
        <div>
          <div class="flex justify-between text-sm"><span class="mono">${f.feature}</span><span class="num ${f.contribution > 0 ? "up" : "down"}">${signed(f.contribution, 3)}</span></div>
          <div class="bar-track mt-1.5"><div class="h-full rounded-full" style="width:${(Math.abs(f.contribution) / maxC) * 100}%;background:${f.contribution > 0 ? "var(--up)" : "var(--down)"}"></div></div>
          <div class="text-xs muted mt-1.5">${f.text}</div>
        </div>`).join("") || '<p class="dim text-sm">No factors (model not trained).</p>';
      if (sent && !sent.headlines.length) {
        $("#sig-heads").innerHTML = `<p class="dim">No sample headlines for ${sym}; sentiment is treated as Neutral. Live news is future work.</p>`;
      } else if (sent) {
        $("#sig-heads").innerHTML = sent.headlines.map((h) => `
          <div class="flex items-start justify-between gap-3 py-2 border-b border-white/5">
            <span>${h.headline}</span><span class="num text-xs shrink-0 ${cls(h.score)}">${signed(h.score, 2)}</span>
          </div>`).join("") + `<div class="flex justify-between pt-2 font-semibold"><span>Aggregate</span><span class="num ${cls(sent.score)}">${signed(sent.score, 2)} · ${sent.label}</span></div>`;
      }
    } catch (e) { toast("Signal error: " + e.message, "err"); }
  }

  async function loadModelInfo() {
    if (S.modelInfo) return;
    try {
      const m = await api("/api/predict/model-info");
      S.modelInfo = m;
      const cm = m.confusion_matrix;
      const labels = ["SELL", "HOLD", "BUY"];
      const maxCm = Math.max(...cm.flat(), 1);
      const srcs = Object.entries(m.data_sources).map(([k, v]) => `${k}: ${v.bars} bars`).join(" · ");
      const firstSrc = Object.values(m.data_sources)[0]?.source || "";
      $("#model-info").innerHTML = `
        <div class="grid grid-cols-2 gap-3">
          <div class="card p-3"><div class="label !text-[10px]">Macro F1 (balanced)</div><div class="num text-2xl mt-1">${num(m.macro_f1, 3)}</div><div class="text-[10px] dim">baseline "always ${m.baseline_majority_class}": ${num(m.baseline_majority_macro_f1, 3)}</div></div>
          <div class="card p-3"><div class="label !text-[10px]">Accuracy</div><div class="num text-2xl mt-1">${pct(m.accuracy)}</div><div class="text-[10px] dim">always ${m.baseline_majority_class}: ${pct(m.baseline_majority_accuracy)} · random ${pct(m.baseline_random_accuracy)}</div></div>
          <div class="card p-3"><div class="label !text-[10px]">BUY/SELL hit-rate</div><div class="num text-2xl mt-1">${m.directional_hit_rate != null ? pct(m.directional_hit_rate) : "—"}</div><div class="text-[10px] dim">chance level ${m.directional_chance_rate != null ? pct(m.directional_chance_rate) : "—"}</div></div>
          <div class="card p-3"><div class="label !text-[10px]">Confident precision</div><div class="num text-2xl mt-1">${m.confident_signal_precision != null ? pct(m.confident_signal_precision) : "—"}</div><div class="text-[10px] dim">on ${pct(m.confident_signal_coverage)} of bars</div></div>
        </div>
        <div class="label mt-5">Confusion matrix (rows = actual)</div>
        <div class="grid grid-cols-4 gap-1 mt-2 text-xs num text-center">
          <div></div>${labels.map((l) => `<div class="dim py-1">${l}</div>`).join("")}
          ${cm.map((row, i) => `<div class="dim py-2 text-left">${labels[i]}</div>` + row.map((v, j) => `<div class="rounded py-2" style="background:rgba(${i === j ? "92,255,176" : "139,123,255"},${0.08 + (v / maxCm) * 0.5})">${v}</div>`).join("")).join("")}
        </div>
        <div class="label mt-5">Global feature importance</div>
        <div class="mt-2 space-y-1.5">${Object.entries(m.feature_importance).map(([k, v]) => `
          <div class="flex items-center gap-2 text-xs"><span class="mono w-24 shrink-0 muted">${k}</span><div class="bar-track flex-1"><div class="h-full rounded-full bg-[var(--violet)]" style="width:${(v / Object.values(m.feature_importance)[0]) * 100}%"></div></div></div>`).join("")}
        </div>
        <p class="text-[11px] dim mt-4">Accuracy alone is misleading here: ${pct(m.baseline_majority_accuracy, 0)} of bars are HOLD, so the model is trained with balanced class weights and judged on macro-F1 and BUY/SELL hit-rate vs chance. Data: ${firstSrc}. ${srcs}. Labels: return over next ${m.horizon_bars} bars beyond ±${(m.label_threshold * 100).toFixed(2)}%. Time-ordered purged split; trained ${m.trained_at}.</p>`;
    } catch (e) { $("#model-info").innerHTML = '<p class="dim">Model not trained yet.</p>'; }
  }

  $("#sig-refresh").onclick = () => loadSignal(S.symbol, true);
  $("#sig-trade").onclick = () => {
    const s = S.signals[S.symbol];
    setSide(s && s.signal === "SELL" ? "SELL" : "BUY");
    go("trade");
  };
  $$("[data-quick]").forEach((b) => (b.onclick = () => { setSide(b.dataset.quick); go("trade"); }));

  // ======================= TRADE =======================
  function setSide(side) {
    S.side = side;
    $$("[data-side]").forEach((b) => b.classList.toggle("active", b.dataset.side === side));
    $("#t-confirm").className = "btn w-full " + (side === "BUY" ? "btn-buy" : "btn-sell");
    $("#t-confirm").textContent = `2 · Place paper ${side.toLowerCase()} order`;
    invalidateVerdict();
  }
  $$("[data-side]").forEach((b) => (b.onclick = () => setSide(b.dataset.side)));

  function invalidateVerdict() { S.lastVerdict = null; $("#t-confirm").disabled = true; }

  function syncTicket() {
    const sel = $("#t-sym");
    if (!sel.options.length) sel.innerHTML = Object.keys(S.market).map((s) => `<option>${s}</option>`).join("");
    sel.value = S.symbol;
    updateTicketPrice();
    getSignal(sel.value).then((s) => {
      $("#t-signal").textContent = sigText(s.signal); $("#t-signal").style.color = SIG_COLOR[s.signal];
      $("#t-conf").textContent = pct(s.confidence, 0);
    }).catch(() => {});
  }
  function updateTicketPrice() {
    const s = S.market[$("#t-sym").value]; if (!s) return;
    const px = S.side === "BUY" ? s.ask : s.bid;
    $("#t-price").textContent = inr(px);
    const q = parseInt($("#t-qty").value || "0", 10);
    $("#t-value").textContent = q > 0 ? inr(q * px, 0) : "—";
  }
  $("#t-sym").onchange = (e) => { selectSymbol(e.target.value); invalidateVerdict(); };
  $("#t-qty").oninput = () => { updateTicketPrice(); invalidateVerdict(); };

  function renderVerdict(v) {
    const col = { APPROVED: "var(--up)", REDUCED: "var(--amber)", REJECTED: "var(--down)" }[v.status];
    const box = $("#t-verdict");
    box.classList.remove("hidden");
    box.style.borderColor = col;
    box.innerHTML = `
      <div class="flex items-center justify-between"><div class="label">RiskGuard verdict</div><span class="text-xs dim">${v.symbol} · ${v.side}</span></div>
      <div class="font-display text-3xl font-bold mt-2" style="color:${col}">${v.status}</div>
      ${v.against_ai ? `<div class="mt-3 rounded-lg px-3 py-2 text-xs" style="background:rgba(255,184,77,.12);color:var(--amber)">⚠ You are buying against the AI ${sigText(v.signal)} signal. You decide; RiskGuard allows it at 25% of the normal size.</div>` : ""}
      <div class="grid grid-cols-2 gap-x-4 gap-y-2 mt-4 text-sm">
        <div class="muted">Requested</div><div class="num text-right">${v.requested_qty ?? "auto"}</div>
        <div class="muted">Approved qty</div><div class="num text-right font-semibold">${v.approved_qty}</div>
        <div class="muted">Entry</div><div class="num text-right">${num(v.entry)}</div>
        ${v.stop_loss != null ? `<div class="muted">Stop loss</div><div class="num text-right down">${num(v.stop_loss)}</div>
        <div class="muted">Target</div><div class="num text-right up">${num(v.target)}</div>
        <div class="muted">Risk : reward</div><div class="num text-right">1 : ${num(v.risk_reward)}</div>
        <div class="muted">Capital at risk</div><div class="num text-right">${inr(v.risk_amount, 0)}</div>` : ""}
        <div class="muted">Stock exposure after</div><div class="num text-right">${pct(v.exposure_symbol_after)}</div>
        <div class="muted">Total exposure after</div><div class="num text-right">${pct(v.exposure_total_after)}</div>
        <div class="muted">Risk level</div><div class="text-right">${v.risk_level}</div>
      </div>
      <ul class="mt-4 space-y-1.5 text-xs">${v.reasons.map((r) => `<li class="flex gap-2"><span style="color:${col}">●</span><span class="muted">${r}</span></li>`).join("")}</ul>`;
  }

  $("#t-check").onclick = async () => {
    const q = parseInt($("#t-qty").value || "0", 10);
    try {
      const { verdict } = await post("/api/risk/evaluate", { symbol: $("#t-sym").value, side: S.side, qty: q > 0 ? q : null });
      S.lastVerdict = verdict;
      renderVerdict(verdict);
      $("#t-confirm").disabled = verdict.status === "REJECTED";
    } catch (e) { toast(e.message, "err"); }
  };

  $("#t-suggest").onclick = async () => {
    try {
      const { verdict } = await post("/api/risk/evaluate", { symbol: $("#t-sym").value, side: S.side, qty: null });
      renderVerdict(verdict);
      if (verdict.approved_qty > 0) { $("#t-qty").value = verdict.approved_qty; updateTicketPrice(); S.lastVerdict = verdict; $("#t-confirm").disabled = false; }
      else { invalidateVerdict(); }
    } catch (e) { toast(e.message, "err"); }
  };

  $("#t-confirm").onclick = async () => {
    const q = parseInt($("#t-qty").value || "0", 10);
    $("#t-confirm").disabled = true;
    try {
      const r = await post("/api/paper/orders", { symbol: $("#t-sym").value, side: S.side, qty: q > 0 ? q : null });
      renderVerdict(r.verdict);
      if (r.order.status === "FILLED") toast(`Filled: ${r.order.side} ${r.order.filled_qty} ${r.order.symbol} @ ${num(r.order.fill_price)}`, "ok");
      else toast("Order rejected by RiskGuard", "err");
      refreshAccount();
    } catch (e) { toast(e.message, "err"); }
  };

  function tile(label, value, sub, subCls = "") {
    return `<div class="card p-4"><div class="label !text-[10px]">${label}</div><div class="num text-xl font-semibold mt-1">${value}</div>${sub != null ? `<div class="num text-xs mt-1 ${subCls}">${sub}</div>` : ""}</div>`;
  }

  async function refreshAccount() {
    if (!S.user) return;
    try {
      const [pf, orders] = await Promise.all([api("/api/paper/portfolio"), S.page === "trade" ? api("/api/paper/orders") : Promise.resolve(null)]);
      $("#side-equity").textContent = inr(pf.equity, 0);
      $("#side-pnl").textContent = `${signed(pf.total_pnl, 0)} (${signed(pf.total_return_pct, 2)}%)`;
      $("#side-pnl").className = "num text-xs mt-1 " + cls(pf.total_pnl);
      const tiles = tile("Equity", inr(pf.equity, 0), `${signed(pf.total_return_pct, 2)}%`, cls(pf.total_pnl)) +
        tile("Cash", inr(pf.cash, 0), `of ${inr(pf.starting_cash, 0)}`, "dim") +
        tile("Unrealised P&L", `<span class="${cls(pf.unrealised_pnl)}">${signed(pf.unrealised_pnl, 0)}</span>`, `${Object.keys(pf.positions).length} open position(s)`, "dim") +
        tile("Realised P&L", `<span class="${cls(pf.realised_pnl)}">${signed(pf.realised_pnl, 0)}</span>`, `today ${signed(pf.realised_today, 0)}`, cls(pf.realised_today));
      $("#acct-tiles").innerHTML = tiles;
      const pos = Object.entries(pf.positions);
      $("#pos-table").innerHTML = `<thead><tr><th>Symbol</th><th class="text-right">Qty</th><th class="text-right">Avg</th><th class="text-right">Mark</th><th class="text-right">Value</th><th class="text-right">P&L</th><th></th></tr></thead><tbody>` +
        (pos.length ? pos.map(([s, p]) => `<tr><td class="font-semibold">${s}</td><td class="num text-right">${p.qty}</td><td class="num text-right">${num(p.avg_price)}</td><td class="num text-right">${num(p.mark)}</td><td class="num text-right">${inr(p.market_value, 0)}</td><td class="num text-right ${cls(p.unrealised_pnl)}">${signed(p.unrealised_pnl, 0)} (${signed(p.unrealised_pct, 2)}%)</td><td class="text-right"><button class="text-xs text-[var(--down)] hover:underline" data-close="${s}" data-qty="${p.qty}">Close</button></td></tr>`).join("")
          : `<tr><td colspan="7" class="text-center dim py-8">No open positions. Check an AI signal, then place your first paper trade.</td></tr>`) + "</tbody>";
      if (orders) {
        $("#orders-table").innerHTML = `<thead><tr><th>Time</th><th>Symbol</th><th>Side</th><th class="text-right">Qty</th><th class="text-right">Price</th><th>Status</th><th>AI</th><th>RiskGuard</th></tr></thead><tbody>` +
          (orders.length ? orders.map((o) => `<tr>
            <td class="num dim">${new Date(o.ts * 1000).toLocaleTimeString("en-IN", { hour12: false })}</td>
            <td class="font-semibold">${o.symbol}</td><td class="${o.side === "BUY" ? "up" : "down"}">${o.side}</td>
            <td class="num text-right">${o.filled_qty || o.requested_qty || "—"}</td><td class="num text-right">${o.fill_price != null ? num(o.fill_price) : "—"}</td>
            <td><span class="pill !py-0.5 !text-[11px]" style="color:${o.status === "FILLED" ? "var(--up)" : "var(--down)"}">${o.status}</span>${o.realised_pnl != null ? `<div class="num text-[11px] ${cls(o.realised_pnl)}">${signed(o.realised_pnl, 0)}</div>` : ""}</td>
            <td class="text-xs" style="color:${SIG_COLOR[o.signal?.signal] || ""}">${sigText(o.signal?.signal)} ${o.signal?.confidence != null ? pct(o.signal.confidence, 0) : ""}</td>
            <td class="text-xs muted max-w-[280px]">${o.risk_status}: ${(o.risk_reasons || [])[0] || ""}</td></tr>`).join("")
            : `<tr><td colspan="8" class="text-center dim py-8">No orders yet.</td></tr>`) + "</tbody>";
      }
    } catch (_) {}
  }

  // Delegated handler: the positions table is re-rendered every few seconds,
  // so a single listener on the table survives re-renders (no lost clicks).
  let closing = false;
  $("#pos-table").addEventListener("click", async (e) => {
    const b = e.target.closest("[data-close]");
    if (!b || closing) return;
    closing = true;
    try {
      const r = await post("/api/paper/orders", { symbol: b.dataset.close, side: "SELL", qty: parseInt(b.dataset.qty, 10) });
      toast(`Closed ${b.dataset.close}: realised ${signed(r.order.realised_pnl || 0, 0)}`, r.order.realised_pnl >= 0 ? "ok" : "err");
      refreshAccount();
    } catch (err) { toast(err.message, "err"); }
    finally { closing = false; }
  });

  // ======================= PORTFOLIO & RISK =======================
  let equityChart;
  async function refreshRisk() {
    if (!S.user) return;
    try {
      const [r, eq] = await Promise.all([api("/api/risk/portfolio"), api("/api/paper/equity")]);
      const pf = r.portfolio, L = r.limits;
      $("#pf-tiles").innerHTML = tile("Equity", inr(pf.equity, 0), `${signed(pf.total_pnl, 0)} total`, cls(pf.total_pnl)) +
        tile("Total exposure", pct(pf.exposure), `limit ${pct(L.max_total_exposure, 0)}`, "dim") +
        tile("Daily loss used", pct(r.daily_loss_used), `limit ${pct(L.daily_loss_limit, 0)} of capital`, "dim") +
        tile("Open positions", Object.keys(pf.positions).length, `cash ${inr(pf.cash, 0)}`, "dim");
      const bar = (label, v, limit, color) => `
        <div><div class="flex justify-between"><span class="muted">${label}</span><span class="num">${pct(v)} <span class="dim">/ ${pct(limit, 0)}</span></span></div>
        <div class="relative bar-track mt-1.5"><div class="h-full rounded-full" style="width:${Math.min(100, v * 100)}%;background:${v > limit ? "var(--down)" : color}"></div>
        <div class="absolute top-0 bottom-0 w-px bg-white/60" style="left:${limit * 100}%"></div></div></div>`;
      $("#exposure").innerHTML = bar("Total portfolio", pf.exposure, L.max_total_exposure, "var(--mint)") +
        Object.keys(pf.positions).map((s) => bar(s, pf.positions[s]?.weight || 0, L.max_symbol_exposure, "var(--violet)")).join("") +
        bar("Daily loss budget", r.daily_loss_used, 1, "var(--amber)");
      $("#risk-table").innerHTML = `<thead><tr><th>Stock</th><th class="text-right">Ann. volatility</th><th class="text-right">Book imbalance</th><th class="text-right">Weight</th><th>Risk level</th></tr></thead><tbody>` +
        Object.entries(r.per_symbol).map(([s, v]) => {
          const lvl = v.annualised_volatility < 0.2 ? "LOW" : v.annualised_volatility < 0.4 ? "MODERATE" : "HIGH";
          const c = { LOW: "var(--up)", MODERATE: "var(--amber)", HIGH: "var(--down)" }[lvl];
          return `<tr><td class="font-semibold">${s}</td><td class="num text-right">${pct(v.annualised_volatility)}</td><td class="num text-right ${cls(v.imbalance)}">${signed(v.imbalance, 2)}</td><td class="num text-right">${pct(pf.positions[s]?.weight || 0)}</td><td><span class="pill !py-0.5 !text-[11px]" style="color:${c}">${lvl}</span></td></tr>`;
        }).join("") + "</tbody>";
      $("#limits").innerHTML = [
        ["Risk per trade", pct(L.risk_per_trade, 0) + " of equity"], ["Stop loss", L.stop_atr_multiple + " × ATR"],
        ["Min risk : reward", "1 : " + L.min_risk_reward], ["Max single-stock exposure", pct(L.max_symbol_exposure, 0)],
        ["Max total exposure", pct(L.max_total_exposure, 0)], ["Daily loss limit", pct(L.daily_loss_limit, 0) + " of capital"],
        ["AI gate", "HOLD → half size; buying against SELL / NO TRADE → warning, 25% size"],
      ].map(([k, v]) => `<div class="flex justify-between gap-4 py-2 border-b border-white/5"><span class="muted">${k}</span><span class="text-right">${v}</span></div>`).join("");

      const data = { labels: eq.map((p) => new Date(p.t * 1000).toLocaleTimeString("en-IN", { hour12: false })), datasets: [{ data: eq.map((p) => p.equity), borderColor: "#5cffb0", backgroundColor: "rgba(92,255,176,.08)", fill: true, tension: .3, pointRadius: 0, borderWidth: 2 }] };
      if (!equityChart) equityChart = new Chart($("#equity-chart"), { type: "line", data, options: chartOpts((v) => "₹" + Number(v).toLocaleString("en-IN")) });
      else { equityChart.data = data; equityChart.update("none"); }
    } catch (_) {}
  }
  $("#reset-btn").onclick = async () => {
    const b = $("#reset-btn");
    if (b.dataset.armed !== "1") { b.dataset.armed = "1"; b.textContent = "Click again to confirm reset"; setTimeout(() => { b.dataset.armed = ""; b.textContent = "Reset account"; }, 3000); return; }
    b.dataset.armed = ""; b.textContent = "Reset account";
    await post("/api/paper/reset"); toast("Account reset to ₹10,00,000", "ok"); refreshRisk(); refreshAccount();
  };

  // ======================= MONITOR =======================
  function chartOpts(fmt) {
    return {
      responsive: true, maintainAspectRatio: false, animation: false,
      plugins: { legend: { display: false }, tooltip: { mode: "index", intersect: false } },
      scales: {
        x: { ticks: { color: "#5b6577", maxTicksLimit: 8, font: { family: "JetBrains Mono", size: 10 } }, grid: { color: "rgba(255,255,255,.03)" } },
        y: { ticks: { color: "#5b6577", callback: fmt, font: { family: "JetBrains Mono", size: 10 } }, grid: { color: "rgba(255,255,255,.04)" } },
      },
    };
  }
  let epsChart, histChart, rateTouched = 0;
  function onMonitor(m) {
    const p = m.processing_latency_us || {}, e = m.end_to_end_latency_us || {};
    const us = (v) => v == null ? "—" : v >= 1000 ? (v / 1000).toFixed(1) + " ms" : v + " µs";
    $("#mon-tiles").innerHTML =
      tile("Events / sec", num(m.events_per_sec, 0), `target ${num(m.target_rate, 0)}`, "dim") +
      tile("P50 processing", us(p.p50)) + tile("P95 processing", us(p.p95)) + tile("P99 processing", us(p.p99)) +
      tile("P99 end-to-end", us(e.p99), "incl. batching + queue wait", "dim") +
      tile("Queue depth", num(m.queue_depth, 0), `dropped ${m.dropped}`, "dim") +
      tile("Total events", num(m.total_events, 0)) + tile("Recorded", num(m.recorder.recorded, 0), `${m.recorder.files} parquet files`, "dim");
    if (Date.now() - rateTouched > 3000) { $("#rate").value = m.target_rate; $("#rate-val").textContent = m.target_rate.toLocaleString("en-IN"); }
    if (S.page !== "monitor") return;
    const ed = { labels: m.eps_history.map((x) => new Date(x.t * 1000).toLocaleTimeString("en-IN", { hour12: false })), datasets: [{ data: m.eps_history.map((x) => x.eps), borderColor: "#5cc8ff", backgroundColor: "rgba(92,200,255,.1)", fill: true, tension: .3, pointRadius: 0, borderWidth: 2 }] };
    if (!epsChart) epsChart = new Chart($("#eps-chart"), { type: "line", data: ed, options: chartOpts((v) => v) }); else { epsChart.data = ed; epsChart.update("none"); }
    const h = m.histogram || { edges: [], counts: [] };
    const hd = { labels: h.edges, datasets: [{ data: h.counts, backgroundColor: "rgba(139,123,255,.55)", borderRadius: 6 }] };
    if (!histChart) histChart = new Chart($("#hist-chart"), { type: "bar", data: hd, options: chartOpts((v) => v) }); else { histChart.data = hd; histChart.update("none"); }
    const stage = (name, sub, col) => `<div class="card p-3 text-center flex-1 min-w-[100px]"><div class="text-xs font-semibold" style="color:${col}">${name}</div><div class="num text-[11px] dim mt-1">${sub}</div></div>`;
    const arrow = `<div class="dim self-center">→</div>`;
    $("#pipeline").innerHTML = `<div class="flex flex-wrap gap-2 items-stretch">${stage("Simulator", num(m.target_rate, 0) + "/s", "var(--sky)")}${arrow}${stage("Event bus", "depth " + m.queue_depth, "var(--sky)")}${arrow}${stage("Processor", "p99 " + p.p99 + "µs", "var(--violet)")}${arrow}${stage("State + WS", Object.keys(S.market).length + " symbols", "var(--mint)")}${arrow}${stage("Recorder", m.recorder.buffered + " buffered", "var(--amber)")}</div>`;
    $("#recorder").innerHTML = `<div class="grid grid-cols-2 gap-2 text-xs">
      <div class="muted">Session</div><div class="mono text-right">${m.recorder.session}</div>
      <div class="muted">Last write</div><div class="num text-right">${m.recorder.last_write_ms} ms (background thread)</div>
      <div class="muted">Since last flush</div><div class="num text-right">${m.recorder.seconds_since_flush} s</div>
      <div class="muted">Uptime</div><div class="num text-right">${num(m.uptime_s, 0)} s</div></div>`;
  }
  $("#rate").oninput = (e) => { rateTouched = Date.now(); $("#rate-val").textContent = Number(e.target.value).toLocaleString("en-IN"); };
  $("#rate").onchange = async (e) => { rateTouched = Date.now(); try { await post("/api/monitor/rate", { events_per_sec: Number(e.target.value) }); toast("Feed rate set to " + e.target.value + " events/sec", "ok"); } catch (err) { toast(err.message, "err"); } };

  // ======================= BOOT =======================
  async function boot() {
    initChart();
    const syms = await (await fetch("/api/symbols")).json();
    syms.forEach((s) => (S.market[s.symbol] = { ...s, bids: [], asks: [], spread: 0 }));
    renderWatchlist();
    await loadCandles(S.symbol);
    connectWS("/ws/market", onMarket);
    connectWS("/ws/monitor", onMonitor);
    refreshMiniSignal();
    setInterval(refreshMiniSignal, 8000);
    setInterval(() => { if (S.page === "signals") loadSignal(S.symbol, false); }, 10000);
    setInterval(() => { refreshAccount(); if (S.page === "portfolio") refreshRisk(); }, 3000);
    setSide("BUY");
    const start = location.hash.slice(1);
    if (TITLES[start]) go(start);
  }
  initAuth().catch(() => showAuth());
  boot().catch((e) => toast("Could not reach the backend: " + e.message, "err"));
})();
