// app.js — NEM-4 PART C: the SAURON'S ARMY client engine.
// Created: 2026-07-05 (feat/nemesis-warband) — vanilla JS, no framework, no CDN.
// Fetches GET /board, renders three ranked tiers of ornate member cards with
// PROCEDURAL SVG crests (a colored monogram per member, no external art), draws
// rivalry threads on the SVG overlay between members who hate each other, runs
// the confront modal (win/lose -> dramatic result), the director bar (advance
// the war -> revenge alert / power struggle), recruit, and .soul exports. Polls
// GET /events?since=N every ~700ms to catch director-driven beats.

(() => {
  "use strict";

  const RANKS = ["Warlord", "Captain", "Grunt"];
  const $ = (sel) => document.querySelector(sel);

  const rows = {
    Warlord: $("#row-warlord"),
    Captain: $("#row-captain"),
    Grunt: $("#row-grunt"),
  };

  // Cross-render memory so we can animate rank changes and keep the modal fresh.
  let lastRankByDid = {};
  let eventCursor = 0;
  let boardCache = { members: [] };
  let modalDid = null;
  let pollTimer = null;

  // ---- tiny fetch helpers ------------------------------------------------
  async function getJSON(url) {
    const r = await fetch(url);
    if (!r.ok) throw new Error(`${url} -> ${r.status}`);
    return r.json();
  }
  async function postJSON(url, body) {
    const r = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(data.error || `${url} -> ${r.status}`);
    return data;
  }

  // ---- procedural crest --------------------------------------------------
  // A deterministic colored monogram from the member's initials + a hashed hue,
  // rendered as an inline SVG shield. No external assets; every orc is distinct.
  function hashString(s) {
    let h = 2166136261;
    for (let i = 0; i < s.length; i++) {
      h ^= s.charCodeAt(i);
      h = Math.imul(h, 16777619);
    }
    return h >>> 0;
  }
  function initials(name) {
    const letters = [...name].filter((c) => /[\p{L}]/u.test(c));
    if (letters.length === 0) return "?";
    const first = letters[0].toUpperCase();
    // second glyph: next consonant-ish char for a two-letter monogram
    const second = letters.length > 1 ? letters[1].toUpperCase() : "";
    return (first + second).slice(0, 2);
  }
  function crestSVG(name, size, grudge) {
    const h = hashString(name);
    const hue = h % 360;
    const hue2 = (hue + 28) % 360;
    // Grudge tints the ring toward blood-red.
    const ring =
      grudge === "GRUDGING" ? "#ff4a24" : grudge === "SLIGHTED" ? "#c8371d" : "#5a4a3a";
    const glow = grudge === "GRUDGING" ? 0.9 : grudge === "SLIGHTED" ? 0.5 : 0.2;
    const uid = "c" + (h % 100000);
    const mono = initials(name);
    const fs = size * 0.4;
    return `
      <svg viewBox="0 0 100 100" width="${size}" height="${size}" role="img" aria-label="${name} crest">
        <defs>
          <radialGradient id="${uid}" cx="42%" cy="34%" r="72%">
            <stop offset="0%"  stop-color="hsl(${hue} 55% 34%)"/>
            <stop offset="60%" stop-color="hsl(${hue2} 48% 20%)"/>
            <stop offset="100%" stop-color="hsl(${hue} 40% 9%)"/>
          </radialGradient>
        </defs>
        <path d="M50 4 L92 18 V52 Q92 82 50 96 Q8 82 8 52 V18 Z"
              fill="url(#${uid})" stroke="${ring}" stroke-width="3"
              style="filter: drop-shadow(0 0 ${8 * glow}px ${ring});"/>
        <path d="M50 4 L92 18 V52 Q92 82 50 96 Q8 82 8 52 V18 Z"
              fill="none" stroke="rgba(0,0,0,0.5)" stroke-width="1" transform="scale(0.9) translate(5.5 5.5)"/>
        <text x="50" y="52" text-anchor="middle" dominant-baseline="central"
              font-family="'Trajan Pro','Cinzel',Palatino,serif" font-size="${fs}"
              font-weight="700" fill="#eaddc6" style="letter-spacing:1px; text-shadow:0 2px 3px rgba(0,0,0,0.8);">${mono}</text>
      </svg>`;
  }

  const RANK_SIGIL = { Warlord: "♛", Captain: "✠", Grunt: "•" };

  // ---- card rendering ----------------------------------------------------
  function cardHTML(m) {
    const emblem = crestSVG(m.name, m.rank_label === "Warlord" ? 62 : m.rank_label === "Captain" ? 54 : 46, m.grudge_level);
    const remembers = m.last_grievance
      ? `<div class="card__remembers"><b>REMEMBERS</b> · ${escapeHTML(stripMarker(m.last_grievance))}</div>`
      : "";
    const rivals =
      m.rivalries && m.rivalries.length
        ? `<div class="card__rivals">${m.rivalries
            .map((r) => `<span class="rival-chip">${escapeHTML(r)}</span>`)
            .join("")}</div>`
        : "";
    const confront = m.alive
      ? `<button class="card__confront" data-did="${m.did}">⚔ Confront</button>`
      : "";
    const grudgeWord =
      m.grudge_level === "GRUDGING" ? "Blood grudge" : m.grudge_level === "SLIGHTED" ? "Slighted" : "No quarrel";
    return `
      <article class="card" data-did="${m.did}" data-grudge="${m.grudge_level}" data-alive="${m.alive}">
        <div class="card__slash"></div>
        <div class="card__skull">☠</div>
        <div class="card__top">
          <div class="card__emblem">${emblem}</div>
          <span class="card__rank" data-rank="${m.rank_label}">
            <span class="card__rank-sigil">${RANK_SIGIL[m.rank_label] || "•"}</span>${m.rank_label}
          </span>
        </div>
        <h3 class="card__name">${escapeHTML(m.name)}</h3>
        <p class="card__epithet">${escapeHTML(m.epithet)}</p>
        <div class="card__grudge">
          <div class="card__grudge-level"><span class="card__grudge-dot"></span>${grudgeWord}</div>
          ${remembers}
        </div>
        ${rivals}
        ${confront}
      </article>`;
  }

  // The package stores grievances as "[GRUDGE ...] <did> wronged me: <text>" or,
  // via phrase_grievances, a clean phrase. Strip any marker/preamble for display.
  function stripMarker(s) {
    if (!s) return "";
    const cut = s.split(" wronged me: ");
    let out = cut.length > 1 ? cut[1] : s;
    out = out.replace(/^\[GRUDGE[^\]]*\]\s*/, "");
    return out;
  }
  function escapeHTML(s) {
    return String(s).replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
    );
  }

  function render(board) {
    boardCache = board;
    // header + reputation
    $("#engine-name").textContent = board.engine || "templated";
    setPhase(board.phase);
    const rep = board.player || {};
    const notEl = $("#rep-notoriety");
    notEl.textContent = rep.notoriety || "UNKNOWN";
    notEl.dataset.band = rep.notoriety || "UNKNOWN";
    $("#rep-tag").textContent =
      rep.notoriety === "NOTORIOUS"
        ? "your legend precedes you — they hunt what they fear"
        : rep.notoriety === "KNOWN"
        ? "your name travels ahead of you"
        : "an unknown wanderer";
    const deeds = [...new Set(rep.deeds || [])];
    $("#rep-deeds").innerHTML = deeds
      .slice(0, 4)
      .map((d) => `<span class="deed-chip">${escapeHTML(d)}</span>`)
      .join("");

    // tiers
    const byRank = { Warlord: [], Captain: [], Grunt: [] };
    for (const m of board.members) (byRank[m.rank_label] || byRank.Grunt).push(m);
    for (const rank of RANKS) {
      rows[rank].innerHTML = byRank[rank].map(cardHTML).join("") || `<p class="tier__empty"></p>`;
    }

    // rank-change animations
    for (const m of board.members) {
      const prev = lastRankByDid[m.did];
      if (prev && prev !== m.rank_label && m.alive) {
        const el = document.querySelector(`.card[data-did="${cssEscape(m.did)}"]`);
        if (el) {
          const rose = RANKS.indexOf(m.rank_label) < RANKS.indexOf(prev); // Warlord=0 is highest
          el.classList.add(rose ? "card--promoted" : "card--demoted");
        }
      }
    }
    lastRankByDid = Object.fromEntries(board.members.map((m) => [m.did, m.rank_label]));

    // draw rivalry threads after layout settles
    requestAnimationFrame(() => drawRivalries(board));
  }

  function cssEscape(s) {
    return window.CSS && CSS.escape ? CSS.escape(s) : s.replace(/[^\w-]/g, "\\$&");
  }

  function setPhase(phase) {
    const pill = $("#phase-pill");
    pill.textContent = phase || "RELAX";
    pill.dataset.phase = phase || "RELAX";
  }

  // ---- rivalry threads (SVG overlay) ------------------------------------
  function drawRivalries(board) {
    const svg = $("#rivalry-layer");
    const army = $("#army");
    const box = army.getBoundingClientRect();
    svg.setAttribute("viewBox", `0 0 ${box.width} ${box.height}`);
    svg.innerHTML = "";

    const nameToDid = {};
    for (const m of board.members) nameToDid[m.name] = m.did;

    // center point of each card, in army-local coordinates
    const center = (did) => {
      const el = document.querySelector(`.card[data-did="${cssEscape(did)}"]`);
      if (!el) return null;
      const r = el.getBoundingClientRect();
      return { x: r.left - box.left + r.width / 2, y: r.top - box.top + r.height / 2 };
    };

    const drawn = new Set();
    for (const m of board.members) {
      for (const rivalName of m.rivalries || []) {
        const otherDid = nameToDid[rivalName];
        if (!otherDid) continue;
        const key = [m.did, otherDid].sort().join("|");
        // mutual rivalry (both hate each other) reads as a hotter, thicker thread
        const other = board.members.find((x) => x.did === otherDid);
        const mutual = other && (other.rivalries || []).includes(m.name);
        if (drawn.has(key)) continue;
        drawn.add(key);
        const a = center(m.did);
        const b = center(otherDid);
        if (!a || !b) continue;
        appendThread(svg, a, b, mutual);
      }
    }
  }

  function appendThread(svg, a, b, mutual) {
    const NS = "http://www.w3.org/2000/svg";
    // a gentle bowed line so crossings read as threads, not a web
    const mx = (a.x + b.x) / 2;
    const my = (a.y + b.y) / 2;
    const dx = b.x - a.x, dy = b.y - a.y;
    const len = Math.hypot(dx, dy) || 1;
    const bow = Math.min(46, len * 0.14);
    const cx = mx - (dy / len) * bow;
    const cy = my + (dx / len) * bow;
    const path = document.createElementNS(NS, "path");
    path.setAttribute("d", `M ${a.x} ${a.y} Q ${cx} ${cy} ${b.x} ${b.y}`);
    path.setAttribute("fill", "none");
    path.setAttribute("stroke", mutual ? "rgba(255,74,36,0.55)" : "rgba(154,116,51,0.32)");
    path.setAttribute("stroke-width", mutual ? "2.2" : "1.3");
    path.setAttribute("stroke-dasharray", mutual ? "1 0" : "5 5");
    if (mutual) path.setAttribute("style", "filter: drop-shadow(0 0 4px rgba(255,74,36,0.6));");
    svg.appendChild(path);

    // crossed-blade mark at the midpoint of a mutual grudge
    if (mutual) {
      const mark = document.createElementNS(NS, "text");
      mark.setAttribute("x", cx);
      mark.setAttribute("y", cy + 4);
      mark.setAttribute("text-anchor", "middle");
      mark.setAttribute("fill", "#ff8a6a");
      mark.setAttribute("font-size", "13");
      mark.textContent = "⚔";
      svg.appendChild(mark);
    }
  }

  // ---- the confront modal -----------------------------------------------
  function openModal(did) {
    const m = boardCache.members.find((x) => x.did === did);
    if (!m) return;
    modalDid = did;
    $("#stage-clash").hidden = false;
    $("#stage-result").hidden = true;
    $("#clash-name").textContent = m.name;
    $("#clash-epithet").textContent = m.epithet + " · " + m.rank_label;
    $("#modal-crest").innerHTML = crestSVG(m.name, 64, m.grudge_level);
    $("#modal-scrim").hidden = false;
  }
  function closeModal() {
    $("#modal-scrim").hidden = true;
    modalDid = null;
  }

  async function resolveClash(playerWon) {
    if (!modalDid) return;
    let beat;
    try {
      beat = await postJSON("/confront", { member_did: modalDid, player_won: playerWon });
    } catch (e) {
      alert("The clash failed: " + e.message);
      return;
    }
    // reveal the result stage dramatically
    $("#stage-clash").hidden = true;
    const banner = $("#result-banner");
    const tone = beat.killed ? "death" : beat.outcome === "member_won" ? "rise" : "fall";
    banner.dataset.tone = tone;
    banner.textContent = beat.killed
      ? `${beat.member} falls`
      : beat.outcome === "member_won"
      ? `${beat.member} rises to ${beat.rank_label}`
      : `${beat.member} is cast down`;
    $("#result-taunt").textContent = beat.taunt || "";
    const meta = [];
    if (beat.rank_change > 0) meta.push(`Promoted to <b>${beat.rank_label}</b>`);
    if (beat.rank_change < 0) meta.push(`Demoted to <b>${beat.rank_label}</b>`);
    if (beat.killed) meta.push(`<b>Slain</b> — a grunt does not survive the pit`);
    if (beat.rivalry_triggered) meta.push(`<b>${beat.rivalry_triggered}</b> seethes with envy`);
    $("#result-meta").innerHTML = meta.join(" &nbsp;·&nbsp; ");
    $("#stage-result").hidden = false;
    // refresh the board underneath (with animations) and the event cursor
    if (beat.board) render(beat.board);
    eventCursor = Math.max(eventCursor, (beat.board && beat.board.cursor) || eventCursor);
  }

  // ---- director bar: advance the war ------------------------------------
  async function advanceWar() {
    const btn = $("#btn-tick");
    btn.disabled = true;
    try {
      const beat = await postJSON("/tick", {});
      setPhase(beat.phase);
      if (beat.board) render(beat.board);
      if (beat.revenge) flareRevenge(beat.revenge);
      if (beat.power_struggle) toastStruggle(beat.power_struggle);
      eventCursor = Math.max(eventCursor, (beat.board && beat.board.cursor) || eventCursor);
    } catch (e) {
      console.error(e);
    } finally {
      btn.disabled = false;
    }
  }

  let revengeTimer = null;
  function flareRevenge(rev) {
    const el = $("#revenge-alert");
    $("#revenge-alert-line").textContent = `${rev.member} ${rev.epithet}: ${rev.taunt}`;
    el.hidden = false;
    // retrigger the entry animation
    el.style.animation = "none";
    void el.offsetWidth;
    el.style.animation = "";
    clearTimeout(revengeTimer);
    revengeTimer = setTimeout(() => (el.hidden = true), 6500);
  }

  function toastStruggle(ps) {
    // reuse the revenge banner styling for a power-struggle callout
    const el = $("#revenge-alert");
    $(".revenge-alert__title").textContent = "A POWER STRUGGLE";
    const fate = ps.loser_killed ? `kills ${ps.loser}` : `casts down ${ps.loser}`;
    $("#revenge-alert-line").textContent = `${ps.winner} rises to ${ps.winner_rank} and ${fate}.`;
    el.hidden = false;
    el.style.animation = "none";
    void el.offsetWidth;
    el.style.animation = "";
    clearTimeout(revengeTimer);
    revengeTimer = setTimeout(() => {
      el.hidden = true;
      $(".revenge-alert__title").textContent = "A NEMESIS HUNTS YOU";
    }, 6500);
  }

  // ---- recruit + exports -------------------------------------------------
  async function recruit() {
    const btn = $("#btn-recruit");
    btn.disabled = true;
    try {
      const rec = await postJSON("/recruit", {});
      if (rec.board) render(rec.board);
      // announce the recruit's first line through the banner
      const el = $("#revenge-alert");
      $(".revenge-alert__title").textContent = `${rec.member.toUpperCase()} JOINS THE HOST`;
      $("#revenge-alert-line").textContent = rec.first_line;
      el.hidden = false;
      el.style.animation = "none";
      void el.offsetWidth;
      el.style.animation = "";
      clearTimeout(revengeTimer);
      revengeTimer = setTimeout(() => {
        el.hidden = true;
        $(".revenge-alert__title").textContent = "A NEMESIS HUNTS YOU";
      }, 6500);
    } catch (e) {
      alert("Recruit failed: " + e.message);
    } finally {
      btn.disabled = false;
    }
  }

  async function download(url, body) {
    const r = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    });
    if (!r.ok) {
      const d = await r.json().catch(() => ({}));
      alert("Export failed: " + (d.error || r.status));
      return;
    }
    const disp = r.headers.get("Content-Disposition") || "";
    const match = disp.match(/filename="([^"]+)"/);
    const filename = match ? match[1] : "download.soul";
    const blob = await r.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 4000);
  }

  // ---- event polling -----------------------------------------------------
  async function poll() {
    try {
      const events = await getJSON(`/events?since=${eventCursor}`);
      for (const ev of events) {
        eventCursor = Math.max(eventCursor, ev.t);
        // Director-driven beats (from another client or an auto-advance) surface
        // here too; the button path already flares its own, so only react to
        // ones we might not have shown. We keep it light: refresh on structural
        // events (death / power_struggle / recruit) so the board stays truthful.
        if (["death", "power_struggle", "recruit"].includes(ev.kind)) {
          const board = await getJSON("/board").catch(() => null);
          if (board) render(board);
          break;
        }
      }
    } catch (e) {
      /* server momentarily busy; try again next tick */
    } finally {
      pollTimer = setTimeout(poll, 700);
    }
  }

  // ---- wiring ------------------------------------------------------------
  function wire() {
    // confront buttons are delegated (cards re-render constantly)
    document.addEventListener("click", (e) => {
      const btn = e.target.closest(".card__confront");
      if (btn) openModal(btn.dataset.did);
    });
    $("#btn-win").addEventListener("click", () => resolveClash(true));
    $("#btn-lose").addEventListener("click", () => resolveClash(false));
    $("#btn-result-done").addEventListener("click", closeModal);
    $("#btn-export-member").addEventListener("click", () => {
      if (modalDid) download("/export_member", { did: modalDid });
    });
    $("#modal-close").addEventListener("click", closeModal);
    $("#modal-scrim").addEventListener("click", (e) => {
      if (e.target === $("#modal-scrim")) closeModal();
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") closeModal();
    });
    $("#btn-tick").addEventListener("click", advanceWar);
    $("#btn-recruit").addEventListener("click", recruit);
    $("#btn-export-warband").addEventListener("click", () => download("/export_warband", {}));
    window.addEventListener("resize", () => drawRivalries(boardCache));
  }

  async function boot() {
    wire();
    try {
      const board = await getJSON("/board");
      eventCursor = board.cursor || 0;
      render(board);
    } catch (e) {
      document.body.insertAdjacentHTML(
        "beforeend",
        `<p style="color:#ff8a6a;text-align:center;padding:40px;font-family:serif">The war-camp is unreachable — is the server running on this port?</p>`
      );
      return;
    }
    poll();
  }

  boot();
})();
