// app.js — "The Butcher Remembers" canvas client.
// Created: 2026-07-02 (experiment/npc-soul-grudge-kernel) — vanilla JS renderer
// over the GameWorld event stream: polls /events?since=N every ~700ms, draws
// the tavern zones (stall / tables / door) with souls as labeled circles,
// floats fading speech bubbles on speech/beat events, and keeps the grudge
// HUD (level chip, bond, last grievance) + director phase chip in sync.
// No frameworks, no assets, no build step.
// Updated: 2026-07-02 (BD-2, 90s demo) — bottom free-play bar: Send posts
// /line WITHOUT a kind (the server's keyword classifier decides, echoed in
// #free-status); Export bjorn.soul / ragnar.player.soul download the real
// .soul files (Content-Disposition); Import soul posts raw bytes to
// /import_soul and re-seeds from the returned snapshot; "Ask the innkeeper"
// hits /reputation and floats Astrid's line as a long-lived amber SPECIAL
// bubble + notoriety chip. Cost overlay (top-right, collapsible) polls /cost
// after each send; hidden while /snapshot reports engine === "templated".

"use strict";

const canvas = document.getElementById("tavern");
const ctx = canvas.getContext("2d");

// Zone geometry is CLIENT-side; the world only speaks zone labels.
const ZONES = {
  stall: { x: 28, y: 64, w: 200, h: 168, label: "Bjorn's stall" },
  tables: { x: 258, y: 168, w: 214, h: 180, label: "tables" },
  door: { x: 498, y: 296, w: 118, h: 126, label: "door" },
  tavern: { x: 258, y: 64, w: 214, h: 76, label: "tavern" }, // fallback / lobby
};

const SOUL_COLORS = { Bjorn: "#c1653f", Astrid: "#5f9e8f", Ragnar: "#7292c4" };
const FALLBACK_COLORS = ["#a07ac0", "#b3a24c", "#c47292"];
const BUBBLE_MS = 4200; // how long a speech bubble lives
const SPECIAL_BUBBLE_MS = 9000; // the reputation gut-punch line lingers

const state = {
  souls: new Map(), // name -> {kind:'npc'|'player', zone, color}
  cards: new Map(), // npc name -> {level, bond, lastGrievance, flashUntil}
  bubbles: [], // {name, text, born, fromPlayer, special}
  phase: "BUILD_UP",
  cost: null,
  cursor: 0,
  engine: "templated", // from /snapshot — gates the cost overlay
};

// ---------------------------------------------------------------------------
// Bootstrap + polling
// ---------------------------------------------------------------------------

async function boot() {
  await seedFromSnapshot();
  setInterval(poll, 700);
  requestAnimationFrame(draw);
}

async function seedFromSnapshot() {
  const snap = await fetch("/snapshot").then((r) => r.json());
  state.souls.clear();
  state.cards.clear();
  snap.npcs.forEach((npc) => {
    ensureSoul(npc.name, "npc", npc.zone);
    const first = Object.values(npc.players)[0] || {};
    state.cards.set(npc.name, {
      level: first.grudge || "NONE",
      bond: typeof first.bond === "number" ? first.bond : 50,
      lastGrievance: first.last_grievance || null,
      flashUntil: 0,
    });
  });
  snap.players.forEach((p) => ensureSoul(p.name, "player", p.zone));
  state.phase = snap.phase;
  state.engine = snap.engine || "templated";
  document.getElementById("cost-overlay").classList.toggle("hidden", state.engine === "templated");
  renderCards();
  renderPhase();
}

function ensureSoul(name, kind, zone) {
  const color =
    SOUL_COLORS[name] || FALLBACK_COLORS[state.souls.size % FALLBACK_COLORS.length];
  state.souls.set(name, { kind, zone: zone || "tavern", color });
}

async function poll() {
  try {
    const events = await fetch(`/events?since=${state.cursor}`).then((r) => r.json());
    if (!Array.isArray(events) || events.length === 0) return;
    events.forEach(apply);
    renderCards();
    renderPhase();
  } catch (err) {
    setStatus("server unreachable...");
  }
}

