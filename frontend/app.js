"use strict";

const API = "/api";   // same origin: CloudFront routes /api/* to the Lambda, so no CORS is needed
const LOGO_URL = "assets/logo.svg";   // drop the official logo here; a wordmark is shown until then
const SESSION_KEY = "roomBooker.session";
const NEEDS_KEY = "roomBooker.needs";

const $ = (id) => document.getElementById(id);
const state = {
  rooms: [], slots: [], maxDaysAhead: 60, maxActive: { employee: 3, guest: 1 }, domain: "prudential.com",
  session: null,                 // { token, user: { name, email, kind, maxActive } }
  date: localISO(new Date()), day: [], upcoming: [], past: [], everyone: [], myTab: "upcoming",
  people: 4, needsAv: false, sheet: null,
};

// ---------- helpers ----------

function localISO(d) {
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}
function parseISO(iso) { const [y, m, d] = iso.split("-").map(Number); return new Date(y, m - 1, d); }
function shiftDate(iso, days) { const d = parseISO(iso); d.setDate(d.getDate() + days); return localISO(d); }
function fmt(iso, opts) { return parseISO(iso).toLocaleDateString(undefined, opts); }
function longDate(iso) { return fmt(iso, { weekday: "long", day: "numeric", month: "long" }); }
function shortDate(iso) { return fmt(iso, { weekday: "short", day: "numeric", month: "short" }); }
function dayLabel(iso) {
  const today = localISO(new Date());
  if (iso === today) return "Today";
  if (iso === shiftDate(today, 1)) return "Tomorrow";
  if (iso === shiftDate(today, -1)) return "Yesterday";
  return longDate(iso);
}
function endOf(slot) { return `${String(Number(slot.slice(0, 2)) + 1).padStart(2, "0")}:00`; }
function isPast(iso, slot) {
  const d = parseISO(iso); d.setHours(Number(slot.slice(0, 2)) + 1, 0, 0, 0);
  return d < new Date();
}
function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (k === "class") node.className = v;
    else if (k === "dataset") Object.assign(node.dataset, v);
    else if (k.startsWith("aria-") || k === "role") node.setAttribute(k, v);
    else node[k] = v;                    // textContent only - never innerHTML with user data
  }
  children.flat().forEach((c) => c != null && node.append(c));
  return node;
}
function initials(name) {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0].toUpperCase()).join("") || "?";
}
function people(n) { return `${n} ${n === 1 ? "person" : "people"}`; }
const store = {
  get(k) { try { return JSON.parse(localStorage.getItem(k)); } catch { return null; } },
  set(k, v) { try { v == null ? localStorage.removeItem(k) : localStorage.setItem(k, JSON.stringify(v)); } catch { /* ignore */ } },
};

let toastTimer;
function toast(msg) {
  const t = $("toast");
  t.textContent = msg;
  t.hidden = false;
  t.style.animation = "none"; void t.offsetWidth; t.style.animation = "";
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { t.hidden = true; }, 3200);
}

async function sha256Hex(text) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, "0")).join("");
}

class ApiError extends Error {
  constructor(status, message, code) { super(message); this.status = status; this.code = code; }
}

async function api(path, { method = "GET", body, auth = true } = {}) {
  const payload = body === undefined ? "" : JSON.stringify(body);
  const headers = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  // CloudFront signs API requests to Lambda (Origin Access Control); Lambda requires the
  // client to supply the payload hash for requests that can carry a body.
  if (method !== "GET") headers["x-amz-content-sha256"] = await sha256Hex(payload);
  if (auth && state.session) headers["X-Auth-Token"] = state.session.token;   // not Authorization: OAC uses it
  let res;
  try {
    res = await fetch(API + path, { method, headers, body: body === undefined ? undefined : payload });
  } catch {
    throw new ApiError(0, "Can't reach Room Booker. Check your connection.");
  }
  const data = await res.json().catch(() => ({}));
  if (res.status === 401 && auth) {
    signOut(false);
    toast("Your session ended. Please sign in again.");
  }
  if (!res.ok) throw new ApiError(res.status, data.error || `Request failed (${res.status})`, data.code);
  return data;
}

