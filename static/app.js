"use strict";

const $ = (s) => document.querySelector(s);
const view = $("#view");
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const DAYS = ["niedziela", "poniedziałek", "wtorek", "środa", "czwartek", "piątek", "sobota"];
const DAYS_SHORT = ["nd", "pn", "wt", "śr", "cz", "pt", "sb"];

function store(k, v) { try { if (v === undefined) return localStorage.getItem(k); localStorage.setItem(k, v); } catch { return null; } }

let kids = [];
let hasParent = false;
let kid = Number(store("kid")) || null;
let tab = store("tab") || "today";

function dayLabel(iso) {
  const d = new Date(iso + "T12:00:00");
  const t = new Date(); t.setHours(12, 0, 0, 0);
  const diff = Math.round((d - t) / 864e5);
  if (diff === 0) return "Dziś";
  if (diff === 1) return "Jutro";
  return DAYS[d.getDay()].replace(/^./, (c) => c.toUpperCase()) + ", " + d.getDate() + "." + String(d.getMonth() + 1).padStart(2, "0");
}
function dateBox(iso) {
  const d = new Date(iso + "T12:00:00");
  return `<div class="date-box"><b>${d.getDate()}</b><span>${DAYS_SHORT[d.getDay()]}</span></div>`;
}

// ---------- wersja statyczna (GitHub Pages): zaszyfrowane pliki data/<n>.json ----------
const STATIC = window.DZ_STATIC === true;
const bundles = {};
const b64d = (s) => Uint8Array.from(atob(s), (c) => c.charCodeAt(0));
const b64e = (u) => btoa(String.fromCharCode(...new Uint8Array(u)));

async function deriveKey(password, salt, iter) {
  const base = await crypto.subtle.importKey("raw", new TextEncoder().encode(password), "PBKDF2", false, ["deriveBits"]);
  return crypto.subtle.deriveBits({ name: "PBKDF2", hash: "SHA-256", salt, iterations: iter }, base, 256);
}
async function decryptWith(rawKey, box) {
  const key = await crypto.subtle.importKey("raw", rawKey, "AES-GCM", false, ["decrypt"]);
  const plain = await crypto.subtle.decrypt({ name: "AES-GCM", iv: b64d(box.iv) }, key, b64d(box.ct));
  return JSON.parse(new TextDecoder().decode(plain));
}
async function fetchBox(n) {
  const r = await fetch(`data/${n}.json?t=${Date.now()}`, { cache: "no-store" });
  if (!r.ok) throw { msg: "Nie udało się pobrać danych." };
  return r.json();
}
let parentBox = null;
async function loadBundle(n, refresh) {
  if (bundles[n] && !refresh) return bundles[n];
  const raw = store(`key${n}`);
  if (raw) {
    const box = await fetchBox(n);
    try { bundles[n] = await decryptWith(b64d(raw), box); return bundles[n]; }
    catch { try { localStorage.removeItem(`key${n}`); } catch {} }
  }
  const praw = store("key0"); // tryb rodzica: jeden plik z całą trójką
  if (praw) {
    try {
      if (!parentBox || refresh) parentBox = await decryptWith(b64d(praw), await fetchBox(0));
      const d = parentBox.kids[String(n)];
      if (d) { bundles[n] = d; return d; }
    } catch { try { localStorage.removeItem("key0"); } catch {} }
  }
  throw { pin: true };
}
async function staticApi(path, refresh) {
  const [n, tab, id] = path.split("/");
  const b = await loadBundle(Number(n), refresh);
  if (tab === "messages" && id) {
    const m = (b.messages?.messages || []).find((x) => x.id === decodeURIComponent(id));
    if (!m) throw { msg: "Nie ma takiej wiadomości." };
    return { ...m, content: m.body || m.preview, attachments: [], partial: true };
  }
  const d = b[tab];
  if (!d) throw { msg: "Tej części nie udało się pobrać z Librusa przy ostatniej aktualizacji." };
  return { ...d, updated: b.generated };
}
async function staticUnlock(n, password) {
  const box = await fetchBox(n);
  const raw = await deriveKey(password, b64d(box.salt), box.iter);
  const data = await decryptWith(raw, box); // rzuci błąd przy złym haśle
  if (n === 0) parentBox = data; else bundles[n] = data;
  store(`key${n}`, b64e(raw)); // zapamiętujemy klucz, nie hasło
}