function apply(e) {
  state.cursor = Math.max(state.cursor, e.t);
  const card = e.npc ? state.cards.get(e.npc) : null;
  switch (e.type) {
    case "move": {
      const soul = state.souls.get(e.name);
      if (soul) soul.zone = e.zone;
      else ensureSoul(e.name, "npc", e.zone);
      break;
    }
    case "beat":
      addBubble(e.player, e.line, true);
      if (card && e.kind !== "neutral") card.lastGrievance = e.line;
      break;
    case "speech":
      addBubble(e.npc, e.text, false);
      break;
    case "grudge_change":
      if (card) {
        card.level = e.new;
        card.flashUntil = performance.now() + 1200;
      }
      break;
    case "bond_change":
      if (card) card.bond = e.value;
      break;
    case "director_phase":
      state.phase = e.phase;
      break;
    case "cost_tick":
      state.cost = e;
      break;
  }
}

// ---------------------------------------------------------------------------
// Canvas rendering
// ---------------------------------------------------------------------------

function bubbleLife(bubble) {
  return bubble.special ? SPECIAL_BUBBLE_MS : BUBBLE_MS;
}

function draw(now) {
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  drawFloor();
  Object.values(ZONES).forEach(drawZone);
  for (const name of state.souls.keys()) drawSoul(name);
  state.bubbles = state.bubbles.filter((b) => now - b.born < bubbleLife(b));
  state.bubbles.forEach((b) => drawBubble(b, now));
  requestAnimationFrame(draw);
}

function drawFloor() {
  ctx.fillStyle = "#241c12";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.strokeStyle = "rgba(0,0,0,0.25)"; // plank seams
  ctx.lineWidth = 1;
  for (let y = 24; y < canvas.height; y += 34) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(canvas.width, y);
    ctx.stroke();
  }
  ctx.fillStyle = "#8a765c";
  ctx.font = "italic 13px Georgia";
  ctx.textAlign = "left";
  ctx.fillText("The Rusty Cleaver — a tavern that keeps score", 16, 26);
}

function drawZone(z) {
  ctx.strokeStyle = "#4a3a24";
  ctx.lineWidth = 1.5;
  roundRect(z.x, z.y, z.w, z.h, 10);
  ctx.stroke();
  ctx.fillStyle = "rgba(217,164,65,0.05)";
  roundRect(z.x, z.y, z.w, z.h, 10);
  ctx.fill();
  ctx.fillStyle = "#8a765c";
  ctx.font = "11px Courier New";
  ctx.textAlign = "left";
  ctx.fillText(z.label.toUpperCase(), z.x + 8, z.y + 16);
}

function zoneMates(zone) {
  return [...state.souls.entries()].filter(([, s]) => s.zone === zone).map(([n]) => n);
}

function positionOf(name) {
  const soul = state.souls.get(name);
  const z = ZONES[soul.zone] || ZONES.tavern;
  const mates = zoneMates(soul.zone);
  const idx = mates.indexOf(name);
  const x = z.x + z.w / 2 + (idx - (mates.length - 1) / 2) * 52;
  const y = z.y + z.h - 44;
  return { x, y };
}

function drawSoul(name) {
  const soul = state.souls.get(name);
  const { x, y } = positionOf(name);
  ctx.beginPath();
  ctx.arc(x, y, 17, 0, Math.PI * 2);
  ctx.fillStyle = soul.color;
  ctx.fill();
  ctx.lineWidth = soul.kind === "player" ? 3 : 1.5;
  ctx.strokeStyle = soul.kind === "player" ? "#e8dcc5" : "#120d08";
  ctx.stroke();
  ctx.fillStyle = "#120d08";
  ctx.font = "bold 13px Georgia";
  ctx.textAlign = "center";
  ctx.fillText(name[0], x, y + 4.5);
  ctx.fillStyle = "#e8dcc5";
  ctx.font = "12px Georgia";
  ctx.fillText(name, x, y + 34);
}

function addBubble(name, text, fromPlayer, special) {
  if (!name || !text) return;
  state.bubbles = state.bubbles.filter((b) => b.name !== name); // one per speaker
  state.bubbles.push({ name, text, born: performance.now(), fromPlayer, special: !!special });
}