// ---------- brand ----------

function renderBrand() {
  const wordmark = () => [el("span", { class: "wordmark-badge", textContent: "P" }), el("span", { class: "wordmark", textContent: "Prudential" })];
  const slots = document.querySelectorAll("[data-brand]");
  slots.forEach((s) => s.replaceChildren(...wordmark()));
  const img = new Image();
  img.onload = () => slots.forEach((s) => s.replaceChildren(el("img", { src: LOGO_URL, alt: "Prudential" })));
  img.src = LOGO_URL;   // silently keeps the wordmark if the file isn't there
}

// ---------- welcome / sessions ----------

function showAuth() {
  $("appView").hidden = true;
  $("authView").hidden = false;
  setGuestMode(false);
}

function setGuestMode(on) {
  $("employeeForm").hidden = on;
  $("authDivider").hidden = on;
  $("guestToggle").hidden = on;
  $("guestForm").hidden = !on;
  $("authError").hidden = true;
  setTimeout(() => (on ? $("guestName") : $("emailInput")).focus(), 50);
}

function authError(msg) { $("authError").textContent = msg; $("authError").hidden = false; }

async function startSession(form, body) {
  const btn = form.querySelector("[type=submit]");
  btn.disabled = true;
  $("authError").hidden = true;
  try {
    const { token, user } = await api("/session", { method: "POST", body, auth: false });
    state.session = { token, user };
    store.set(SESSION_KEY, state.session);
    form.reset();
    enterApp();
    toast(user.kind === "guest" ? `Welcome, ${user.name}` : `Signed in as ${user.email}`);
  } catch (e) {
    authError(e.message.charAt(0).toUpperCase() + e.message.slice(1));
  } finally {
    btn.disabled = false;
  }
}

function signOut(showToast = true) {
  state.session = null;
  store.set(SESSION_KEY, null);
  showAuth();
  if (showToast) toast("Signed out");
}

function wireAuth() {
  const domainRe = () => new RegExp(`@${state.domain.replace(/\./g, "\\.")}$`, "i");
  $("employeeForm").addEventListener("submit", (ev) => {
    ev.preventDefault();
    const email = $("emailInput").value.trim();
    if (!domainRe().test(email)) return authError(`Please use your @${state.domain} email address.`);
    startSession(ev.target, { email });
  });
  $("guestToggle").addEventListener("click", () => setGuestMode(true));
  $("guestBack").addEventListener("click", () => setGuestMode(false));
  $("guestForm").addEventListener("submit", (ev) => {
    ev.preventDefault();
    const name = $("guestName").value.trim();
    if (!name) return authError("Please tell us your name.");
    startSession(ev.target, { guest: true, name });
  });
}

// ---------- app shell ----------

function enterApp() {
  const { user } = state.session;
  $("authView").hidden = true;
  $("appView").hidden = false;
  $("avatarBtn").textContent = initials(user.name);
  $("avatarBtn").setAttribute("aria-label", `Account: ${user.name}`);
  $("menuName").textContent = user.name;
  $("menuEmail").textContent = user.kind === "guest" ? "Guest on this device" : user.email;
  const h = new Date().getHours();
  const part = h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
  $("greeting").textContent = `${part}, ${user.name.split(" ")[0]}`;
  $("kindBadge").textContent = user.kind === "guest" ? "GUEST" : "";
  // After the last slot has ended, open on tomorrow instead of a day with nothing left to book.
  const today = localISO(new Date());
  state.date = state.slots.every((s) => isPast(today, s)) ? shiftDate(today, 1) : today;
  state.myTab = "upcoming";
  renderDayStrip();
  renderNeeds();
  refreshAll();
}