async function api(path, refresh) {
  if (STATIC) return staticApi(path, refresh);
  const r = await fetch(`api/${path}${refresh ? "?refresh=1" : ""}`, { credentials: "same-origin" });
  if (r.status === 401) throw { pin: true };
  if (!r.ok) {
    let msg = "Coś poszło nie tak.";
    try { msg = (await r.json()).detail || msg; } catch {}
    throw { msg };
  }
  return r.json();
}

function loading() { view.innerHTML = '<div class="skeleton"></div>'.repeat(4); }
function errorCard(msg) { return `<div class="card error">${esc(msg)}</div>`; }
function footer(data) {
  if (!data.updated) return "";
  return `<p class="meta">${STATIC ? "Dane z Librusa z" : "Pobrano o"} ${esc(data.updated)}${data.stale ? " · Librus nie odpowiada, to ostatnie zapisane dane" : ""}</p>`;
}

// ---------- ekrany ----------

function renderToday(d) {
  let h = "";
  if (!d.days.length) h += `<div class="card empty">Brak lekcji w najbliższych dniach 🎉</div>`;
  for (const day of d.days) {
    h += `<h2>${esc(dayLabel(day.date))}</h2><div class="card">`;
    for (const l of day.lessons) {
      const tags = (l.canceled ? '<span class="tag cancel">odwołana</span>' : "") +
        (l.substitution ? '<span class="tag subst">zastępstwo</span>' : "");
      const extra = [l.room && (/^sala/i.test(l.room) ? l.room : `sala ${l.room}`), l.teacher, l.original && l.original !== l.subject && `zamiast: ${l.original}`]
        .filter(Boolean).map(esc).join(" · ");
      h += `<div class="lesson${l.canceled ? " canceled" : ""}">
        <div class="no">${l.no ?? ""}</div>
        <div><div class="subj">${esc(l.subject)}${tags}</div><div class="small muted">${extra}</div></div>
        <div class="time">${esc(l.from || "")}<br>${esc(l.to || "")}</div></div>`;
    }
    h += `</div>`;
  }
  if (d.soon.length) {
    h += `<h2>W tym tygodniu</h2>`;
    for (const e of d.soon) h += eventCard(e);
  }
  return h + footer(d);
}

function eventCard(e) {
  return `<div class="card event">${dateBox(e.date)}<div>
    <div class="cat">${esc(e.category)}${e.time ? " · " + esc(e.time) : ""}</div>
    ${e.subject ? `<b>${esc(e.subject)}</b>` : ""}<div class="small">${esc(e.content)}</div></div></div>`;
}

function gradeClass(g) {
  const v = parseFloat(String(g.value).replace(",", "."));
  let c = "g";
  if (!isNaN(v)) c += v >= 5 ? " hi" : v < 2 ? " lo" : "";
  if (g.kind === "final" || g.kind === "semester") c += " final";
  if (g.kind === "proposal") c += " proposal";
  return c;
}

let gradesData = null;
function renderGrades(d) {
  gradesData = d;
  if (!d.subjects.length) return `<div class="card empty">Jeszcze nie ma ocen.</div>` + footer(d);
  let h = "";
  if (d.newest.length) {
    h += `<h2>Ostatnie oceny</h2><div class="card">`;
    for (const g of d.newest) {
      h += `<div class="lesson"><div><span class="${gradeClass(g)}">${esc(g.value)}</span></div>
        <div><div class="subj">${esc(g.subject)}</div><div class="small muted">${esc(g.category)}</div></div>
        <div class="time">${esc(g.date ? dayLabel(g.date) : "")}</div></div>`;
    }
    h += `</div>`;
  }
  h += `<h2>Wszystkie przedmioty</h2>`;
  d.subjects.forEach((s, i) => {
    const sems = Object.keys(s.average).sort();
    const avg = sems.length ? "śr. " + s.average[sems[sems.length - 1]].toFixed(2) : "";
    h += `<div class="card subject" data-i="${i}"><div class="subject-head"><b>${esc(s.subject)}</b><span class="avg">${avg}</span></div>
      <div class="grades">${s.grades.slice(0, 18).map((g) => `<span class="${gradeClass(g)}">${esc(g.value)}</span>`).join("")}</div></div>`;
  });
  return h + footer(d);
}

