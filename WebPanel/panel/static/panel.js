// github.com/Shran21
(function () {
  "use strict";
  var doc = document, root = doc.documentElement;
  var T = {};
  try { T = JSON.parse(doc.getElementById("panel-i18n").textContent) || {}; } catch (e) {}
  function tr(key, fallback) { return T[key] || fallback; }

  /* ---- theme: auto -> light -> dark -> auto -------------------------- */
  function stored() { try { return localStorage.getItem("panel_theme") || ""; } catch (e) { return ""; } }
  function apply(mode) {
    if (mode === "light" || mode === "dark") { root.dataset.theme = mode; }
    else { delete root.dataset.theme; }
    doc.querySelectorAll("[data-theme-toggle]").forEach(function (button) {
      button.dataset.mode = mode || "auto";
      button.title = tr("theme." + (mode || "auto"), mode || "auto");
    });
  }
  function cycle() {
    var now = stored(), next = now === "" ? "light" : now === "light" ? "dark" : "";
    try { if (next) { localStorage.setItem("panel_theme", next); } else { localStorage.removeItem("panel_theme"); } } catch (e) {}
    apply(next);
  }
  apply(stored());

  /* ---- clicks and keys: drawer, theme, palette, row links ------------ */
  doc.addEventListener("click", function (ev) {
    var hit = ev.target.closest("[data-drawer]");
    if (hit) {
      var want = hit.dataset.drawer;
      if (want === "open") { doc.body.classList.add("drawer-open"); }
      else if (want === "close") { doc.body.classList.remove("drawer-open"); }
      else { doc.body.classList.toggle("drawer-open"); }
      return;
    }
    if (ev.target.closest("[data-theme-toggle]")) { cycle(); return; }
    if (ev.target.closest("[data-palette-open]")) { openPalette(); return; }
    var row = ev.target.closest("tr.rowlink[data-href]");
    if (row && !ev.target.closest("a, button, input, select, label, form")) {
      location.href = row.dataset.href;
    }
  });
  doc.addEventListener("keydown", function (ev) {
    var target = ev.target;
    if (ev.key === "Enter" && target && target.matches && target.matches("tr.rowlink[data-href]")) {
      location.href = target.dataset.href;
      return;
    }
    if ((ev.ctrlKey || ev.metaKey) && !ev.altKey && (ev.key === "k" || ev.key === "K")) {
      ev.preventDefault();
      openPalette();
    }
  });

  /* ---- confirmation: a dialog that names what it is about to do ------- */
  var dialog = doc.getElementById("confirm-dialog");
  doc.addEventListener("submit", function (ev) {
    var form = ev.target;
    if (!(form instanceof HTMLFormElement) || !form.hasAttribute("data-ask")) { return; }
    if (form.dataset.confirmed === "1") { delete form.dataset.confirmed; return; }
    ev.preventDefault();
    var submitter = ev.submitter || null;
    ask(form.dataset.ask, form.dataset.askDetail || "", function (ok) {
      if (!ok) { return; }
      form.dataset.confirmed = "1";
      if (form.requestSubmit) { form.requestSubmit(submitter || undefined); } else { form.submit(); }
    });
  }, true);

  function ask(text, detail, done) {
    if (!dialog || typeof dialog.showModal !== "function") { done(window.confirm(text)); return; }
    dialog.querySelector(".dlg-text").textContent = text;
    var extra = dialog.querySelector(".dlg-detail");
    extra.textContent = detail;
    extra.hidden = !detail;
    var settled = false;
    function settle(ok) {
      if (settled) { return; }
      settled = true;
      dialog.removeEventListener("close", onClose);
      if (dialog.open) { dialog.close(); }
      done(ok);
    }
    function onClose() { settle(false); }
    dialog.querySelector("[data-ok]").onclick = function () { settle(true); };
    dialog.querySelector("[data-cancel]").onclick = function () { settle(false); };
    dialog.addEventListener("close", onClose);
    dialog.showModal();
    dialog.querySelector("[data-cancel]").focus();
  }

  /* ---- live pages: one event stream, timed polling as the fallback ---- */
  var regions = Array.prototype.slice.call(doc.querySelectorAll("[data-refresh]"));
  if (regions.length) { setupLive(regions); }

  function setupLive(regions) {
    var region = regions[0];
    var dirty = false, stamp = null, lastAt = Date.now(), mode = "";
    regions.forEach(function (r) {
      r.addEventListener("input", function () { dirty = true; });
      r.addEventListener("change", function () { dirty = true; });
    });
    function typing() {
      var active = doc.activeElement;
      return active && ["INPUT", "SELECT", "TEXTAREA"].indexOf(active.tagName) >= 0
        && regions.some(function (r) { return r.contains(active); });
    }
    function busy() {
      // a swap under an open dialog would detach the form it is about to submit
      return dirty || typing() || (dialog && dialog.open) || (palette && palette.open);
    }
    function refresh() {
      if (busy()) { return; }
      fetch(location.href, { credentials: "same-origin", headers: { "X-Requested-With": "panel" } })
        .then(function (r) { return r.text(); })
        .then(function (html) {
          if (busy()) { return; }
          var fresh = new DOMParser().parseFromString(html, "text/html").querySelectorAll("[data-refresh]");
          if (!fresh.length) { return; }
          regions.forEach(function (r, i) { if (fresh[i]) { r.innerHTML = fresh[i].innerHTML; } });
          lastAt = Date.now();
          paintStamp();
          tickUptime();
        })
        .catch(function () {});
    }
    var head = doc.querySelector(".page-head");
    if (head) {
      stamp = doc.createElement("span");
      stamp.className = "livestamp";
      stamp.innerHTML = "<i></i><span></span>";
      head.appendChild(stamp);
    }
    function paintStamp() {
      if (!stamp) { return; }
      var seconds = Math.max(0, Math.round((Date.now() - lastAt) / 1000));
      stamp.querySelector("span").textContent =
        (mode === "sse" ? tr("live.on", "live") : tr("live.poll", "polling"))
        + " · " + tr("live.ago", "{n}s").replace("{n}", seconds);
      stamp.classList.toggle("is-live", mode === "sse");
    }
    setInterval(paintStamp, 1000);

    var every = (parseFloat(region.dataset.refresh) || 10) * 1000;
    var poll = null;
    function startPolling() {
      if (poll) { return; }
      mode = "poll";
      poll = setInterval(refresh, every);
      paintStamp();
    }
    if (window.EventSource) {
      var source = new EventSource("/events");
      var minGap = 2500, lastRefresh = 0, pending = null;
      function soon() {
        if (pending) { return; }
        var wait = Math.max(0, minGap - (Date.now() - lastRefresh));
        pending = setTimeout(function () { pending = null; lastRefresh = Date.now(); refresh(); }, wait);
      }
      source.addEventListener("open", function () {
        mode = "sse";
        if (poll) { clearInterval(poll); poll = null; }
        paintStamp();
      });
      source.addEventListener("change", soon);
      source.addEventListener("tick", soon);
      source.addEventListener("error", function () { startPolling(); });
    } else {
      startPolling();
    }
    paintStamp();
  }

  /* ---- palette: Ctrl+K finds a pilot, a sector or a card -------------- */
  var palette = doc.getElementById("palette");
  var palInput = palette && palette.querySelector("input");
  var palList = palette && palette.querySelector(".pal-list");
  var palTimer = null, palSeq = 0, palActive = -1;

  function openPalette() {
    if (!palette || typeof palette.showModal !== "function") { return; }
    if (!palette.open) { palette.showModal(); }
    palInput.value = "";
    renderPalette(null);
    palInput.focus();
  }
  function palItems() { return Array.prototype.slice.call(palList.querySelectorAll(".pal-item")); }
  function move(delta) {
    var list = palItems();
    if (!list.length) { return; }
    palActive = (palActive + delta + list.length) % list.length;
    list.forEach(function (el, i) { el.classList.toggle("is-active", i === palActive); });
    list[palActive].scrollIntoView({ block: "nearest" });
  }
  function renderPalette(groups) {
    palList.textContent = "";
    palActive = -1;
    if (!groups) { return; }
    var count = 0;
    ["pilots", "sectors", "cards"].forEach(function (kind) {
      var items = groups[kind] || [];
      if (!items.length) { return; }
      var head = doc.createElement("div");
      head.className = "pal-group";
      head.textContent = tr("palette." + kind, kind);
      palList.appendChild(head);
      items.forEach(function (item) {
        var link = doc.createElement("a");
        link.className = "pal-item";
        link.href = item.href;
        var title = doc.createElement("span");
        title.textContent = item.title;
        link.appendChild(title);
        if (item.meta) {
          var meta = doc.createElement("span");
          meta.className = "dim mono";
          meta.textContent = item.meta;
          link.appendChild(meta);
        }
        palList.appendChild(link);
        count++;
      });
    });
    if (!count) {
      var empty = doc.createElement("div");
      empty.className = "pal-empty dim";
      empty.textContent = tr("palette.empty", "—");
      palList.appendChild(empty);
    } else {
      move(1);
    }
  }
  if (palette) {
    palInput.addEventListener("input", function () {
      var q = palInput.value.trim();
      clearTimeout(palTimer);
      if (!q) { renderPalette(null); return; }
      palTimer = setTimeout(function () {
        var seq = ++palSeq;
        fetch("/search?q=" + encodeURIComponent(q), { credentials: "same-origin" })
          .then(function (r) { return r.json(); })
          .then(function (data) { if (seq === palSeq) { renderPalette(data); } })
          .catch(function () {});
      }, 120);
    });
    palette.addEventListener("keydown", function (ev) {
      if (ev.key === "ArrowDown") { ev.preventDefault(); move(1); }
      else if (ev.key === "ArrowUp") { ev.preventDefault(); move(-1); }
      else if (ev.key === "Enter") {
        var list = palItems();
        if (palActive >= 0 && list[palActive]) { ev.preventDefault(); location.href = list[palActive].href; }
      }
    });
    palette.addEventListener("click", function (ev) { if (ev.target === palette) { palette.close(); } });
  }

  /* ---- uptime: the server gives seconds, the browser keeps them moving --- */
  function twoDigits(n) { return (n < 10 ? "0" : "") + n; }
  function tickUptime() {
    var now = Date.now();
    doc.querySelectorAll("[data-uptime]").forEach(function (el) {
      var base = parseInt(el.dataset.uptime, 10);
      if (isNaN(base)) { return; }
      if (el._uptimeFor !== el.dataset.uptime) { el._uptimeFor = el.dataset.uptime; el._uptimeAt = now; }
      var total = base + Math.floor((now - el._uptimeAt) / 1000);
      var hours = Math.floor(total / 3600), minutes = Math.floor((total % 3600) / 60), seconds = total % 60;
      el.textContent = twoDigits(hours) + ":" + twoDigits(minutes) + ":" + twoDigits(seconds);
    });
  }
  window.panelTick = tickUptime;
  setInterval(tickUptime, 1000);
  tickUptime();

  /* ---- copy helper for pages that offer it ----------------------------- */
  doc.addEventListener("click", function (ev) {
    var button = ev.target.closest("[data-copy-from]");
    if (!button) { return; }
    var source = doc.getElementById(button.dataset.copyFrom);
    if (!source || !navigator.clipboard) { return; }
    navigator.clipboard.writeText(source.innerText).then(function () {
      var was = button.textContent;
      button.textContent = tr("logs.copied", "ok");
      setTimeout(function () { button.textContent = was; }, 1400);
    }).catch(function () {});
  });
})();