function wireShell() {
  const menu = $("accountMenu");
  $("avatarBtn").addEventListener("click", (ev) => {
    ev.stopPropagation();
    menu.hidden = !menu.hidden;
    $("avatarBtn").setAttribute("aria-expanded", String(!menu.hidden));
  });
  document.addEventListener("click", (ev) => { if (!menu.contains(ev.target)) menu.hidden = true; });
  document.addEventListener("keydown", (ev) => { if (ev.key === "Escape") menu.hidden = true; });
  $("signOutBtn").addEventListener("click", () => { menu.hidden = true; signOut(); });
  $("todayBtn").addEventListener("click", () => selectDay(localISO(new Date())));
  document.querySelectorAll("#myTabs [role=tab]").forEach((b) => b.addEventListener("click", () => {
    state.myTab = b.dataset.tab;
    renderMine();
  }));
}

// ---------- "who's coming?" filter ----------

function maxCapacity() { return Math.max(...state.rooms.map((r) => r.capacity)); }
function fits(room) { return room.capacity >= state.people && (!state.needsAv || room.av); }

function setPeople(n) {
  state.people = Math.min(Math.max(1, n), maxCapacity());
  saveNeeds();
  renderNeeds();
  renderRooms();
}
function saveNeeds() { store.set(NEEDS_KEY, { people: state.people, needsAv: state.needsAv }); }

function renderNeeds() {
  $("peopleCount").textContent = String(state.people);
  $("peopleMinus").disabled = state.people <= 1;
  $("peoplePlus").disabled = state.people >= maxCapacity();
  $("avToggle").checked = state.needsAv;
  const presets = [2, 4, 8, 12, 20, 40].filter((n) => n <= maxCapacity());
  $("quickPeople").replaceChildren(...presets.map((n) => {
    const b = el("button", { type: "button", textContent: String(n), "aria-pressed": String(n === state.people), "aria-label": people(n) });
    b.addEventListener("click", () => setPeople(n));
    return b;
  }));
  const count = state.rooms.filter(fits).length;
  $("matchText").textContent = count
    ? `${count} of ${state.rooms.length} rooms fit ${people(state.people)}${state.needsAv ? " with video/TV" : ""}.`
    : `No room fits ${people(state.people)}${state.needsAv ? " with video/TV" : ""}. Try fewer people.`;
}

function wireNeeds() {
  $("peopleMinus").addEventListener("click", () => setPeople(state.people - 1));
  $("peoplePlus").addEventListener("click", () => setPeople(state.people + 1));
  $("avToggle").addEventListener("change", (ev) => {
    state.needsAv = ev.target.checked;
    saveNeeds();
    renderNeeds();
    renderRooms();
  });
}

// ---------- data ----------

async function refreshAll() {
  await Promise.all([loadDay(), loadMine(), loadEveryone()]);
}

async function loadDay() {
  $("rooms").replaceChildren(...state.rooms.filter(fits).slice(0, 3).map(() => el("div", { class: "skeleton" })));
  try {
    state.day = (await api(`/bookings?date=${encodeURIComponent(state.date)}`)).bookings;
    renderRooms();
  } catch (e) { if (e.status !== 401) toast(e.message); }
}
async function loadMine() {
  try {
    const me = await api("/me");
    Object.assign(state, { upcoming: me.upcoming, past: me.past });
    state.session.user.maxActive = me.maxActive;
    renderMine();
  } catch (e) { if (e.status !== 401) toast(e.message); }
}
async function loadEveryone() {
  try {
    state.everyone = (await api("/bookings")).bookings;
    renderEveryone();
  } catch (e) { if (e.status !== 401) toast(e.message); }
}

// ---------- rendering ----------

function renderDayStrip() {
  const today = localISO(new Date());
  const days = Array.from({ length: state.maxDaysAhead + 1 }, (_, i) => shiftDate(today, i));   // whole booking window
  $("dayStrip").replaceChildren(...days.map((iso) => {
    const d = parseISO(iso);
    const btn = el("button", {
      type: "button", role: "option",
      class: "day" + (iso === today ? " today" : "") + (d.getDay() % 6 === 0 ? " weekend" : ""),
      "aria-selected": String(iso === state.date), "aria-label": longDate(iso), dataset: { date: iso },
    },
    el("span", { class: "dow", textContent: fmt(iso, { weekday: "short" }) }),
    el("span", { class: "num", textContent: String(d.getDate()) }),
    el("span", { class: "pip" }));
    btn.addEventListener("click", () => selectDay(iso));
    return btn;
  }));
  $("dayTitle").textContent = dayLabel(state.date);
}

