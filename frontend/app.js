// Financial Planer — local frontend. Talks to the local FastAPI backend.
// No AI in the money logic: OCR only reads, the server computes.

const PALETTE = ["#8b7cf0", "#f0955f", "#3cbfa2", "#e585ba", "#6aa9f0", "#c58cf0", "#f0c25f", "#5fbf9a"];
const MONTHS_DE = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli",
  "August", "September", "Oktober", "November", "Dezember"];

const api = {
  async get(u) { const r = await fetch(u); if (!r.ok) throw new Error(await r.text()); return r.json(); },
  async send(u, method, body) {
    const r = await fetch(u, {
      method,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  },
};

const $ = (s) => document.querySelector(s);
let overview = { balance_cents: 0, unsorted: [], categories: [] };
const colorForName = {};

function fmt(cents) {
  const neg = cents < 0; cents = Math.abs(cents);
  const s = Math.floor(cents / 100).toLocaleString("de-DE") + "," + String(cents % 100).padStart(2, "0");
  return (neg ? "−" : "") + s + " €";
}
function toCents(str) {
  let c = String(str == null ? "" : str).replace(/[^\d.,-]/g, "");
  if (!c) return 0;
  const neg = c.trim().indexOf("-") === 0; c = c.replace(/-/g, "");
  const d = Math.max(c.lastIndexOf("."), c.lastIndexOf(","));
  let ip, fp;
  if (d === -1) { ip = c; fp = ""; } else { ip = c.slice(0, d); fp = c.slice(d + 1); }
  ip = ip.replace(/[^\d]/g, "") || "0"; fp = (fp.replace(/[^\d]/g, "") + "00").slice(0, 2);
  const cents = parseInt(ip, 10) * 100 + parseInt(fp || "0", 10);
  return neg ? -cents : cents;
}
function esc(s) { return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;"); }
function monthLabel(key) { const [y, m] = key.split("-"); return MONTHS_DE[parseInt(m, 10) - 1] + " " + y; }

// ---- load / render ----------------------------------------------------------

async function refresh() {
  overview = await api.get("/api/overview");
  overview.categories.forEach((c, i) => { colorForName[c.name] = PALETTE[i % PALETTE.length]; });
  renderBalance();
  renderDeck();
  renderGrid();
}

function renderBalance() {
  const el = $("#bal-val");
  el.textContent = fmt(overview.balance_cents);
  el.classList.toggle("neg", overview.balance_cents < 0);
  const n = overview.unsorted.length;
  $("#count").textContent = n ? " · " + n + " offen" : "";
}

function buildCard(tx) {
  const card = document.createElement("div");
  card.className = "card";
  card.dataset.id = tx.id;
  card.innerHTML =
    '<input class="payee" value="' + esc(tx.payee || "") + '" placeholder="Empfänger…">' +
    '<input class="amount" inputmode="decimal" value="' + fmt(tx.amount_cents) + '">';
  return card;
}

function renderDeck() {
  const deck = $("#deck");
  deck.innerHTML = "";
  const cards = overview.unsorted;
  const empty = cards.length === 0;
  $("#deck-empty").hidden = !empty; deck.hidden = empty;

  const shown = cards.slice(0, 3);
  for (let i = shown.length - 1; i >= 0; i--) {
    const tx = shown[i];
    const card = buildCard(tx);
    card.style.zIndex = String(10 - i);
    card.style.transform = "translateY(" + (i * -12) + "px) scale(" + (1 - i * 0.05) + ")";
    card.style.opacity = i === 0 ? "1" : (i === 1 ? "0.9" : "0.75");
    if (i === 0) {
      const amt = card.querySelector(".amount");
      amt.addEventListener("focus", () => { amt.value = (Math.abs(tx.amount_cents) / 100).toString().replace(".", ","); });
      amt.addEventListener("blur", async () => {
        const cents = -Math.abs(toCents(amt.value));
        if (cents !== tx.amount_cents) { await api.send("/api/transactions/" + tx.id, "PATCH", { amount_cents: cents }); await refresh(); }
        else { amt.value = fmt(tx.amount_cents); }
      });
      card.querySelector(".payee").addEventListener("blur", (e) => {
        if (e.target.value !== (tx.payee || "")) api.send("/api/transactions/" + tx.id, "PATCH", { payee: e.target.value });
      });
      enableDrag(card, tx, (target) => { const inp = target.closest("input"); if (inp) { try { inp.focus(); } catch (_) {} } });
    } else { card.classList.add("behind"); }
    deck.appendChild(card);
  }
}

function renderGrid() {
  const grid = $("#grid"); grid.innerHTML = "";
  overview.categories.forEach((cat, i) => {
    const box = document.createElement("div");
    box.className = "cat"; box.dataset.id = cat.id;
    box.innerHTML =
      '<button class="x" title="Box löschen">✕</button>' +
      '<div class="nm"><span class="dot" style="background:' + PALETTE[i % PALETTE.length] + '"></span>' + esc(cat.name) + "</div>" +
      '<div class="tot">' + fmt(cat.total_cents) + "</div>" +
      '<div class="cnt">' + cat.count + " Einträge · tippen</div>";
    box.addEventListener("click", () => openCategory(cat.id, cat.name, i));
    box.querySelector(".x").addEventListener("click", async (e) => {
      e.stopPropagation();
      if (cat.count && !confirm('"' + cat.name + '" löschen? Einträge wandern zurück in den Stapel.')) return;
      await api.send("/api/categories/" + cat.id, "DELETE"); await refresh();
    });
    grid.appendChild(box);
  });
  const add = document.createElement("div");
  add.className = "cat add"; add.textContent = "＋ Box";
  add.addEventListener("click", async () => {
    const name = (prompt("Name der neuen Kategorie-Box:") || "").trim();
    if (!name) return;
    try { await api.send("/api/categories", "POST", { name }); await refresh(); }
    catch { alert("Kategorie existiert schon oder ist ungültig."); }
  });
  grid.appendChild(add);
}

// ---- drag & drop (pointer capture, works on touch + mouse) ------------------

function enableDrag(card, tx, onTap) {
  card.addEventListener("touchmove", (e) => e.preventDefault(), { passive: false });
  card.addEventListener("pointerdown", (e) => {
    if (e.button && e.button !== 0) return;
    const startTarget = e.target;
    const sx = e.clientX, sy = e.clientY; let dragging = false, ghost = null;
    const rect = card.getBoundingClientRect(), offX = e.clientX - rect.left, offY = e.clientY - rect.top;
    try { card.setPointerCapture(e.pointerId); } catch (_) {}

    function move(ev) {
      if (ev.pointerId !== e.pointerId) return;
      const dx = ev.clientX - sx, dy = ev.clientY - sy;
      if (!dragging && Math.hypot(dx, dy) < 8) return;
      if (!dragging) {
        dragging = true;
        if (document.activeElement && document.activeElement.blur) document.activeElement.blur();
        ghost = card.cloneNode(true); ghost.classList.add("ghost", "dragging");
        ghost.style.width = rect.width + "px"; ghost.style.height = rect.height + "px"; ghost.style.inset = "auto";
        document.body.appendChild(ghost); card.style.opacity = "0.12";
      }
      if (ev.cancelable) ev.preventDefault();
      const tilt = Math.max(-7, Math.min(7, dx / 16));
      ghost.style.left = (ev.clientX - offX) + "px"; ghost.style.top = (ev.clientY - offY) + "px";
      ghost.style.transform = "rotate(" + tilt + "deg)";
      highlight(ev.clientX, ev.clientY);
    }
    async function end(ev) {
      if (ev.pointerId !== e.pointerId) return;
      card.removeEventListener("pointermove", move);
      card.removeEventListener("pointerup", end);
      card.removeEventListener("pointercancel", end);
      try { card.releasePointerCapture(e.pointerId); } catch (_) {}
      clearHi();
      if (!dragging) { if (onTap) onTap(startTarget); return; }
      card.style.opacity = ""; if (ghost) ghost.remove();
      const box = boxAt(ev.clientX, ev.clientY);
      if (box) { await api.send("/api/transactions/" + tx.id + "/assign", "POST", { category_id: parseInt(box.dataset.id, 10) }); await refresh(); }
    }
    card.addEventListener("pointermove", move);
    card.addEventListener("pointerup", end);
    card.addEventListener("pointercancel", end);
  });
}
function boxAt(x, y) { const el = document.elementFromPoint(x, y); const c = el ? el.closest(".cat") : null; return (c && !c.classList.contains("add")) ? c : null; }
function highlight(x, y) { clearHi(); const b = boxAt(x, y); if (b) b.classList.add("on"); }
function clearHi() { document.querySelectorAll(".cat.on").forEach((b) => b.classList.remove("on")); }

// ---- category detail modal --------------------------------------------------

async function openCategory(catId, name, i) {
  const items = await api.get("/api/categories/" + catId + "/items");
  const total = items.reduce((a, b) => a + b.amount_cents, 0);
  $("#m-title").innerHTML = '<span class="dot" style="background:' + PALETTE[i % PALETTE.length] + '"></span>' + esc(name);
  $("#m-total").textContent = fmt(total);
  const list = $("#m-list"); list.innerHTML = "";
  if (!items.length) list.innerHTML = '<div class="m-empty">Noch keine Einträge — zieh eine Karte hierher.</div>';
  items.forEach((it) => {
    const row = document.createElement("div");
    row.className = "m-row";
    row.innerHTML =
      '<div class="p">' + esc(it.payee || "—") + '<div class="d">' + (it.occurred_on || "") + "</div></div>" +
      '<span class="a ' + (it.amount_cents > 0 ? "pos" : "") + '">' + fmt(it.amount_cents) + "</span>" +
      '<button class="back" title="Zurück in den Stapel">↩</button>';
    row.querySelector(".back").addEventListener("click", async () => {
      await api.send("/api/transactions/" + it.id + "/unassign", "POST");
      await refresh(); openCategory(catId, name, i);
    });
    list.appendChild(row);
  });
  $("#modal").hidden = false;
}
$("#m-close").addEventListener("click", () => { $("#modal").hidden = true; });
$("#modal").addEventListener("click", (e) => { if (e.target === $("#modal")) $("#modal").hidden = true; });

// ---- monthly analysis -------------------------------------------------------

async function openAnalysis() {
  const rep = await api.get("/api/analysis");
  const hl = $("#a-highlights");
  hl.innerHTML =
    '<div class="a-hl"><div class="k">Bester Monat</div><div class="v">' + (rep.best_month ? monthLabel(rep.best_month) : "—") + "</div></div>" +
    '<div class="a-hl"><div class="k">Höchste Ausgaben</div><div class="v">' + (rep.worst_expense_month ? monthLabel(rep.worst_expense_month) : "—") + "</div></div>";

  const list = $("#a-list"); list.innerHTML = "";
  if (!rep.months.length) { list.innerHTML = '<div class="m-empty">Noch keine Daten — sortiere erst ein paar Ausgaben.</div>'; }
  rep.months.forEach((m) => {
    const el = document.createElement("div");
    el.className = "month";
    const segs = m.categories.map((c) => {
      const pct = m.expense_cents ? (c.expense_cents / m.expense_cents * 100) : 0;
      const col = colorForName[c.name] || "#9aa0b5";
      return '<div class="seg" style="width:' + pct.toFixed(1) + "%;background:" + col + '"></div>';
    }).join("");
    const legend = m.categories.slice(0, 4).map((c) => {
      const col = colorForName[c.name] || "#9aa0b5";
      return '<span><span class="dot" style="background:' + col + '"></span>' + esc(c.name) + " " + fmt(c.expense_cents) + "</span>";
    }).join("");
    el.innerHTML =
      '<div class="top"><span class="mo">' + monthLabel(m.month) + "</span>" +
        '<span class="figures"><div class="exp">−' + fmt(m.expense_cents).replace("−", "") + "</div>" +
        (m.income_cents ? '<div class="inc">+' + fmt(m.income_cents) + "</div>" : "") + "</span></div>" +
      '<div class="barwrap">' + segs + "</div>" +
      '<div class="legend">' + legend + "</div>";
    list.appendChild(el);
  });
  $("#analysis").hidden = false;
}
$("#analysis-btn").addEventListener("click", openAnalysis);
$("#a-close").addEventListener("click", () => { $("#analysis").hidden = true; });
$("#analysis").addEventListener("click", (e) => { if (e.target === $("#analysis")) $("#analysis").hidden = true; });

// ---- balance + actions ------------------------------------------------------

$("#bal-edit").addEventListener("click", async () => {
  const input = prompt("Aktueller Kontostand (€):", (overview.balance_cents / 100).toFixed(2).replace(".", ","));
  if (input == null) return;
  await api.send("/api/balance", "PUT", { target_cents: toCents(input) });
  await refresh();
});
$("#blank").addEventListener("click", async () => { await api.send("/api/cards", "POST"); await refresh(); });
$("#file").addEventListener("change", async (e) => {
  const files = Array.prototype.slice.call(e.target.files);
  for (const f of files) {
    const fd = new FormData(); fd.append("file", f);
    await fetch("/api/upload", { method: "POST", body: fd });
  }
  e.target.value = ""; await refresh();
});

// ---- init -------------------------------------------------------------------

(async function init() {
  try { const st = await api.get("/api/status"); $("#ocr-hint").hidden = st.ocr_available; } catch (_) {}
  await refresh();
})();