function drawBubble(bubble, now) {
  if (!state.souls.has(bubble.name)) return;
  const { x, y } = positionOf(bubble.name);
  const age = now - bubble.born;
  const life = bubbleLife(bubble);
  const alpha = age < life - 900 ? 1 : Math.max(0, (life - age) / 900);
  const maxLines = bubble.special ? 4 : 3;
  const lines = wrap(bubble.text, 30, maxLines);
  const w = Math.min(230, Math.max(...lines.map((l) => l.length)) * 6.4 + 20);
  const h = lines.length * 15 + 14;
  let bx = Math.min(Math.max(x - w / 2, 6), canvas.width - w - 6);
  let by = Math.max(y - 44 - h, 6);

  ctx.globalAlpha = alpha;
  if (bubble.special) {
    // The reputation gut-punch: amber, glowing, unmistakable.
    ctx.shadowColor = "#d9a441";
    ctx.shadowBlur = 14;
    ctx.fillStyle = "#d9a441";
  } else {
    ctx.fillStyle = bubble.fromPlayer ? "#3a4a5c" : "#efe3c8";
  }
  roundRect(bx, by, w, h, 8);
  ctx.fill();
  ctx.beginPath(); // tail
  ctx.moveTo(x - 5, by + h);
  ctx.lineTo(x + 5, by + h);
  ctx.lineTo(x, by + h + 8);
  ctx.fill();
  ctx.shadowBlur = 0;
  ctx.fillStyle = bubble.special ? "#241c12" : bubble.fromPlayer ? "#e8dcc5" : "#241c12";
  ctx.font = bubble.special ? "bold 12px Georgia" : "12px Georgia";
  ctx.textAlign = "left";
  lines.forEach((line, i) => ctx.fillText(line, bx + 10, by + 18 + i * 15));
  ctx.globalAlpha = 1;
}

function wrap(text, width, maxLines) {
  const words = String(text).split(/\s+/);
  const lines = [];
  let line = "";
  for (const word of words) {
    if ((line + " " + word).trim().length > width) {
      lines.push(line.trim());
      line = word;
      if (lines.length === maxLines) {
        lines[maxLines - 1] += "…";
        return lines;
      }
    } else {
      line += " " + word;
    }
  }
  if (line.trim()) lines.push(line.trim());
  return lines.slice(0, maxLines);
}