function selectDay(iso) {
  state.date = iso;
  document.querySelectorAll(".day").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.date === iso)));
  document.querySelector(`.day[data-date="${iso}"]`)?.scrollIntoView({ behavior: "smooth", inline: "nearest", block: "nearest" });
  $("dayTitle").textContent = dayLabel(iso);
  loadDay();
}

// ---------- month calendar ----------

const cal = { year: 0, month: 0 };   // month currently shown in the calendar sheet

function monthKey(y, m) { return y * 12 + m; }
function calBounds() {
  const first = parseISO(localISO(new Date()));
  const last = parseISO(shiftDate(localISO(new Date()), state.maxDaysAhead));
  return { first, last, minKey: monthKey(first.getFullYear(), first.getMonth()), maxKey: monthKey(last.getFullYear(), last.getMonth()) };
}

function openCalendar() {
  const sel = parseISO(state.date);
  cal.year = sel.getFullYear();
  cal.month = sel.getMonth();
  $("calWindow").textContent = String(state.maxDaysAhead);
  renderCalendar();
  const sheet = $("calSheet");
  sheet.classList.remove("closing");
  sheet.showModal();
  $("calDays").querySelector('[aria-selected="true"]')?.focus({ preventScroll: true });
}

function closeCalendar() {
  const sheet = $("calSheet");
  if (!sheet.open) return;
  sheet.classList.add("closing");
  sheet.addEventListener("animationend", () => { sheet.classList.remove("closing"); sheet.close(); }, { once: true });
}

function renderCalendar() {
  const { first, last, minKey, maxKey } = calBounds();
  const key = monthKey(cal.year, cal.month);
  const start = new Date(cal.year, cal.month, 1);
  $("calTitle").textContent = start.toLocaleDateString(undefined, { month: "long", year: "numeric" });
  $("calPrev").disabled = key <= minKey;
  $("calNext").disabled = key >= maxKey;

  // Weekday header, Monday first (1 Jan 2024 was a Monday).
  $("calDow").replaceChildren(...Array.from({ length: 7 }, (_, i) =>
    el("span", { textContent: new Date(2024, 0, 1 + i).toLocaleDateString(undefined, { weekday: "narrow" }) })));

  const mine = new Set(state.upcoming.map((b) => b.date));
  const today = localISO(new Date());
  const lead = (start.getDay() + 6) % 7;                       // blanks before the 1st (Monday-first)
  const daysInMonth = new Date(cal.year, cal.month + 1, 0).getDate();
  const cells = Array.from({ length: lead }, () => el("span"));
  for (let d = 1; d <= daysInMonth; d++) {
    const date = new Date(cal.year, cal.month, d);
    const iso = localISO(date);
    const bookable = date >= first && date <= last;
    const btn = el("button", {
      type: "button", role: "gridcell",
      class: "cal-day" + (iso === today ? " today" : "") + (date.getDay() % 6 === 0 ? " weekend" : ""),
      textContent: String(d), disabled: !bookable,
      "aria-selected": String(iso === state.date),
      "aria-label": longDate(iso) + (mine.has(iso) ? ", you have a booking" : "") + (bookable ? "" : ", not bookable"),
    });
    if (mine.has(iso)) btn.append(el("span", { class: "cal-dot" }));
    btn.addEventListener("click", () => { selectDay(iso); closeCalendar(); });
    cells.push(btn);
  }
  $("calDays").replaceChildren(...cells);
}

function shiftMonth(delta) {
  const d = new Date(cal.year, cal.month + delta, 1);
  cal.year = d.getFullYear();
  cal.month = d.getMonth();
  renderCalendar();
}

