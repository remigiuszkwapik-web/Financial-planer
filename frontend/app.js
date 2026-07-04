// Financial Planer — local frontend. No AI, no external calls.
// Reads amount + payee off each card, you drag the card into a category box.

const api = {
  async get(url) { return (await fetch(url)).json(); },
  async send(url, method, body) {
    const r = await fetch(url, {
      method,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
    if (!r.ok) throw new Error(await r.text());
    return r.status === 204 ? null : r.json();
  },
};

const state = { cards: [], categories: [] };

function centsToStr(c) {
  const sign = c < 0 ? "-" : "";
  c = Math.abs(c);
  return `${sign}${Math.floor(c / 100)},${String(c % 100).padStart(2, "0")} €`;
}

function strToCents(s) {
  const cleaned = (s || "").replace(/[^\d.,-]/g, "");
  if (!cleaned) return 0;
  const neg = cleaned.trim().startsWith("-");
  const body = cleaned.replace("-", "");
  const lastDot = body.lastIndexOf(".");
  const lastComma = body.lastIndexOf(",");
  const dec = Math.max(lastDot, lastComma);
  let intPart, fracPart;
  if (dec === -1) { intPart = body; fracPart = ""; }
  else { intPart = body.slice(0, dec); fracPart = body.slice(dec + 1); }
  intPart = intPart.replace(/[^\d]/g, "") || "0";
  fracPart = (fracPart.replace(/[^\d]/g, "") + "00").slice(0, 2);
  const cents = parseInt(intPart, 10) * 100 + parseInt(fracPart || "0", 10);
  return neg ? -cents : cents;
}

// ---- rendering --------------------------------------------------------------

function renderCards() {
  const wrap = document.getElementById("cards");
  wrap.innerHTML = "";
  document.getElementById("cards-count").textContent = state.cards.length;
  document.getElementById("cards-empty").hidden = state.cards.length > 0;

  for (const tx of state.cards) {
    const card = document.createElement("div");
    card.className = "card";
    card.dataset.id = tx.id;

    const thumb = tx.image_path
      ? `<img class="thumb" src="/api/image/${tx.image_path}" alt="" />`
      : `<div class="thumb"></div>`;

    card.innerHTML = `
      ${thumb}
      <div class="info">
        <input class="amount" value="${centsToStr(tx.amount_cents).replace(" €", "")} €" inputmode="decimal" />
        <input class="payee" value="${(tx.payee || "").replace(/"/g, "&quot;")}" placeholder="Empfänger…" />
      </div>
      <button class="del" title="Löschen">🗑</button>`;

    const amountEl = card.querySelector(".amount");
    amountEl.addEventListener("blur", async () => {
      const cents = strToCents(amountEl.value);
      amountEl.value = centsToStr(cents).replace(" €", "") + " €";
      tx.amount_cents = cents;
      await api.send(`/api/transactions/${tx.id}`, "PATCH", { amount_cents: cents });
    });
    const payeeEl = card.querySelector(".payee");
    payeeEl.addEventListener("blur", async () => {
      tx.payee = payeeEl.value;
      await api.send(`/api/transactions/${tx.id}`, "PATCH", { payee: payeeEl.value });
    });
    card.querySelector(".del").addEventListener("click", async () => {
      await api.send(`/api/transactions/${tx.id}`, "DELETE");
      state.cards = state.cards.filter((c) => c.id !== tx.id);
      renderCards();
    });

    enableDrag(card, tx);
    wrap.appendChild(card);
  }
}

function renderCategories(summary) {
  const wrap = document.getElementById("categories");
  wrap.innerHTML = "";
  document.getElementById("categories-empty").hidden = state.categories.length > 0;
  const totals = {};
  if (summary) for (const c of summary.categories) totals[c.name] = c;

  for (const cat of state.categories) {
    const t = totals[cat.name] || { total_cents: 0, count: 0 };
    const box = document.createElement("div");
    box.className = "cat-box";
    box.dataset.id = cat.id;
    box.dataset.name = cat.name;
    box.innerHTML = `
      <button class="cat-del" title="Kategorie löschen">✕</button>
      <div class="cat-head">
        <span class="cat-name">${cat.name}</span>
        <span class="cat-total">${centsToStr(t.total_cents)}</span>
      </div>
      <div class="cat-meta">${t.count} Buchung(en) — Karten hier hineinziehen</div>`;
    box.querySelector(".cat-del").addEventListener("click", async () => {
      if (!confirm(`Kategorie "${cat.name}" löschen? Buchungen werden wieder unsortiert.`)) return;
      await api.send(`/api/categories/${cat.id}`, "DELETE");
      await refresh();
    });
    wrap.appendChild(box);
  }
}

function renderSummary(summary) {
  const el = document.getElementById("summary");
  const rows = [];
  for (const c of summary.categories) {
    rows.push(`<div class="sum-row"><span>${c.name} (${c.count})</span><span class="val">${centsToStr(c.total_cents)}</span></div>`);
  }
  if (summary.unsorted.count) {
    rows.push(`<div class="sum-row"><span>Unsortiert (${summary.unsorted.count})</span><span class="val">${centsToStr(summary.unsorted.total_cents)}</span></div>`);
  }
  rows.push(`<div class="sum-row total"><span>Gesamt</span><span class="val">${centsToStr(summary.grand_total_cents)}</span></div>`);
  el.innerHTML = `<div class="sum-grid">${rows.join("")}</div>`;
}

// ---- drag & drop (mouse + touch via pointer events) -------------------------

function enableDrag(card, tx) {
  let ghost = null, startX = 0, startY = 0, dragging = false;

  card.addEventListener("pointerdown", (e) => {
    // Don't start a drag when editing the text fields.
    if (e.target.closest("input, button")) return;
    startX = e.clientX; startY = e.clientY; dragging = false;
    card.setPointerCapture(e.pointerId);

    const move = (ev) => {
      const dx = ev.clientX - startX, dy = ev.clientY - startY;
      if (!dragging && Math.hypot(dx, dy) < 8) return;
      if (!dragging) {
        dragging = true;
        const rect = card.getBoundingClientRect();
        ghost = card.cloneNode(true);
        ghost.classList.add("dragging");
        ghost.style.width = rect.width + "px";
        document.body.appendChild(ghost);
        card.style.opacity = "0.3";
      }
      ghost.style.left = ev.clientX - 30 + "px";
      ghost.style.top = ev.clientY - 26 + "px";
      highlightTarget(ev.clientX, ev.clientY);
    };

    const up = async (ev) => {
      card.removeEventListener("pointermove", move);
      card.removeEventListener("pointerup", up);
      if (ghost) { ghost.remove(); ghost = null; }
      card.style.opacity = "";
      clearHighlights();
      if (!dragging) return;
      const box = boxAt(ev.clientX, ev.clientY);
      if (box) await assign(tx, parseInt(box.dataset.id, 10));
    };

    card.addEventListener("pointermove", move);
    card.addEventListener("pointerup", up);
  });
}

function boxAt(x, y) {
  const el = document.elementFromPoint(x, y);
  return el ? el.closest(".cat-box") : null;
}
function highlightTarget(x, y) {
  clearHighlights();
  const box = boxAt(x, y);
  if (box) box.classList.add("drop-target");
}
function clearHighlights() {
  document.querySelectorAll(".cat-box.drop-target").forEach((b) => b.classList.remove("drop-target"));
}

async function assign(tx, categoryId) {
  await api.send(`/api/transactions/${tx.id}`, "PATCH", {
    category_id: categoryId, set_category: true,
  });
  state.cards = state.cards.filter((c) => c.id !== tx.id);
  renderCards();
  await refreshSummary();
}

// ---- data flow --------------------------------------------------------------

async function refreshSummary() {
  const summary = await api.get("/api/summary");
  renderCategories(summary);
  renderSummary(summary);
}

async function refresh() {
  state.cards = await api.get("/api/cards");
  state.categories = await api.get("/api/categories");
  renderCards();
  await refreshSummary();
}

// ---- uploads ----------------------------------------------------------------

async function uploadFiles(files) {
  for (const file of files) {
    if (!file.type.startsWith("image/")) continue;
    const fd = new FormData();
    fd.append("file", file);
    const tx = await (await fetch("/api/upload", { method: "POST", body: fd })).json();
    state.cards.unshift(tx);
    renderCards();
  }
}

function initUpload() {
  const dz = document.getElementById("dropzone");
  const input = document.getElementById("file-input");
  input.addEventListener("change", () => uploadFiles(input.files).then(() => (input.value = "")));
  ["dragover", "dragenter"].forEach((ev) =>
    dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.add("drag"); }));
  ["dragleave", "drop"].forEach((ev) =>
    dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.remove("drag"); }));
  dz.addEventListener("drop", (e) => uploadFiles(e.dataTransfer.files));
}

function initCategoryForm() {
  const form = document.getElementById("add-category");
  const input = document.getElementById("category-name");
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const name = input.value.trim();
    if (!name) return;
    try {
      await api.send("/api/categories", "POST", { name });
      input.value = "";
      await refresh();
    } catch { alert("Kategorie existiert schon oder ist ungültig."); }
  });
}

async function init() {
  const status = await api.get("/api/status");
  document.getElementById("ocr-hint").hidden = status.ocr_available;
  initUpload();
  initCategoryForm();
  await refresh();
}

init();