function subjectSheet(i) {
  const s = gradesData.subjects[i];
  let h = `<h3 style="margin-top:0">${esc(s.subject)}</h3>`;
  for (const [sem, a] of Object.entries(s.average)) h += `<p class="muted small">Średnia ważona${sem !== "0" ? `, semestr ${esc(sem)}` : ""}: <b>${a.toFixed(2)}</b></p>`;
  for (const g of s.grades) {
    h += `<div class="lesson"><div><span class="${gradeClass(g)}">${esc(g.value)}</span></div>
      <div><div>${esc(g.category || "Ocena")}${g.weight ? ` <span class="muted small">waga ${esc(g.weight)}</span>` : ""}</div>
      ${g.comments.length ? `<div class="small muted">${g.comments.map(esc).join("<br>")}</div>` : ""}</div>
      <div class="time">${esc(g.date || "")}</div></div>`;
  }
  openSheet(h);
}

function renderAgenda(d) {
  let h = `<h2>Sprawdziany i wydarzenia</h2>`;
  h += d.events.length ? d.events.map(eventCard).join("") : `<div class="card empty">Nic zaplanowanego.</div>`;
  h += `<h2>Zadania domowe</h2>`;
  if (!d.homework.length) h += `<div class="card empty">Brak zadań.</div>`;
  for (const w of d.homework) {
    h += `<div class="card event">${dateBox(w.due || w.date)}<div>
      <div class="cat">na ${esc(dayLabel(w.due || w.date))}${w.attachments ? " · 📎" : ""}</div>
      <b>${esc(w.topic)}</b><div class="small content">${esc(w.text)}</div></div></div>`;
  }
  return h + footer(d);
}

let msgData = null;
function renderMessages(d) {
  msgData = d;
  let h = `<h2>Wiadomości</h2>`;
  if (!d.messages.length) h += `<div class="card empty">Brak wiadomości.</div>`;
  for (const m of d.messages) {
    h += `<div class="card msg${m.unread ? " unread" : ""}" data-id="${esc(m.id)}">
      <div class="row"><span>${esc(m.sender)}${m.important ? '<span class="tag imp">wychowawca</span>' : ""}</span><span>${esc((m.date || "").slice(0, 10))}</span></div>
      <div class="topic">${m.attachment ? "📎 " : ""}${esc(m.topic)}</div>
      <div class="small muted">${esc(m.preview)}</div></div>`;
  }
  if (d.notices.length) {
    h += `<h2>Ogłoszenia szkoły</h2>`;
    d.notices.forEach((a, i) => {
      h += `<div class="card msg notice" data-n="${i}"><div class="row"><span>${esc((a.date || "").slice(0, 10))}</span></div>
        <div class="topic"><b>${esc(a.subject)}</b></div><div class="small muted">${esc(a.content.slice(0, 140))}</div></div>`;
    });
  }
  return h + footer(d);
}

async function openMessage(id) {
  openSheet('<div class="skeleton"></div>');
  try {
    const m = await api(`${kid}/messages/${encodeURIComponent(id)}`);
    openSheet(`<p class="muted small">${esc(m.sender)} · ${esc((m.date || "").slice(0, 16))}</p>
      <h3 style="margin-top:0">${esc(m.topic)}</h3><div class="content">${esc(m.content)}</div>
      ${m.partial ? '<p class="small muted">To skrócona treść. Całą wiadomość i załączniki zobaczysz w Librusie.</p>' : ""}
      ${m.attachments.length ? `<p class="small muted">📎 ${m.attachments.map(esc).join(", ")} (otwórz w Librusie)</p>` : ""}`);
    const item = msgData && msgData.messages.find((x) => x.id === id);
    if (item) item.unread = false;
  } catch (e) { openSheet(errorCard(e.msg || "Nie udało się otworzyć.")); }
}

function openSheet(html) {
  $("#sheet-body").innerHTML = html;
  const s = $("#sheet");
  if (!s.open) s.showModal();
}

// ---------- PIN ----------