function wireCalendar() {
  $("calBtn").addEventListener("click", openCalendar);
  $("calClose").addEventListener("click", closeCalendar);
  $("calPrev").addEventListener("click", () => shiftMonth(-1));
  $("calNext").addEventListener("click", () => shiftMonth(1));
  const sheet = $("calSheet");
  sheet.addEventListener("cancel", (ev) => { ev.preventDefault(); closeCalendar(); });
  sheet.addEventListener("click", (ev) => { if (ev.target === sheet) closeCalendar(); });
}

function renderRooms() {
  const byKey = new Map(state.day.map((b) => [`${b.room}|${b.slot}`, b]));
  // Best fit first: the smallest room that seats everyone (keeps big rooms free for big groups).
  const shown = state.rooms.filter(fits).sort((a, b) => a.capacity - b.capacity);
  const hidden = state.rooms.length - shown.length;
  const allPast = state.slots.every((s) => isPast(state.date, s));
  const cards = shown.map((room, i) => {
    const freeCount = state.slots.filter((s) => !byKey.has(`${room.name}|${s}`) && !isPast(state.date, s)).length;
    const slots = state.slots.map((slot) => {
      const b = byKey.get(`${room.name}|${slot}`);
      const past = isPast(state.date, slot);
      const cls = b ? (b.mine ? "mine" : "taken") : "free";
      const label = b
        ? `${room.name} ${slot}: ${b.mine ? "your booking" : `booked by ${b.name}`} — ${b.title}`
        : `Book ${room.name} at ${slot}`;
      const btn = el("button", { type: "button", class: `slot ${cls}${past && !b ? " past" : ""}`, textContent: slot.slice(0, 2), title: label, "aria-label": label });
      btn.addEventListener("click", () => openSheet({ room, slot, booking: b }));
      return btn;
    });
    return el("article", { class: "card room" },
      el("div", { class: "room-head" },
        el("div", {},
          el("h3", { class: "room-name", textContent: room.name }),
          el("p", { class: "room-meta", textContent: `${room.floor} · seats ${room.capacity}` })),
        el("div", { class: "room-badges" },
          i === 0 ? el("span", { class: "best-fit", textContent: "Best fit" }) : null,
          el("span", {
            class: "room-free" + (freeCount ? "" : " none"),
            textContent: freeCount ? `${freeCount} free` : allPast ? "Closed" : "Full",
          }))),
      el("div", { class: "chips" }, room.features.map((f) => el("span", { class: "chip", textContent: f }))),
      el("div", { class: "slots" }, slots));
  });
  $("rooms").replaceChildren(...(cards.length ? cards
    : [el("div", { class: "card no-rooms", textContent: `No room seats ${people(state.people)}${state.needsAv ? " with video/TV" : ""}.` })]));
  $("hiddenNote").hidden = !hidden || !cards.length;
  $("hiddenNote").textContent = `${hidden} room${hidden === 1 ? " is" : "s are"} hidden because ${hidden === 1 ? "it's" : "they're"} too small${state.needsAv ? " or ha" + (hidden === 1 ? "s" : "ve") + " no video/TV" : ""}.`;
}