function roundRect(x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

// ---------------------------------------------------------------------------
// HUD (right panel + top bar)
// ---------------------------------------------------------------------------

function renderCards() {
  const box = document.getElementById("cards");
  box.innerHTML = "";
  const now = performance.now();
  for (const [name, card] of state.cards) {
    const el = document.createElement("div");
    el.className = "card" + (card.flashUntil > now ? " flash" : "");
    el.innerHTML =
      `<div class="head"><span class="name">${name}</span>` +
      `<span class="chip ${card.level}">${card.level}</span></div>` +
      `<div class="bond">bond with Ragnar: <b>${card.bond.toFixed(1)}</b> / 100</div>` +
      `<div class="grievance">${
        card.lastGrievance ? "remembers: “" + escapeHtml(card.lastGrievance) + "”"
                           : "no grievances yet"
      }</div>`;
    box.appendChild(el);
  }
  document.getElementById("cost").textContent = state.cost
    ? `${state.cost.model}: ${state.cost.calls} calls (${state.cost.cached_calls} cached) — $${state.cost.total_cost.toFixed(4)}`
    : "templated dialogue — $0";
}

function renderPhase() {
  document.querySelectorAll("#phase-indicator .phase").forEach((el) => {
    el.classList.toggle("active", el.dataset.phase === state.phase);
  });
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

function setStatus(message) {
  document.getElementById("status").textContent = message || "";
}

// ---------------------------------------------------------------------------
// Controls — right panel (explicit kind) + bottom free-play bar (auto kind)
// ---------------------------------------------------------------------------

function setFreeStatus(message) {
  document.getElementById("free-status").textContent = message || "";
}

async function refreshCost() {
  // Only meaningful when a metered LLM engine is active.
  if (state.engine === "templated") return;
  try {
    const cost = await fetch("/cost").then((r) => r.json());
    const cached = cost.cached_calls ? ` (+${cost.cached_calls} cached)` : "";
    document.getElementById("cost-lines").textContent =
      `${cost.calls} LLM line${cost.calls === 1 ? "" : "s"}${cached} — ${cost.model}`;
    document.getElementById("cost-total").textContent =
      `this session: $${cost.total_cost.toFixed(4)}`;
    document.getElementById("cost-deepseek").textContent =
      `would cost on DeepSeek: $${cost.projected_deepseek.toFixed(5)}`;
    document.getElementById("cost-hour").textContent =
      `per player-hour: $${cost.cost_per_player_hour.toFixed(4)}`;
  } catch (err) {
    /* cost readout is best-effort — never break play */
  }
}

async function postLine(payload) {
  const res = await fetch("/line", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.error || `error ${res.status}`);
  refreshCost();
  return body;
}

document.getElementById("controls").addEventListener("submit", async (e) => {
  e.preventDefault();
  const input = document.getElementById("line");
  const text = input.value.trim();
  if (!text) return;
  setStatus("");
  try {
    await postLine({
      player: "Ragnar",
      text,
      kind: document.getElementById("kind").value,
      npc: document.getElementById("npc").value,
    });
    input.value = "";
  } catch (err) {
    setStatus(err.message);
  }
});

// Free-play: no "kind" — the server's keyword classifier decides, and we echo
// what it heard so the tone flip is legible on camera.
document.getElementById("freeplay").addEventListener("submit", async (e) => {
  e.preventDefault();
  const input = document.getElementById("free-line");
  const text = input.value.trim();
  if (!text) return;
  setFreeStatus("");
  try {
    const summary = await postLine({
      player: "Ragnar",
      text,
      npc: document.getElementById("npc").value,
    });
    input.value = "";
    setFreeStatus(summary.kind === "neutral" ? "" : `heard as: ${summary.kind}`);
  } catch (err) {
    setFreeStatus(err.message);
  }
});

document.getElementById("reset").addEventListener("click", async () => {
  await fetch("/reset", { method: "POST" });
  state.cursor = 0;
  state.bubbles = [];
  state.cost = null;
  setStatus("");
  setFreeStatus("");
  document.getElementById("notoriety-chip").className = "chip hidden";
  await seedFromSnapshot();
});

// ---------------------------------------------------------------------------
// Soul file actions — export / import / the reputation gut-punch
// ---------------------------------------------------------------------------

async function downloadSoul(url, payload, fallbackName) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload || {}),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    setFreeStatus(err.error || `error ${res.status}`);
    return;
  }
  const blob = await res.blob();
  const disposition = res.headers.get("Content-Disposition") || "";
  const match = disposition.match(/filename="?([^";]+)"?/);
  const name = match ? match[1] : fallbackName;
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
  URL.revokeObjectURL(a.href);
  setFreeStatus(`${name} saved — ${Math.round(blob.size / 1024)} KB of memory`);
}

document.getElementById("export-npc").addEventListener("click", () => {
  downloadSoul("/export_soul", { npc: "Bjorn" }, "bjorn.soul");
});

document.getElementById("export-player").addEventListener("click", () => {
  downloadSoul("/export_player", { player: "Ragnar" }, "ragnar.player.soul");
});

document.getElementById("import-btn").addEventListener("click", () => {
  document.getElementById("soul-file").click();
});

document.getElementById("soul-file").addEventListener("change", async (e) => {
  const file = e.target.files[0];
  e.target.value = ""; // allow re-importing the same file
  if (!file) return;
  const bytes = await file.arrayBuffer();
  const res = await fetch("/import_soul", {
    method: "POST",
    headers: { "Content-Type": "application/octet-stream" },
    body: bytes,
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    setFreeStatus(body.error || `error ${res.status}`);
    return;
  }
  state.bubbles = [];
  await seedFromSnapshot(); // the imported grudge state, straight to the HUD
  setFreeStatus(`${body.replaced} awakened from ${file.name} — they remember.`);
});

document.getElementById("ask-innkeeper").addEventListener("click", async () => {
  const res = await fetch("/reputation?npc=Astrid&player=Ragnar");
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    setFreeStatus(body.error || `error ${res.status}`);
    return;
  }
  addBubble(body.npc, body.line, false, true); // the gut-punch, in amber
  const chip = document.getElementById("notoriety-chip");
  chip.textContent = body.notoriety;
  chip.className = `chip ${body.notoriety}`;
});

document.getElementById("cost-toggle").addEventListener("click", () => {
  document.getElementById("cost-body").classList.toggle("hidden");
});

boot();