function renderPin(child) {
  const what = STATIC ? "hasło" : "PIN";
  const input = STATIC
    ? '<input id="pini" type="password" autocomplete="current-password" aria-label="Hasło" style="letter-spacing:normal;font-size:20px;width:260px">'
    : '<input id="pini" inputmode="numeric" autocomplete="off" maxlength="8" aria-label="PIN">';
  view.innerHTML = `<div class="pin"><p>Cześć, <b>${esc(child.name)}</b>! Podaj ${what}.</p>
    <form id="pinf">${input}<br>
    <button class="btn">Wejdź</button><p id="pinerr" class="small" style="color:var(--warn)"></p>
    ${STATIC ? '<p class="small muted">Telefon zapamięta je, wpisujesz tylko raz.</p>' : ""}
    ${STATIC && hasParent && !child.parent ? '<button type="button" id="asparent" class="kid" style="margin-top:18px">Jestem rodzicem</button>' : ""}</form></div>`;
  const ap = $("#asparent");
  if (ap) ap.onclick = () => renderPin({ n: 0, name: "rodzicu", parent: true, back: child });
  $("#pini").focus();
  $("#pinf").onsubmit = async (ev) => {
    ev.preventDefault();
    const btn = $("#pinf .btn"); btn.disabled = true;
    try {
      if (STATIC) {
        try {
          await staticUnlock(child.n, $("#pini").value);
          if (child.parent) kids.forEach((k) => (k.locked = false)); else child.locked = false;
          show();
        }
        catch { $("#pinerr").textContent = "Złe hasło."; $("#pini").value = ""; }
        return;
      }
      const r = await fetch(`api/${child.n}/unlock`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ pin: $("#pini").value }) });
      if (r.ok) { child.locked = false; show(); }
      else { let m = "Zły PIN."; try { m = (await r.json()).detail; } catch {} $("#pinerr").textContent = m; $("#pini").value = ""; }
    } finally { btn.disabled = false; }
  };
}

// ---------- nawigacja ----------

const RENDER = { today: renderToday, grades: renderGrades, agenda: renderAgenda, messages: renderMessages };
let seq = 0;

async function show(refresh = false) {
  const child = kids.find((k) => k.n === kid);
  if (!child) { view.innerHTML = `<div class="card empty">Brak skonfigurowanych kont.</div>`; return; }
  if (child.locked) return renderPin(child);
  const my = ++seq;
  if (!refresh) loading();
  $("#refresh").classList.add("spin");
  try {
    const data = await api(`${kid}/${tab}`, refresh);
    if (my === seq) view.innerHTML = RENDER[tab](data);
  } catch (e) {
    if (my !== seq) return;
    if (e.pin) { child.locked = true; return renderPin(child); }
    view.innerHTML = errorCard(e.msg || "Brak połączenia z serwerem.");
  } finally {
    if (my === seq) $("#refresh").classList.remove("spin");
  }
}

function drawKids() {
  $("#kids").innerHTML = kids.map((k) => `<button class="kid${k.n === kid ? " on" : ""}" data-n="${k.n}">${esc(k.name)}</button>`).join("");
}

$("#kids").onclick = (e) => {
  const b = e.target.closest(".kid"); if (!b) return;
  kid = Number(b.dataset.n); store("kid", String(kid)); drawKids(); show();
};
document.querySelector(".tabs").onclick = (e) => {
  const b = e.target.closest("button"); if (!b) return;
  tab = b.dataset.tab; store("tab", tab);
  document.querySelectorAll(".tabs button").forEach((x) => x.classList.toggle("on", x === b));
  window.scrollTo(0, 0); show();
};
$("#refresh").onclick = () => show(true);
view.onclick = (e) => {
  const s = e.target.closest(".subject"); if (s) return subjectSheet(Number(s.dataset.i));
  const n = e.target.closest(".notice");
  if (n) { const a = msgData.notices[Number(n.dataset.n)]; return openSheet(`<h3 style="margin-top:0">${esc(a.subject)}</h3><div class="content">${esc(a.content)}</div>`); }
  const m = e.target.closest(".msg[data-id]"); if (m) return openMessage(m.dataset.id);
};

(async function init() {
  document.querySelectorAll(".tabs button").forEach((x) => x.classList.toggle("on", x.dataset.tab === tab));
  try {
    if (STATIC) {
      const k = await (await fetch(`data/kids.json?t=${Date.now()}`, { cache: "no-store" })).json();
      hasParent = !!k.parent;
      kids = k.kids.map((x) => ({ ...x, locked: !store(`key${x.n}`) && !store("key0") }));
    } else kids = await (await fetch("api/children")).json();
  } catch { view.innerHTML = errorCard("Brak połączenia z serwerem."); return; }
  if (!kids.some((k) => k.n === kid)) kid = kids[0]?.n ?? null;
  drawKids();
  show();
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => {});
})();