function renderMine() {
  const max = state.session.user.maxActive;
  const used = state.upcoming.length;
  const C = 2 * Math.PI * 18;
  $("ringFill").style.strokeDashoffset = String(C * (1 - Math.min(used / Math.max(max, 1), 1)));
  $("ringLabel").textContent = `${used}/${max}`;
  const guest = state.session.user.kind === "guest";
  $("quotaText").textContent = used >= max
    ? (guest ? `Guests can hold ${max} booking. Sign in with your @${state.domain} email for up to ${state.maxActive.employee}.`
             : `You've reached your limit of ${max}. Cancel one to book another.`)
    : `${max - used} of ${max} booking${max === 1 ? "" : "s"} left${guest ? " (guest)" : ""}.`;
  $("myTabs").dataset.active = state.myTab;
  document.querySelectorAll("#myTabs [role=tab]").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.tab === state.myTab)));
  const list = state.myTab === "upcoming" ? state.upcoming : state.past;
  if (!list.length) {
    $("myList").replaceChildren(el("li", { class: "empty-mini", textContent: state.myTab === "upcoming"
      ? "No upcoming bookings. Pick a free hour below." : "No bookings in the last 30 days." }));
    return;
  }
  $("myList").replaceChildren(...list.map((b) => {
    const room = state.rooms.find((r) => r.name === b.room);
    const btn = el("button", { type: "button", class: "chev" },
      el("span", { class: "dot" }),
      el("span", { class: "what", textContent: `${b.title} · ${b.room}` }),
      el("span", { class: "when", textContent: `${shortDate(b.date)}, ${b.slot}${b.attendees ? ` · ${b.attendees}p` : ""}` }));
    btn.addEventListener("click", () => openSheet({ room, slot: b.slot, booking: b, date: b.date }));
    return el("li", { class: state.myTab === "past" ? "past-item" : "" }, btn);
  }));
}

function renderEveryone() {
  const list = $("everyoneList");
  if (!state.everyone.length) {
    list.replaceChildren(el("div", { class: "empty", textContent: "No upcoming bookings yet. Be the first!" }));
    return;
  }
  const groups = new Map();
  state.everyone.forEach((b) => { if (!groups.has(b.date)) groups.set(b.date, []); groups.get(b.date).push(b); });
  const nodes = [];
  for (const [date, items] of groups) {
    nodes.push(el("div", { class: "group-label", textContent: dayLabel(date) }));
    items.forEach((b) => nodes.push(el("div", { class: "row" },
      el("span", { class: "time", textContent: b.slot }),
      el("span", { class: "room-tag", textContent: b.room }),
      el("span", { class: "title", textContent: b.title }),
      el("span", { class: b.mine ? "by you" : "by", textContent: b.mine ? "You" : b.name + (b.guest ? " (guest)" : "") }))));
  }
  list.replaceChildren(...nodes);
}

// ---------- sheet (book / manage / view) ----------

function openSheet({ room, slot, booking, date = state.date }) {
  const past = isPast(date, slot);
  const mode = !booking ? "create" : booking.mine && !past ? "manage" : "view";
  state.sheet = { room, slot, booking, date, mode };
  $("sheetTitle").textContent = room.name;
  $("sheetWhen").textContent = `${longDate(date)} · ${slot} – ${endOf(slot)}`;
  $("sheetRoom").replaceChildren(
    el("span", { class: "chip", textContent: room.floor }),
    el("span", { class: "chip", textContent: `Seats ${room.capacity}` }),
    ...room.features.map((f) => el("span", { class: "chip", textContent: f })));
  $("sheetEditable").hidden = mode === "view";
  $("sheetReadonly").hidden = mode !== "view";
  $("sheetError").hidden = true;
  $("sheetCancel").hidden = mode !== "manage";
  if (mode === "view") {
    $("roTitle").textContent = booking.title;
    $("roName").textContent = booking.mine ? "You" : booking.name + (booking.guest ? " (guest)" : "");
    $("roPeople").textContent = booking.attendees ? people(booking.attendees) : "—";
  } else {
    $("titleInput").value = booking ? booking.title : "";
    $("sheetPeople").textContent = mode === "create"
      ? `${people(state.people)}${state.needsAv ? " · Video/TV" : ""}`
      : (booking.attendees ? people(booking.attendees) : "—");
    $("sheetSubmit").textContent = mode === "create" ? "Book" : "Save changes";
    const { maxActive } = state.session.user;
    const used = state.upcoming.length;
    $("sheetHint").textContent = mode === "create"
      ? (used >= maxActive ? `You already hold ${maxActive} upcoming booking${maxActive === 1 ? "" : "s"}. Cancel one first.`
                           : `This will be booking ${used + 1} of ${maxActive}.`)
      : "Only you can change or cancel this booking.";
    $("sheetSubmit").disabled = mode === "create" && used >= maxActive;
  }
  resetCancelButton();
  const sheet = $("sheet");
  sheet.classList.remove("closing");
  sheet.showModal();
  if (mode !== "view") setTimeout(() => $("titleInput").focus(), 300);
}

