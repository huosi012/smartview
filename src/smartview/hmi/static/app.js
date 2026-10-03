/* smartview HMI 前端：WebSocket 推送 + 轮询兜底，无第三方依赖。 */
(function () {
  const $ = (id) => document.getElementById(id);
  const LEVEL_NAME = { 0: "正常", 1: "注意", 2: "警告", 3: "危险" };
  let lastVersion = -1;
  let wsOk = false;
  let settings = {};
  let eventsTimer = null;
  let audioCtx = null;
  let lastBeep = 0;
  // ?stream=jpg：低带宽 / 截图模式，用单帧 JPEG 轮询代替 MJPEG 长连接
  const JPG_MODE = new URLSearchParams(location.search).get("stream") === "jpg";

  function fmtTime(ts) {
    if (!ts) return "—";
    const d = new Date(ts * 1000);
    return d.toLocaleTimeString("zh-CN", { hour12: false }) + "." + String(d.getMilliseconds()).padStart(3, "0").slice(0, 1);
  }

  function beep(level) {
    if (!$("beep").checked) return;
    const now = performance.now();
    if (now - lastBeep < (level >= 3 ? 400 : 1200)) return;
    lastBeep = now;
    try {
      audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)();
      const o = audioCtx.createOscillator();
      const g = audioCtx.createGain();
      o.frequency.value = level >= 3 ? 1600 : 1200;
      g.gain.value = 0.2;
      o.connect(g).connect(audioCtx.destination);
      o.start();
      o.stop(audioCtx.currentTime + (level >= 3 ? 0.25 : 0.15));
    } catch (e) { /* 忽略 */ }
  }

  function renderAlarm(a) {
    const lv = a.level;
    document.body.dataset.level = lv;
    const banner = $("banner");
    banner.className = "banner l" + lv;
    $("levelBadge").textContent = "L" + lv;
    $("levelName").textContent = a.level_zh || LEVEL_NAME[lv];
    $("message").textContent = a.message || "";
    let sub = [];
    if (a.top) {
      if (a.top.ttc_s != null) sub.push("TTC " + a.top.ttc_s.toFixed(1) + " s");
      if (a.top.row != null) sub.push("第 " + (a.top.row + 1) + " 行");
      sub.push(a.top.cam_id + " #" + a.top.track_id);
      if (a.top.reasons && a.top.reasons.length) sub.push(a.top.reasons.join("，"));
    }
    if (a.acked) sub.push("已确认");
    if (a.muted_until && a.muted_until > a.ts) sub.push("已静音");
    if (a.sensor_fault) sub.push("⚠ " + a.fault_reasons.join("；"));
    $("subline").textContent = sub.join(" · ");
    if (lv >= 2 && a.buzzer_on) beep(lv);
  }

  function renderCams(cams, alarm) {
    const root = $("cams");
    const ids = Object.keys(cams).sort();
    const roleMap = {};
    (settings.cameras || []).forEach((c) => { roleMap[c.id] = c.role_zh; });
    ids.forEach((id) => {
      let el = document.getElementById("cam-" + id);
      if (!el) {
        el = document.createElement("div");
        el.className = "cam";
        el.id = "cam-" + id;
        const src = JPG_MODE ? "/api/cam/" + encodeURIComponent(id) + ".jpg?t=0" : "/stream/" + encodeURIComponent(id) + ".mjpg";
        el.innerHTML = '<div class="hd"><span class="name"></span><span class="status"></span></div>' +
          '<img alt="' + id + '" src="' + src + '">' +
          '<div class="tracks"></div>';
        root.appendChild(el);
      }
      if (JPG_MODE) {
        const im = el.querySelector("img");
        if (!im.dataset.ts || Date.now() - Number(im.dataset.ts) > 250) {
          im.dataset.ts = String(Date.now());
          im.src = "/api/cam/" + encodeURIComponent(id) + ".jpg?t=" + im.dataset.ts;
        }
      }
      const c = cams[id];
      const h = c.health || {};
      el.className = "cam l" + (alarm.per_cam && alarm.per_cam[id] != null ? alarm.per_cam[id] : c.level || 0);
      el.querySelector(".name").textContent = (roleMap[id] || "") + " " + id + (c.purging ? "（吹扫中）" : "");
      const st = el.querySelector(".status");
      st.textContent = (h.status_zh || "—") + " · " + (h.fps != null ? h.fps.toFixed(0) : "--") + " fps · " + (c.infer_ms != null ? c.infer_ms.toFixed(0) : "--") + " ms";
      st.className = "status" + (h.ok === false ? " bad" : "");
      const tr = el.querySelector(".tracks");
      if (!c.tracks || !c.tracks.length) tr.textContent = "无目标";
      else tr.innerHTML = c.tracks.map((t) => "<b>" + (t.cls_zh || t.cls) + "</b> " + (t.dist_m != null ? t.dist_m.toFixed(1) + " m" : "") + (t.in_path ? " 路径内" : " 路径外") + (t.row != null ? " 第" + (t.row + 1) + "行" : "")).join("　");
    });
  }

  function renderState(s) {
    settings = s.settings || settings;
    renderAlarm(s.alarm);
    renderCams(s.cameras || {}, s.alarm);
    const sp = s.speed || {};
    $("speed").textContent = sp.kmh != null ? sp.kmh.toFixed(1) + " km/h" : "--";
    const src = $("speedSrc");
    src.textContent = sp.source === "nmea" ? (sp.quality === "ok" ? "GNSS" : "GNSS 失锁") : "手动";
    src.className = "badge " + (sp.source === "nmea" ? (sp.quality === "ok" ? "ok" : "stale") : "");
    if (settings.sensitivity && document.activeElement !== $("sensitivity")) $("sensitivity").value = settings.sensitivity;
    if (settings.speed_kmh != null && document.activeElement !== $("speedInput")) $("speedInput").value = settings.speed_kmh;
    const sys = s.system || {};
    if (sys.events) $("eventCount").textContent = sys.events.total;
    const p = s.purge || {};
    if (p.enabled) {
      const chs = Object.entries(p.channels || {}).map(([k, v]) => k + (v.active ? "（进行中）" : v.count ? "×" + v.count : "")).join(" ");
      $("purgeInfo").textContent = chs + (p.next_periodic_in_s != null ? " · 下次 " + Math.max(0, p.next_periodic_in_s).toFixed(0) + " s" : "");
    } else $("purgeInfo").textContent = "未启用";
    $("footer").textContent = "smartview " + (s.version_str || "") + " · " + (sys.mode === "live" ? "真机" : "回放") + " · 运行 " + Math.round(s.uptime_s || 0) + " s" + (sys.disk_free_gb != null ? " · 磁盘剩余 " + sys.disk_free_gb + " GB" : "") + (sys.load1 != null ? " · 负载 " + sys.load1 : "");
    $("conn").textContent = wsOk ? "WebSocket" : "轮询";
  }

  async function loadEvents() {
    try {
      const r = await fetch("/api/events?limit=50");
      const j = await r.json();
      const rows = j.events.map((e) => "<tr><td>" + fmtTime(e.ts_start) + "</td><td class='l" + e.level_max + "'>L" + e.level_max + " " + e.level_zh + "</td><td>" + e.cam_id + "</td><td>" + (e.cls_zh || e.cls_name) + "</td><td>" + (e.dist_min != null ? e.dist_min.toFixed(1) + " m" : "—") + "</td><td>" + (e.ttc_min != null ? e.ttc_min.toFixed(1) + " s" : "—") + "</td><td>" + (e.acked ? "✔" : "") + "</td><td>" + (e.snapshot_path ? "<a href='/api/events/" + e.event_id + "/snapshot.jpg' target='_blank'>查看</a>" : "") + (e.clip_path ? " <a href='/api/events/" + e.event_id + "/clip'>片段</a>" : "") + "</td></tr>").join("");
      $("eventRows").innerHTML = rows || "<tr><td colspan='8'>暂无事件</td></tr>";
      const by = j.stats.by_level || {};
      $("stats").textContent = "共 " + j.stats.total + " 条" + (by.L3 ? "，危险 " + by.L3 : "") + (by.L2 ? "，警告 " + by.L2 : "");
      $("eventCount").textContent = j.stats.total;
    } catch (e) { /* 忽略 */ }
  }

  async function post(url, body) {
    try {
      const r = await fetch(url, { method: body === undefined ? "POST" : "POST", headers: { "Content-Type": "application/json" }, body: body === undefined ? null : JSON.stringify(body) });
      return await r.json();
    } catch (e) { return null; }
  }

  $("btnAck").onclick = () => post("/api/ack");
  $("btnMute").onclick = () => post("/api/mute", { seconds: 30 });
  $("btnUnmute").onclick = () => post("/api/unmute");
  $("btnTest").onclick = () => post("/api/test-alarm", { level: 2 });
  $("btnPurge").onclick = () => post("/api/purge", {});
  $("sensitivity").onchange = (e) => fetch("/api/settings", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ sensitivity: e.target.value }) });
  $("btnSpeed").onclick = () => fetch("/api/settings", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ speed_kmh: parseFloat($("speedInput").value) }) });

  async function poll() {
    if (wsOk) return;
    try {
      const r = await fetch("/api/state");
      const s = await r.json();
      if (s.version !== lastVersion) { lastVersion = s.version; renderState(s); }
    } catch (e) { $("conn").textContent = "断开"; }
  }

  function connectWs() {
    let ws;
    try { ws = new WebSocket((location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws"); } catch (e) { return; }
    ws.onopen = () => { wsOk = true; };
    ws.onmessage = (ev) => { try { const s = JSON.parse(ev.data); lastVersion = s.version; renderState(s); } catch (e) { /* 忽略 */ } };
    ws.onclose = () => { wsOk = false; setTimeout(connectWs, 2000); };
    ws.onerror = () => { wsOk = false; try { ws.close(); } catch (e) { /* 忽略 */ } };
  }

  connectWs();
  setInterval(poll, 500);
  poll();
  loadEvents();
  eventsTimer = setInterval(loadEvents, 3000);
})();