function closeSheet() {
  const sheet = $("sheet");
  if (!sheet.open) return;
  sheet.classList.add("closing");
  sheet.addEventListener("animationend", () => { sheet.classList.remove("closing"); sheet.close(); }, { once: true });
}

function sheetError(msg) { $("sheetError").textContent = msg; $("sheetError").hidden = false; }

function resetCancelButton() {
  const b = $("sheetCancel");
  b.dataset.confirm = "";
  b.textContent = "Cancel booking";
  b.disabled = false;
}

function wireSheet() {
  const sheet = $("sheet");
  sheet.querySelectorAll("[data-close]").forEach((b) => b.addEventListener("click", closeSheet));
  sheet.addEventListener("cancel", (ev) => { ev.preventDefault(); closeSheet(); });     // Esc key
  sheet.addEventListener("click", (ev) => { if (ev.target === sheet) closeSheet(); });  // tap backdrop

  $("sheetForm").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const s = state.sheet;
    const title = $("titleInput").value.trim();
    if (!title) return sheetError("Give the meeting a name.");
    const btn = $("sheetSubmit");
    btn.disabled = true;
    try {
      if (s.mode === "create") {
        await api("/bookings", { method: "POST", body: {
          date: s.date, room: s.room.name, slot: s.slot, title, attendees: state.people, needsAv: state.needsAv,
        } });
        toast(`${s.room.name} booked · ${shortDate(s.date)}, ${s.slot}`);
      } else {
        await api(`/bookings/${s.booking.date}/${s.booking.room}/${s.booking.slot}`, { method: "PATCH", body: { title } });
        toast("Booking updated");
      }
      closeSheet();
      refreshAll();
    } catch (e) {
      sheetError(e.message.charAt(0).toUpperCase() + e.message.slice(1));
      if (e.code === "taken") loadDay();
    } finally {
      btn.disabled = false;
    }
  });

  $("sheetCancel").addEventListener("click", async () => {
    const b = $("sheetCancel");
    if (b.dataset.confirm !== "1") {                 // two-tap confirm, like iOS destructive actions
      b.dataset.confirm = "1";
      b.textContent = "Tap again to cancel booking";
      return;
    }
    const s = state.sheet;
    b.disabled = true;
    try {
      await api(`/bookings/${s.booking.date}/${s.booking.room}/${s.booking.slot}`, { method: "DELETE" });
      toast("Booking cancelled");
      closeSheet();
      refreshAll();
    } catch (e) {
      sheetError(e.message);
      resetCancelButton();
    }
  });
}

// ---------- init ----------

async function init() {
  renderBrand();
  wireAuth();
  wireShell();
  wireNeeds();
  wireSheet();
  wireCalendar();
  let cfg;
  try {
    cfg = await api("/config", { auth: false });
  } catch (e) {
    showAuth();
    authError(e.message);
    return;
  }
  Object.assign(state, { rooms: cfg.rooms, slots: cfg.slots, maxDaysAhead: cfg.maxDaysAhead,
                         maxActive: cfg.maxActive, domain: cfg.employeeDomain });
  $("emailInput").placeholder = `name@${state.domain}`;
  $("emailHint").textContent = `Use your @${state.domain} email. No password needed.`;
  const needs = store.get(NEEDS_KEY);
  if (needs) Object.assign(state, { people: Math.min(Math.max(1, Number(needs.people) || 4), maxCapacity()), needsAv: !!needs.needsAv });

  const saved = store.get(SESSION_KEY);
  if (saved && saved.token) {
    state.session = saved;
    enterApp();             // a 401 from any call signs out and returns to the welcome screen
  } else {
    showAuth();
  }
}

init();
