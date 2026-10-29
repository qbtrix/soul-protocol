# gateway/_dashboard.py - Single-page HTML for the Soul dashboard (served at GET /dashboard).
# Created: 2026-10 - Moved out of app.py and redesigned. Dark/light/system theme,
#   sidebar navigation, keyboard shortcuts, memory filters/sort/export, chart
#   tooltips, expandable trust chain, configurable auto-refresh. No emoji, no
#   gradients. Motion is limited to short color and width transitions, which
#   are disabled under prefers-reduced-motion. All dynamic text is HTML-escaped
#   before insertion.
#   Only the existing read-only /api/* endpoints are used.

DASHBOARD_HTML = r"""<!doctype html>
<html lang="en" data-theme="dark" data-pref="system">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Soul Dashboard</title>
<link rel="icon" type="image/svg+xml" href="/favicon.svg">
<script>
(function(){
  var pref='system';
  try{pref=localStorage.getItem('soul-dashboard-theme')||'system';}catch(e){}
  var dark=pref==='dark'||(pref==='system'&&window.matchMedia('(prefers-color-scheme: dark)').matches);
  document.documentElement.dataset.theme=dark?'dark':'light';
  document.documentElement.dataset.pref=pref;
})();
</script>
<style>
:root{
  --bg:#09090b;--panel:#0f0f12;--panel2:#18181b;--inset:#0c0c0f;--border:#27272a;--border-strong:#3f3f46;
  --text:#fafafa;--muted:#a1a1aa;
  --accent:#059669;--accent-text:#34d399;--on-accent:#02130c;
  --good:#4ade80;--warn:#fbbf24;--danger:#f87171;--info:#60a5fa;
  --focus:#34d399;--shadow:0 10px 30px rgba(0,0,0,.5);--scrim:rgba(0,0,0,.65);
  --radius:8px;--side:216px;
  --mono:ui-monospace,SFMono-Regular,Menlo,Consolas,"Liberation Mono",monospace;
  --sans:system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;
  color-scheme:dark;
}
:root[data-theme="light"]{
  --bg:#fafafa;--panel:#ffffff;--panel2:#f4f4f5;--inset:#f4f4f5;--border:#e4e4e7;--border-strong:#a1a1aa;
  --text:#18181b;--muted:#52525b;
  --accent:#047857;--accent-text:#047857;--on-accent:#ffffff;
  --good:#15803d;--warn:#a16207;--danger:#b91c1c;--info:#1d4ed8;
  --focus:#047857;--shadow:0 10px 30px rgba(0,0,0,.15);--scrim:rgba(24,24,27,.45);
  color-scheme:light;
}
*{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%}
body{font-family:var(--sans);background:var(--bg);color:var(--text);line-height:1.5;font-size:14px}
button,input,select{font:inherit;color:inherit}
button{cursor:pointer}
:focus-visible{outline:2px solid var(--focus);outline-offset:2px}
::-webkit-scrollbar{width:8px;height:8px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:var(--border-strong);border-radius:4px}
.sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
.mono{font-family:var(--mono)}

/* Shell */
.shell>*{min-width:0}
.shell{display:grid;grid-template-columns:var(--side) minmax(0,1fr);min-height:100%}
.side{position:sticky;top:0;align-self:start;height:100vh;display:flex;flex-direction:column;padding:20px 12px;border-right:1px solid var(--border);background:var(--panel)}
.brand{font-weight:600;font-size:15px;padding:0 10px 16px}
.nav{display:flex;flex-direction:column;gap:2px}
.nav button{display:flex;justify-content:space-between;align-items:center;gap:8px;text-align:left;background:none;border:0;border-radius:6px;padding:7px 10px;color:var(--muted);font-size:13px}
.nav button:hover{background:var(--panel2);color:var(--text)}
.nav button[aria-selected="true"]{background:var(--panel2);color:var(--text);box-shadow:inset 2px 0 0 var(--accent)}
.nav kbd,.kbd{font-family:var(--mono);font-size:10px;color:var(--muted);border:1px solid var(--border);border-radius:4px;padding:0 5px;background:var(--bg)}
.side-foot{margin-top:auto;display:flex;flex-direction:column;gap:12px;padding:0 4px}
.side-label{font-size:10px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);padding:0 6px}
.seg{display:grid;grid-template-columns:repeat(3,1fr);border:1px solid var(--border);border-radius:6px;overflow:hidden;background:var(--bg)}
.seg button{background:none;border:0;padding:5px 0;font-size:12px;color:var(--muted)}
.seg button+button{border-left:1px solid var(--border)}
.seg button:hover{color:var(--text)}
.seg button[aria-pressed="true"]{background:var(--accent);color:var(--on-accent);font-weight:600}
.refresh-opts{display:flex;flex-direction:column;gap:8px;font-size:12px;color:var(--muted);padding:0 6px}
.refresh-opts label{display:flex;align-items:center;justify-content:space-between;gap:8px}
.refresh-opts select{background:var(--bg);border:1px solid var(--border);border-radius:6px;padding:3px 6px;font-size:12px}
.refresh-opts input[type=checkbox]{accent-color:var(--accent)}

.main{min-width:0;padding:24px 32px 64px;width:100%}
.top{display:flex;flex-wrap:wrap;gap:12px 20px;align-items:flex-start;justify-content:space-between;margin-bottom:24px}
.top h1{font-size:22px;font-weight:600;letter-spacing:-.01em}
.did{display:inline-block;background:none;border:0;padding:0;font-family:var(--mono);font-size:11px;color:var(--muted);max-width:100%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.did:hover{color:var(--accent-text);text-decoration:underline}
.top-right{display:flex;flex-direction:column;align-items:flex-end;gap:8px}
.badges{display:flex;gap:6px;flex-wrap:wrap}
.badge{background:var(--panel);border:1px solid var(--border);border-radius:6px;padding:2px 9px;font-size:12px;color:var(--muted)}
.badge b{color:var(--text);font-weight:600}
.status{display:flex;align-items:center;gap:10px;font-size:12px;color:var(--muted)}
.dot{width:7px;height:7px;border-radius:50%;background:var(--good);display:inline-block;margin-right:6px}
.dot.off{background:var(--danger)}
.btn{background:var(--accent);color:var(--on-accent);border:1px solid var(--accent);border-radius:6px;padding:5px 12px;font-size:12px;font-weight:600}
.btn:hover{filter:brightness(1.1)}
.btn.ghost{background:transparent;color:var(--text);border-color:var(--border);font-weight:500}
.btn.ghost:hover{border-color:var(--border-strong);filter:none}
.btn:disabled{opacity:.5;cursor:default}
.nav button,.btn,.fbtn,.card,.mem,.chip,.tl-row,.seg button,.x,.link,.legal a{transition:background-color .15s ease,border-color .15s ease,color .15s ease}
.link{background:none;border:0;padding:0;font-size:12px;color:var(--accent-text)}
.link:hover{text-decoration:underline}
.legal{display:flex;gap:14px;font-size:11px;padding:0 6px}
.legal a{color:var(--muted);text-decoration:none}
.legal a:hover{color:var(--text);text-decoration:underline}

.view{display:none}
.view.active{display:block}

/* Panels and cards */
.panel{background:var(--panel);border:1px solid var(--border);border-radius:var(--radius);padding:18px 20px;margin-bottom:16px}
.panel-head{display:flex;flex-wrap:wrap;gap:8px 12px;align-items:center;justify-content:space-between;margin-bottom:14px}
h2{font-size:11px;font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:.08em}
.panel-head h2{margin:0}
.panel>h2{margin-bottom:14px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(132px,1fr));gap:10px;margin-bottom:16px}
.card{background:var(--panel);border:1px solid var(--border);border-radius:var(--radius);padding:12px 14px;text-align:left;display:block;width:100%}
button.card:hover{border-color:var(--accent);background:var(--panel2)}
button.card .sub::after{content:" \203A";opacity:0;transition:opacity .15s ease}
button.card:hover .sub::after,button.card:focus-visible .sub::after{opacity:1}
.card .k{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.08em}
.card .v{font-size:24px;font-weight:600;margin-top:2px;font-variant-numeric:tabular-nums}
.card .sub{font-size:11px;color:var(--muted)}
.empty{color:var(--muted);text-align:center;padding:24px 12px;font-size:13px}
.err{color:var(--danger)}

.id-card{display:flex;gap:24px;align-items:flex-start;flex-wrap:wrap;justify-content:space-between}
.id-info{flex:1;min-width:220px}
.id-info .name{font-size:26px;font-weight:600;letter-spacing:-.01em}
.id-info .arch{color:var(--accent-text);font-size:14px}
.id-info .persona{color:var(--muted);margin-top:8px}
.chips{display:flex;gap:6px;flex-wrap:wrap;margin-top:12px}
.chip{background:var(--panel2);border:1px solid var(--border);border-radius:6px;padding:2px 10px;font-size:12px;color:var(--text)}
.chip.lock{border-color:var(--danger);color:var(--danger)}
.kv-mini .l{font-size:11px;color:var(--muted)}
.kv-mini .xv{font-size:13px;font-weight:500;margin-bottom:8px}

.two{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.two>.panel{margin-bottom:16px}

.meter{margin:8px 0}
.meter .lbl{display:flex;justify-content:space-between;font-size:12px;color:var(--muted);margin-bottom:4px}
.meter .lbl b{color:var(--text);font-weight:600;font-variant-numeric:tabular-nums}
.track{background:var(--inset);border:1px solid var(--border);border-radius:4px;height:8px;overflow:hidden}
.fill{height:100%;background:var(--accent);transition:width .4s ease}
.fill.good{background:var(--good)}.fill.info{background:var(--info)}.fill.warn{background:var(--warn)}

.ocean{display:flex;gap:28px;align-items:center;flex-wrap:wrap}
.radar-box{position:relative;flex-shrink:0}
.ocean-list{flex:1;min-width:220px}
.trait{display:grid;grid-template-columns:140px 1fr 44px;align-items:center;gap:10px;margin:8px 0;font-size:12px}
.trait .label{color:var(--muted)}
.trait .val{text-align:right;font-family:var(--mono);font-variant-numeric:tabular-nums}
.trait.hl .label{color:var(--text)}
.trait.hl .track{border-color:var(--accent)}

/* Memories */
.tools{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin-bottom:12px}
.search{flex:1;min-width:200px;background:var(--inset);border:1px solid var(--border);border-radius:6px;padding:7px 12px}
.search:focus{outline:none;border-color:var(--accent)}
.search::placeholder{color:var(--muted)}
.chipbar{display:flex;gap:6px;flex-wrap:wrap}
.fbtn{background:var(--panel2);border:1px solid var(--border);border-radius:6px;padding:3px 10px;font-size:12px;color:var(--muted)}
.fbtn:hover{color:var(--text);border-color:var(--border-strong)}
.fbtn[aria-pressed="true"]{background:var(--accent);border-color:var(--accent);color:var(--on-accent);font-weight:600}
.fbtn .n{font-family:var(--mono);font-size:11px;margin-left:4px;opacity:.8}
.sel{background:var(--inset);border:1px solid var(--border);border-radius:6px;padding:5px 8px;font-size:12px}
.range{display:flex;align-items:center;gap:8px;font-size:12px;color:var(--muted)}
.range input{accent-color:var(--accent);width:110px}
.range b{color:var(--text);font-family:var(--mono);min-width:1.5em;display:inline-block;text-align:right}
.meta-line{display:flex;justify-content:space-between;align-items:center;font-size:12px;color:var(--muted);margin-bottom:8px;gap:12px;flex-wrap:wrap}
.list{list-style:none;display:flex;flex-direction:column;gap:6px;max-height:calc(100vh - 270px);min-height:360px;overflow-y:auto;padding-right:2px}
.list li{margin:0}
.mem{display:block;width:100%;text-align:left;background:var(--inset);border:1px solid var(--border);border-radius:var(--radius);padding:10px 12px}
.mem:hover{border-color:var(--accent);background:var(--panel2)}
.mem-row{display:flex;gap:6px;align-items:center;margin-bottom:4px}
.tag{font-size:10px;text-transform:uppercase;letter-spacing:.05em;border-radius:4px;padding:1px 6px;font-weight:600;color:var(--c);background:color-mix(in srgb,var(--c) 14%,transparent);border:1px solid color-mix(in srgb,var(--c) 35%,transparent)}
.tag.episodic{--c:var(--good)}.tag.semantic{--c:var(--accent-text)}.tag.procedural{--c:var(--info)}
.tag.social{--c:var(--warn)}.tag.emotion{--c:var(--danger)}.tag.neutral{--c:var(--muted)}
.imp{margin-left:auto;font-family:var(--mono);font-size:11px;color:var(--muted)}
.mem-content{font-size:13px;word-break:break-word;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
mark{background:color-mix(in srgb,var(--accent) 30%,transparent);color:inherit;border-radius:2px}

.mini-list{list-style:none;display:flex;flex-direction:column;gap:6px}
.mini-list .mem-content{-webkit-line-clamp:2}
.skill.compact{grid-template-columns:minmax(0,1fr) 44px minmax(90px,45%);padding:8px 0}

/* Skills / evolution */
.skill{display:grid;grid-template-columns:minmax(120px,200px) 44px 1fr 96px;gap:14px;align-items:center;padding:10px 0;border-bottom:1px solid var(--border)}
.skill:last-child{border:0}
.skill .nm{font-weight:600;font-size:13px;overflow-wrap:anywhere}
.lvl{font-family:var(--mono);font-size:11px;font-weight:700;background:var(--accent);color:var(--on-accent);border-radius:4px;padding:1px 6px;text-align:center}
.skill .meter{margin:0}
.skill .dt{color:var(--muted);font-size:11px;text-align:right}
.mut{background:var(--inset);border:1px solid var(--border);border-radius:var(--radius);padding:12px;margin:8px 0}
.mut .tr{font-weight:600;color:var(--accent-text)}
.mut .ch{font-size:12px;color:var(--muted);margin-top:4px}
.mut .old{color:var(--danger);text-decoration:line-through}
.mut .new{color:var(--good)}
.mut .why{font-size:12px;color:var(--muted);margin-top:4px}
.sub-h{font-size:11px;color:var(--muted);margin:14px 0 6px}
.chartbox{position:relative}
canvas{display:block}

/* Communication */
.comm{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px}
.comm-item{background:var(--inset);border:1px solid var(--border);border-radius:var(--radius);padding:12px}
.comm-item .ck{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.08em}
.comm-item .cv{font-size:16px;font-weight:600;color:var(--accent-text);margin-top:2px}

/* Trust chain */
.tl{list-style:none;position:relative;padding-left:22px}
.tl::before{content:"";position:absolute;left:6px;top:6px;bottom:6px;width:2px;background:var(--border)}
.tl li{position:relative;margin:0 0 6px}
.tl li::before{content:"";position:absolute;left:-21px;top:12px;width:10px;height:10px;border-radius:50%;background:var(--c,var(--muted));border:2px solid var(--panel)}
.tl:has(li.none)::before,.tl li.none::before{display:none}
.tl .remember{--c:var(--good)}.tl .observe{--c:var(--info)}.tl .bond{--c:var(--accent)}.tl .graph{--c:var(--warn)}
.tl-row{display:flex;gap:10px;align-items:baseline;width:100%;text-align:left;background:none;border:1px solid transparent;border-radius:6px;padding:6px 8px;font-size:13px}
.tl-row:hover{background:var(--panel2)}
.tl-row[aria-expanded="true"]{background:var(--panel2);border-color:var(--border)}
.tl-act{font-weight:600}
.tl-time{color:var(--muted);font-size:11px;margin-left:auto;white-space:nowrap}
.tl-detail{margin:2px 0 4px;padding:8px 10px;font-size:12px;background:var(--inset);border:1px solid var(--border);border-radius:6px}
.tl-detail .hash{font-family:var(--mono);font-size:11px;word-break:break-all;color:var(--muted);margin:4px 0 8px}

.kv{display:flex;justify-content:space-between;gap:16px;padding:8px 0;border-bottom:1px solid var(--border);font-size:13px}
.kv:last-child{border:0}
.kv-list{margin-top:14px;border-top:1px solid var(--border)}
.kv-list .kv .mv{font-family:var(--sans);font-weight:500}
.kv .mk{color:var(--muted)}
.kv .mv{font-family:var(--mono);text-align:right;overflow-wrap:anywhere}

/* Modal, tooltip, toast */
.scrim{display:none;position:fixed;inset:0;background:var(--scrim);z-index:100;align-items:center;justify-content:center;padding:16px}
.scrim.open{display:flex}
.modal{background:var(--panel);border:1px solid var(--border);border-radius:12px;padding:20px 22px;max-width:580px;width:100%;max-height:85vh;overflow-y:auto;box-shadow:var(--shadow)}
.modal-head{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:12px}
.modal-head h3{font-size:15px;font-weight:600}
.modal-body-text{margin-top:14px;font-size:14px;word-break:break-word;white-space:pre-wrap}
.modal-actions{display:flex;gap:8px;margin-top:16px;flex-wrap:wrap;align-items:center}
.modal-actions .grow{flex:1}
.x{background:none;border:1px solid var(--border);border-radius:6px;width:28px;height:28px;color:var(--muted);font-size:16px;line-height:1}
.x:hover{color:var(--text);border-color:var(--border-strong)}
#tip{position:fixed;z-index:200;pointer-events:none;display:none;background:var(--panel);border:1px solid var(--border-strong);border-radius:6px;padding:5px 9px;font-size:12px;box-shadow:var(--shadow);max-width:260px}
#toast{position:fixed;bottom:20px;left:50%;transform:translateX(-50%);z-index:300;display:none;background:var(--text);color:var(--bg);border-radius:6px;padding:7px 14px;font-size:12px;font-weight:500}
.help-grid{display:grid;grid-template-columns:auto 1fr;gap:8px 16px;font-size:13px}
@media(prefers-reduced-motion:reduce){*,*::after{transition:none!important}}

@media(max-width:860px){
  .shell{grid-template-columns:1fr}
  .side{position:static;height:auto;flex-direction:row;flex-wrap:wrap;align-items:center;gap:8px 16px;padding:10px 12px;border-right:0;border-bottom:1px solid var(--border)}
  .brand{padding:0}
  .nav{flex-direction:row;overflow-x:auto;order:3;width:100%}
  .nav button{white-space:nowrap}.nav kbd{display:none}
  .side-foot{margin:0 0 0 auto;flex-direction:row;align-items:center}
  .side-label,.refresh-opts{display:none}
  .main{padding:20px 16px 48px}
  .two{grid-template-columns:1fr}
  .top-right{align-items:flex-start}
  .skill,.skill.compact{grid-template-columns:1fr 44px;gap:8px}.skill .meter,.skill .dt{grid-column:1/-1;text-align:left}
  .legal{order:4}
  .trait{grid-template-columns:110px 1fr 40px}
}
</style>
</head>
<body>
<div class="shell">
  <aside class="side">
    <div class="brand">Soul Dashboard</div>
    <nav class="nav" role="tablist" aria-label="Sections" aria-orientation="vertical">
      <button role="tab" data-tab="overview" aria-selected="true">Overview <kbd>1</kbd></button>
      <button role="tab" data-tab="memories" aria-selected="false">Memories <kbd>2</kbd></button>
      <button role="tab" data-tab="skills" aria-selected="false">Skills and Evolution <kbd>3</kbd></button>
      <button role="tab" data-tab="comms" aria-selected="false">Communication <kbd>4</kbd></button>
      <button role="tab" data-tab="trust" aria-selected="false">Trust Chain <kbd>5</kbd></button>
      <button role="tab" data-tab="meta" aria-selected="false">Metadata <kbd>6</kbd></button>
    </nav>
    <div class="side-foot">
      <div class="refresh-opts">
        <label><span>Auto Refresh</span><input type="checkbox" id="auto" checked></label>
        <label><span>Every</span>
          <select id="interval" aria-label="Refresh interval">
            <option value="10">10 s</option><option value="30" selected>30 s</option><option value="60">60 s</option><option value="300">5 min</option>
          </select>
        </label>
      </div>
      <div>
        <div class="side-label" id="theme-label">Theme</div>
        <div class="seg" id="theme" role="group" aria-labelledby="theme-label">
          <button type="button" data-pref="system" aria-pressed="false">Auto</button>
          <button type="button" data-pref="light" aria-pressed="false">Light</button>
          <button type="button" data-pref="dark" aria-pressed="false">Dark</button>
        </div>
      </div>
      <button type="button" class="btn ghost" id="help-btn">Shortcuts <span class="kbd">?</span></button>
      <nav class="legal" aria-label="Legal"><a href="/privacy">Privacy Policy</a><a href="/terms">Terms</a></nav>
    </div>
  </aside>

  <main class="main">
    <div class="top">
      <div>
        <h1 id="soul-name">Loading</h1>
        <button type="button" class="did" id="did" title="Copy DID"></button>
      </div>
      <div class="top-right">
        <div class="badges">
          <span class="badge">Mood <b id="mood">-</b></span>
          <span class="badge">Energy <b id="energy">-</b></span>
          <span class="badge">Focus <b id="focus">-</b></span>
          <span class="badge">Lifecycle <b id="lifecycle">-</b></span>
        </div>
        <div class="status">
          <span id="updated" aria-live="polite"><span class="dot"></span>Waiting</span>
          <button type="button" class="btn" id="refresh">Refresh</button>
        </div>
      </div>
    </div>

    <!-- Overview -->
    <section class="view active" id="v-overview" aria-label="Overview">
      <div class="panel">
        <div class="id-card">
          <div class="id-info">
            <div class="name" id="id-name"></div>
            <div class="arch" id="id-arch"></div>
            <div class="persona" id="id-persona"></div>
            <div class="chips" id="id-values"></div>
          </div>
          <div class="kv-mini">
            <div class="l">Born</div><div class="xv" id="id-born">-</div>
            <div class="l">Soul Age</div><div class="xv" id="id-age">-</div>
            <div class="l">Bonded To</div><div class="xv" id="id-bond">-</div>
          </div>
        </div>
      </div>
      <div class="cards" id="stats"></div>
      <div class="two">
        <div class="panel"><h2>State</h2><div id="state-bars"></div></div>
        <div class="panel"><h2>Bond</h2><div id="bond-bars"></div></div>
      </div>
      <div class="two">
        <div class="panel">
          <div class="panel-head"><h2>Top Memories</h2><button type="button" class="link" data-goto="memories">View All</button></div>
          <ul class="mini-list" id="ov-mem"></ul>
        </div>
        <div class="panel">
          <div class="panel-head"><h2>Top Skills</h2><button type="button" class="link" data-goto="skills">View All</button></div>
          <div id="ov-skills"></div>
        </div>
      </div>
      <div class="panel">
        <h2>Personality: OCEAN</h2>
        <div class="ocean">
          <div class="radar-box"><canvas id="radar" aria-label="OCEAN radar chart" role="img"></canvas></div>
          <div class="ocean-list" id="personality"></div>
        </div>
      </div>
    </section>

    <!-- Memories -->
    <section class="view" id="v-memories" aria-label="Memories">
      <div class="panel">
        <div class="panel-head"><h2>Memory Browser</h2>
          <div style="display:flex;gap:8px">
            <button type="button" class="btn ghost" id="mem-export">Export JSON</button>
          </div>
        </div>
        <div class="tools">
          <input id="search" class="search" type="search" placeholder="Search Memories (Press / to Focus)" aria-label="Search memories">
          <select id="mem-sort" class="sel" aria-label="Sort memories">
            <option value="importance">Sort: Importance</option>
            <option value="type">Sort: Type</option>
            <option value="alpha">Sort: A to Z</option>
          </select>
          <label class="range">Min Importance <input type="range" id="mem-min" min="0" max="10" value="0"><b id="mem-min-v">0</b></label>
        </div>
        <div class="chipbar" id="mem-filters" style="margin-bottom:12px"></div>
        <div class="meta-line"><span id="mem-count"></span><span>Click a memory for details. Use the arrow keys to move between memories in the detail view.</span></div>
        <ul class="list" id="mem-list"></ul>
      </div>
    </section>

    <!-- Skills -->
    <section class="view" id="v-skills" aria-label="Skills and Evolution">
      <div class="panel">
        <div class="panel-head"><h2>Skills</h2>
          <select id="skill-sort" class="sel" aria-label="Sort skills">
            <option value="level">Sort: Level</option><option value="name">Sort: Name</option><option value="recent">Sort: Recently Used</option>
          </select>
        </div>
        <div id="skills-list"></div>
      </div>
      <div class="panel">
        <h2>Evolution</h2>
        <div id="evo-info"></div>
        <div class="sub-h">Pending Mutations</div>
        <div id="mutations"></div>
      </div>
      <div class="panel">
        <h2>Evaluation History</h2>
        <div class="chartbox"><canvas id="eval-chart" aria-label="Evaluation scores" role="img"></canvas></div>
        <div class="empty" id="eval-empty" style="display:none">No Evaluations Yet</div>
      </div>
    </section>

    <!-- Communication -->
    <section class="view" id="v-comms" aria-label="Communication">
      <div class="panel"><h2>Communication Style</h2><div class="comm" id="comm-style"></div></div>
      <div class="two">
        <div class="panel"><h2>Biorhythms</h2><div id="bio-meters"></div></div>
        <div class="panel"><h2>Self-Model: Domain Confidence</h2><div id="self-model"></div></div>
      </div>
    </section>

    <!-- Trust chain -->
    <section class="view" id="v-trust" aria-label="Trust Chain">
      <div class="panel">
        <div class="panel-head"><h2>Audit Trail (<span id="tc-count">0</span> entries)</h2></div>
        <div class="tools">
          <input id="tc-search" class="search" type="search" placeholder="Filter by Action" aria-label="Filter Trust Chain by action">
        </div>
        <div class="chipbar" id="tc-filters" style="margin-bottom:12px"></div>
        <ol class="tl" id="timeline"></ol>
      </div>
    </section>

    <!-- Metadata -->
    <section class="view" id="v-meta" aria-label="Metadata">
      <div class="two">
        <div class="panel"><h2>Soul Metadata</h2><div id="meta-table"></div></div>
        <div class="panel"><h2>Memory Configuration</h2><div id="mem-config"></div></div>
      </div>
    </section>
  </main>
</div>

<div class="scrim" id="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title">
  <div class="modal">
    <div class="modal-head"><h3 id="modal-title">Memory Detail</h3><button type="button" class="x" id="modal-close" aria-label="Close">&times;</button></div>
    <div id="modal-body"></div>
    <div class="modal-actions">
      <button type="button" class="btn ghost" id="m-prev">Previous</button>
      <button type="button" class="btn ghost" id="m-next">Next</button>
      <span class="grow"></span>
      <button type="button" class="btn" id="m-copy">Copy Text</button>
    </div>
  </div>
</div>

<div class="scrim" id="help" role="dialog" aria-modal="true" aria-labelledby="help-title">
  <div class="modal">
    <div class="modal-head"><h3 id="help-title">Keyboard Shortcuts</h3><button type="button" class="x" id="help-close" aria-label="Close">&times;</button></div>
    <div class="help-grid">
      <span class="kbd">1-6</span><span>Switch Section</span>
      <span class="kbd">/</span><span>Search Memories</span>
      <span class="kbd">r</span><span>Refresh Now</span>
      <span class="kbd">t</span><span>Cycle Theme: Auto, Light, Dark</span>
      <span class="kbd">Left, Right</span><span>Previous or Next Memory in the Detail View</span>
      <span class="kbd">Esc</span><span>Close Dialog</span>
      <span class="kbd">?</span><span>Show This List</span>
    </div>
  </div>
</div>

<div id="tip" role="tooltip"></div>
<div id="toast" role="status"></div>

<script>
"use strict";
const $=(s,r=document)=>r.querySelector(s);
const $$=(s,r=document)=>Array.from(r.querySelectorAll(s));
const esc=v=>String(v==null?"":v).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c]));
const cap=s=>s?String(s).charAt(0).toUpperCase()+String(s).slice(1):"";
const titleCase=s=>s==null?"":String(s).replace(/\b\w/g,c=>c.toUpperCase());
const store={get(k,d){try{const v=localStorage.getItem("soul-dashboard-"+k);return v==null?d:v;}catch(e){return d;}},set(k,v){try{localStorage.setItem("soul-dashboard-"+k,v);}catch(e){}}};
let online=true;
async function get(u){const r=await fetch(u,{cache:"no-store"});if(!r.ok)throw new Error(r.status);return r.json();}
async function load(u){try{const d=await get(u);return d;}catch(e){online=false;return null;}}
const css=n=>getComputedStyle(document.documentElement).getPropertyValue(n).trim();
function pct(v){return Math.max(0,Math.min(100,Number(v)||0));}
function bondLabel(s){if(s>=80)return"Trusted Companion";if(s>=60)return"Close Friend";if(s>=40)return"Friend";if(s>=20)return"Acquaintance";return"Stranger";}
function ago(d){const days=Math.floor((Date.now()-new Date(d).getTime())/864e5);if(isNaN(days))return"-";if(days>365)return Math.floor(days/365)+"y "+Math.floor((days%365)/30)+"mo";if(days>30)return Math.floor(days/30)+"mo "+(days%30)+"d";return days+"d";}
function fmtDate(d){if(!d)return"-";const t=new Date(d);return isNaN(t)?esc(d):t.toLocaleDateString("en",{year:"numeric",month:"short",day:"numeric"});}
function meter(label,val,cls,right){const p=pct(val);return '<div class="meter"><div class="lbl"><span>'+esc(label)+'</span><b>'+esc(right!=null?right:Math.round(p)+"%")+'</b></div><div class="track"><div class="fill '+(cls||"")+'" style="width:'+p+'%"></div></div></div>';}
function kv(k,v){return '<div class="kv"><span class="mk">'+esc(k)+'</span><span class="mv">'+esc(v)+'</span></div>';}
function empty(t){return '<div class="empty">'+esc(t)+'</div>';}
let toastT;
function toast(t){const e=$("#toast");e.textContent=t;e.style.display="block";clearTimeout(toastT);toastT=setTimeout(()=>{e.style.display="none";},1600);}
async function copy(text,msg){try{await navigator.clipboard.writeText(text);toast(msg||"Copied");}catch(e){toast("Copy failed");}}

/* Tooltip */
const tip=$("#tip");
function showTip(x,y,html){tip.innerHTML=html;tip.style.display="block";const w=tip.offsetWidth,h=tip.offsetHeight;tip.style.left=Math.min(x+14,innerWidth-w-8)+"px";tip.style.top=Math.min(y+14,innerHeight-h-8)+"px";}
function hideTip(){tip.style.display="none";}

/* Theme */
function applyTheme(pref){
  const dark=pref==="dark"||(pref==="system"&&matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.dataset.theme=dark?"dark":"light";
  document.documentElement.dataset.pref=pref;
  $$("#theme button").forEach(b=>b.setAttribute("aria-pressed",String(b.dataset.pref===pref)));
  drawRadar();drawEval();
}
function setTheme(pref){store.set("theme",pref);applyTheme(pref);}
$$("#theme button").forEach(b=>b.addEventListener("click",()=>setTheme(b.dataset.pref)));
matchMedia("(prefers-color-scheme: dark)").addEventListener("change",()=>{if(document.documentElement.dataset.pref==="system")applyTheme("system");});
function cycleTheme(){const order=["system","light","dark"];const cur=document.documentElement.dataset.pref||"system";const next=order[(order.indexOf(cur)+1)%3];setTheme(next);toast("Theme: "+(next==="system"?"Auto":cap(next)));}

/* Navigation */
const TABS=["overview","memories","skills","comms","trust","meta"];
function showTab(name,focus){
  if(!TABS.includes(name))name="overview";
  $$(".nav button").forEach(b=>b.setAttribute("aria-selected",String(b.dataset.tab===name)));
  $$(".view").forEach(v=>v.classList.toggle("active",v.id==="v-"+name));
  if(location.hash!=="#"+name)history.replaceState(null,"","#"+name);
  store.set("tab",name);
  if(name==="overview")drawRadar();
  if(name==="skills")drawEval();
  if(focus)$(".nav button[data-tab="+name+"]").focus();
}
$$(".nav button").forEach(b=>b.addEventListener("click",()=>showTab(b.dataset.tab)));
$$("[data-goto]").forEach(b=>b.addEventListener("click",()=>showTab(b.dataset.goto)));
$(".nav").addEventListener("keydown",e=>{
  if(e.key!=="ArrowDown"&&e.key!=="ArrowUp"&&e.key!=="ArrowRight"&&e.key!=="ArrowLeft")return;
  const cur=TABS.indexOf(document.activeElement.dataset.tab);if(cur<0)return;
  const d=(e.key==="ArrowDown"||e.key==="ArrowRight")?1:-1;
  e.preventDefault();showTab(TABS[(cur+d+TABS.length)%TABS.length],true);
});

/* Dialogs */
function openDlg(id){const d=$(id);d.classList.add("open");const f=$("button",d);if(f)f.focus();}
function closeDlgs(){$$(".scrim.open").forEach(d=>d.classList.remove("open"));}
$$(".scrim").forEach(s=>s.addEventListener("click",e=>{if(e.target===s)s.classList.remove("open");}));
$("#modal-close").addEventListener("click",closeDlgs);
$("#help-close").addEventListener("click",closeDlgs);
$("#help-btn").addEventListener("click",()=>openDlg("#help"));

/* Header and identity */
let identity=null;
$("#did").addEventListener("click",()=>{const v=$("#did").textContent;if(v)copy(v,"DID copied");});
async function loadIdentity(){
  const d=await load("/api/identity");if(!d)return;identity=d;
  $("#soul-name").textContent=d.name||"";
  document.title=(d.name?d.name+" | ":"")+"Soul Dashboard";
  $("#did").textContent=d.did||"";
  $("#id-name").textContent=d.name||"";
  $("#id-arch").textContent=titleCase(d.archetype);
  $("#id-persona").textContent=cap(d.persona);
  $("#id-born").textContent=fmtDate(d.born);
  $("#id-age").textContent=d.born?ago(d.born):"-";
  $("#id-values").innerHTML=(d.core_values||[]).map(v=>'<span class="chip">'+esc(titleCase(v))+'</span>').join("");
  $("#lifecycle").textContent=d.lifecycle?titleCase(d.lifecycle):"-";
}
async function loadState(){
  const d=await load("/state");if(!d)return;
  $("#mood").textContent=d.mood?titleCase(d.mood):"Neutral";
  $("#energy").textContent=d.energy!=null?Math.round(d.energy)+"%":"-";
  $("#focus").textContent=d.focus?titleCase(d.focus):"-";
  $("#state-bars").innerHTML=meter("Energy",d.energy,"good")+meter("Social Battery",d.social_battery,"info")
    +'<div class="kv-list">'+kv("Mood",d.mood?titleCase(d.mood):"Neutral")+kv("Focus",d.focus?titleCase(d.focus):"-")+kv("Lifecycle",d.lifecycle?titleCase(d.lifecycle):"-")+'</div>';
}

/* Overview stats */
let stats=null;
async function loadStats(){
  const d=await load("/api/stats");if(!d)return;stats=d;
  const c=d.memory_counts||{},b=d.bond||{};
  const cards=[
    ["Total",c.total||0,"All Memories",""],
    ["Semantic",c.semantic||0,"Facts","semantic"],
    ["Episodic",c.episodic||0,"Events","episodic"],
    ["Procedural",c.procedural||0,"Skills","procedural"],
    ["Social",c.social||0,"People","social"],
    ["Interactions",d.interaction_count||0,"Observed",null]
  ];
  $("#stats").innerHTML=cards.map(([k,v,s,f])=>f===null
    ?'<div class="card"><div class="k">'+k+'</div><div class="v">'+esc(v)+'</div><div class="sub">'+s+'</div></div>'
    :'<button type="button" class="card" data-f="'+f+'" title="Open in memory browser"><div class="k">'+k+'</div><div class="v">'+esc(v)+'</div><div class="sub">'+s+'</div></button>').join("");
  $$("#stats button.card").forEach(c=>c.addEventListener("click",()=>{memFilter=c.dataset.f||"all";showTab("memories");renderMemories();}));
  const st=Math.round(b.strength||0);
  const next=[20,40,60,80].find(t=>st<t);
  $("#bond-bars").innerHTML=meter("Strength",st,"",st+" / 100")
    +'<div class="kv-list">'+kv("Stage",b.label?titleCase(b.label):bondLabel(st))
    +kv("Next Stage",next==null?"Highest Stage Reached":bondLabel(next)+" at "+next)
    +kv("Interactions Observed",d.interaction_count||0)+'</div>';
  $("#id-bond").textContent=b.bonded_to||"Nobody Yet";
  renderFilters();
}

/* Personality and radar */
const TRAITS=[["openness","Openness","O"],["conscientiousness","Conscientiousness","C"],["extraversion","Extraversion","E"],["agreeableness","Agreeableness","A"],["neuroticism","Neuroticism","N"]];
let ocean={},radarPts=[];
async function loadPersonality(){
  const d=await load("/api/personality");if(!d)return;ocean=d.ocean||{};
  $("#personality").innerHTML=TRAITS.map(([k,l])=>{const v=Math.round((ocean[k]||0)*100);
    return '<div class="trait" data-k="'+k+'"><div class="label">'+l+'</div><div class="track"><div class="fill" style="width:'+v+'%"></div></div><div class="val">'+v+'%</div></div>';}).join("");
  $$("#personality .trait").forEach(t=>{
    t.addEventListener("mouseenter",()=>{hlTrait=t.dataset.k;drawRadar();});
    t.addEventListener("mouseleave",()=>{hlTrait=null;drawRadar();});
  });
  drawRadar();
}
let hlTrait=null;
function fit(c,w,h){const r=window.devicePixelRatio||1;c.width=Math.round(w*r);c.height=Math.round(h*r);c.style.width=w+"px";c.style.height=h+"px";const x=c.getContext("2d");x.setTransform(r,0,0,r,0,0);return x;}
function drawRadar(){
  const c=$("#radar");if(!c)return;
  const S=Math.min(260,Math.max(200,($("#v-overview").clientWidth||260)-40));
  const ctx=fit(c,S,S),cx=S/2,cy=S/2,R=S/2-38,n=TRAITS.length,step=Math.PI*2/n;
  const accent=css("--accent"),accentText=css("--accent-text"),border=css("--border-strong"),muted=css("--muted"),text=css("--text");
  ctx.clearRect(0,0,S,S);
  ctx.lineWidth=1;ctx.strokeStyle=border;
  for(let ring=.25;ring<=1.001;ring+=.25){ctx.beginPath();for(let i=0;i<=n;i++){const a=-Math.PI/2+i*step;ctx.lineTo(cx+R*ring*Math.cos(a),cy+R*ring*Math.sin(a));}ctx.globalAlpha=ring===1?.9:.4;ctx.stroke();}
  ctx.globalAlpha=.4;
  for(let i=0;i<n;i++){const a=-Math.PI/2+i*step;ctx.beginPath();ctx.moveTo(cx,cy);ctx.lineTo(cx+R*Math.cos(a),cy+R*Math.sin(a));ctx.stroke();}
  ctx.globalAlpha=1;
  radarPts=[];
  ctx.beginPath();
  TRAITS.forEach(([k,l,s],i)=>{const a=-Math.PI/2+i*step,v=ocean[k]||0,x=cx+R*v*Math.cos(a),y=cy+R*v*Math.sin(a);radarPts.push({x,y,k,l,v});i?ctx.lineTo(x,y):ctx.moveTo(x,y);});
  ctx.closePath();ctx.globalAlpha=.2;ctx.fillStyle=accent;ctx.fill();ctx.globalAlpha=1;ctx.strokeStyle=accent;ctx.lineWidth=2;ctx.stroke();
  TRAITS.forEach(([k,l,s],i)=>{const a=-Math.PI/2+i*step,v=ocean[k]||0,p=radarPts[i];
    ctx.beginPath();ctx.arc(p.x,p.y,k===hlTrait?6:3.5,0,Math.PI*2);ctx.fillStyle=k===hlTrait?text:accentText;ctx.fill();
    ctx.fillStyle=k===hlTrait?text:muted;ctx.font=(k===hlTrait?"600 ":"")+"12px system-ui,sans-serif";ctx.textAlign="center";ctx.textBaseline="middle";
    ctx.fillText(s+" "+Math.round(v*100)+"%",cx+(R+22)*Math.cos(a),cy+(R+22)*Math.sin(a));});
}
$("#radar").addEventListener("mousemove",e=>{
  const r=e.target.getBoundingClientRect(),x=e.clientX-r.left,y=e.clientY-r.top;
  let best=null,bd=22;radarPts.forEach(p=>{const d=Math.hypot(p.x-x,p.y-y);if(d<bd){bd=d;best=p;}});
  const k=best?best.k:null;
  if(k!==hlTrait){hlTrait=k;drawRadar();$$("#personality .trait").forEach(t=>t.classList.toggle("hl",t.dataset.k===k));}
  if(best)showTip(e.clientX,e.clientY,"<b>"+esc(best.l)+"</b><br>"+Math.round(best.v*100)+"%");else hideTip();
});
$("#radar").addEventListener("mouseleave",()=>{hlTrait=null;hideTip();drawRadar();$$("#personality .trait").forEach(t=>t.classList.remove("hl"));});

/* Memories */
let allMem=[],memFilter="all",memIdx=-1,shownMem=[],modalMem=[],topMem=[];
const MEM_TYPES=["semantic","episodic","procedural","social"];
async function loadMemories(){
  const q=$("#search").value.trim();
  const d=await load("/api/memories?limit=200"+(q?"&q="+encodeURIComponent(q):""));
  allMem=d?(d.memories||[]):[];renderFilters();renderMemories();
}
async function loadTopMemories(){
  const d=await load("/api/memories?limit=5");if(!d)return;topMem=d.memories||[];
  const ul=$("#ov-mem");
  if(!topMem.length){ul.innerHTML="<li>"+empty("No Memories Yet")+"</li>";return;}
  ul.innerHTML=topMem.map((m,i)=>'<li><button type="button" class="mem" data-i="'+i+'"><div class="mem-row"><span class="tag '+esc(m.type)+'">'+esc(m.type)+'</span><span class="imp">Importance '+esc(m.importance)+'</span></div><div class="mem-content">'+esc(cap(m.content))+'</div></button></li>').join("");
  $$("#ov-mem .mem").forEach(b=>b.addEventListener("click",()=>showMem(Number(b.dataset.i),topMem)));
}
function renderFilters(){
  const counts={all:allMem.length};MEM_TYPES.forEach(t=>counts[t]=allMem.filter(m=>m.type===t).length);
  $("#mem-filters").innerHTML=["all"].concat(MEM_TYPES).map(t=>'<button type="button" class="fbtn" data-f="'+t+'" aria-pressed="'+(memFilter===t)+'">'+(t==="all"?"All":t[0].toUpperCase()+t.slice(1))+'<span class="n">'+counts[t]+'</span></button>').join("");
  $$("#mem-filters .fbtn").forEach(b=>b.addEventListener("click",()=>{memFilter=b.dataset.f;renderFilters();renderMemories();}));
}
function hl(text,q){const t=esc(text);if(!q)return t;const e=esc(q).replace(/[.*+?^${}()|[\]\\]/g,"\\$&");try{return t.replace(new RegExp("("+e+")","ig"),"<mark>$1</mark>");}catch(x){return t;}}
function renderMemories(){
  const q=$("#search").value.trim(),min=Number($("#mem-min").value),sort=$("#mem-sort").value;
  let list=allMem.filter(m=>(memFilter==="all"||m.type===memFilter)&&(Number(m.importance)||0)>=min);
  if(sort==="importance")list=list.slice().sort((a,b)=>(b.importance||0)-(a.importance||0));
  else if(sort==="type")list=list.slice().sort((a,b)=>String(a.type).localeCompare(b.type)||(b.importance||0)-(a.importance||0));
  else list=list.slice().sort((a,b)=>String(a.content).localeCompare(String(b.content)));
  shownMem=list;
  $("#mem-count").textContent=list.length+" of "+allMem.length+" memories";
  $("#mem-export").disabled=!list.length;
  const ul=$("#mem-list");
  if(!list.length){ul.innerHTML="<li>"+empty(allMem.length?"No memories match these filters":"No memories found")+"</li>";return;}
  ul.innerHTML=list.map((m,i)=>'<li><button type="button" class="mem" data-i="'+i+'"><div class="mem-row"><span class="tag '+esc(m.type)+'">'+esc(m.type)+'</span>'
    +(m.emotion?'<span class="tag emotion">'+esc(m.emotion)+'</span>':"")+'<span class="imp">Importance '+esc(m.importance)+'</span></div><div class="mem-content">'+hl(cap(m.content),q)+'</div></button></li>').join("");
  $$("#mem-list .mem").forEach(b=>b.addEventListener("click",()=>showMem(Number(b.dataset.i),shownMem)));
}
function showMem(i,list){
  if(list)modalMem=list;
  if(i<0||i>=modalMem.length)return;memIdx=i;const m=modalMem[i];
  $("#modal-title").textContent="Memory "+(i+1)+" of "+modalMem.length;
  $("#modal-body").innerHTML=[["ID",m.id],["Type",titleCase(m.type)],["Layer",titleCase(m.layer)],["Domain",titleCase(m.domain)],["Importance",m.importance],["Emotion",m.emotion?titleCase(m.emotion):"None"],["User",m.user_id||"None"]].map(([k,v])=>kv(k,v)).join("")
    +'<div class="modal-body-text">'+esc(cap(m.content))+'</div>';
  $("#m-prev").disabled=i===0;$("#m-next").disabled=i===modalMem.length-1;
  if(!$("#modal").classList.contains("open"))openDlg("#modal");
}
$("#m-prev").addEventListener("click",()=>showMem(memIdx-1));
$("#m-next").addEventListener("click",()=>showMem(memIdx+1));
$("#m-copy").addEventListener("click",()=>{const m=modalMem[memIdx];if(m)copy(m.content,"Memory copied");});
$("#mem-export").addEventListener("click",()=>{
  const blob=new Blob([JSON.stringify(shownMem,null,2)],{type:"application/json"});
  const a=document.createElement("a");a.href=URL.createObjectURL(blob);a.download=((identity&&identity.name)||"soul")+"-memories.json";document.body.appendChild(a);a.click();a.remove();URL.revokeObjectURL(a.href);
  toast("Exported "+shownMem.length+" memories");
});
let searchT;
$("#search").addEventListener("input",()=>{clearTimeout(searchT);searchT=setTimeout(loadMemories,250);});
$("#mem-sort").addEventListener("change",e=>{store.set("memsort",e.target.value);renderMemories();});
$("#mem-min").addEventListener("input",e=>{$("#mem-min-v").textContent=e.target.value;renderMemories();});

/* Skills and evolution */
let skills=[];
async function loadSkills(){const d=await load("/api/skills");if(!d)return;skills=d.skills||[];renderSkills();renderTopSkills();}
function renderSkills(){
  const s=$("#skill-sort").value,l=skills.slice();
  if(s==="level")l.sort((a,b)=>(b.level-a.level)||(b.xp-a.xp));
  else if(s==="name")l.sort((a,b)=>String(a.name).localeCompare(b.name));
  else l.sort((a,b)=>String(b.last_used||"").localeCompare(String(a.last_used||"")));
  $("#skills-list").innerHTML=l.map(k=>{const p=k.xp_to_next?Math.round(k.xp/k.xp_to_next*100):0;
    return '<div class="skill"><span class="nm">'+esc(cap(k.name))+'</span><span class="lvl">L'+esc(k.level)+'</span>'+meter("XP",p,"",k.xp+" / "+k.xp_to_next)+'<span class="dt">'+fmtDate(k.last_used)+'</span></div>';}).join("")||empty("No Skills Yet");
}
function renderTopSkills(){
  const l=skills.slice().sort((a,b)=>(b.level-a.level)||(b.xp-a.xp)).slice(0,5);
  $("#ov-skills").innerHTML=l.map(k=>{const p=k.xp_to_next?Math.round(k.xp/k.xp_to_next*100):0;
    return '<div class="skill compact"><span class="nm">'+esc(cap(k.name))+'</span><span class="lvl">L'+esc(k.level)+'</span>'+meter("XP",p,"",k.xp+" / "+k.xp_to_next)+'</div>';}).join("")||empty("No Skills Yet");
}
$("#skill-sort").addEventListener("change",e=>{store.set("skillsort",e.target.value);renderSkills();});
async function loadEvolution(){
  const d=await load("/api/evolution");if(!d)return;
  const mut=(d.mutable_traits||[]).map(t=>'<span class="chip">'+esc(cap(t))+'</span>').join("")||'<span class="sub">None</span>';
  const imm=(d.immutable_traits||[]).map(t=>'<span class="chip lock">'+esc(cap(t))+'</span>').join("")||'<span class="sub">None</span>';
  $("#evo-info").innerHTML='<div class="badges"><span class="badge">Mode <b>'+esc(titleCase(d.mode))+'</b></span><span class="badge">Rate <b>'+esc(d.mutation_rate)+'</b></span><span class="badge">Approval <b>'+(d.require_approval?"Required":"Not Required")+'</b></span></div>'
    +'<div class="sub-h">Mutable Traits</div><div class="chips" style="margin-top:0">'+mut+'</div><div class="sub-h">Immutable Traits</div><div class="chips" style="margin-top:0">'+imm+'</div>';
  $("#mutations").innerHTML=(d.pending||[]).map(m=>'<div class="mut"><div class="tr">'+esc(cap(m.trait))+'</div><div class="ch"><span class="old">'+esc(m.old_value)+'</span> to <span class="new">'+esc(m.new_value)+'</span></div><div class="why">'+esc(cap(m.reason))+'</div></div>').join("")||empty("No Pending Mutations");
}
let evals=[],evalBars=[];
async function loadEvaluations(){const d=await load("/api/evaluations");if(!d)return;evals=d.evaluations||[];drawEval();}
function drawEval(){
  const c=$("#eval-chart"),none=$("#eval-empty");if(!c)return;
  c.style.display=evals.length?"block":"none";none.style.display=evals.length?"none":"block";
  if(!evals.length)return;
  const box=c.parentElement,W=Math.max(260,box.clientWidth||600),H=220,padL=40,padB=28,padT=14;
  if(!box.clientWidth)return;
  const ctx=fit(c,W,H);ctx.clearRect(0,0,W,H);
  const border=css("--border-strong"),muted=css("--muted"),accent=css("--accent");
  const n=evals.length,gap=6,bw=Math.max(6,Math.min(64,(W-padL-10)/n-gap)),max=Math.max(1,...evals.map(e=>e.overall_score||0));
  ctx.strokeStyle=border;ctx.lineWidth=1;ctx.fillStyle=muted;ctx.font="11px system-ui,sans-serif";ctx.textAlign="right";ctx.textBaseline="middle";
  [0,.5,1].forEach(f=>{const y=H-padB-f*(H-padB-padT);ctx.globalAlpha=.4;ctx.beginPath();ctx.moveTo(padL,y);ctx.lineTo(W-6,y);ctx.stroke();ctx.globalAlpha=1;ctx.fillText(Math.round(f*max*100)+"%",padL-6,y);});
  evalBars=[];
  evals.forEach((e,i)=>{const h=((e.overall_score||0)/max)*(H-padB-padT),x=padL+8+i*(bw+gap),y=H-padB-h;
    ctx.fillStyle=accent;ctx.fillRect(x,y,bw,h);evalBars.push({x,y,w:bw,h,e,i});
    if(n<=24){ctx.fillStyle=muted;ctx.textAlign="center";ctx.textBaseline="top";ctx.fillText(String(i+1),x+bw/2,H-padB+6);}});
}
$("#eval-chart").addEventListener("mousemove",e=>{
  const r=e.target.getBoundingClientRect(),x=e.clientX-r.left,y=e.clientY-r.top;
  const b=evalBars.find(b=>x>=b.x-3&&x<=b.x+b.w+3&&y>=b.y-6);
  if(!b){hideTip();return;}
  showTip(e.clientX,e.clientY,"<b>Evaluation "+(b.i+1)+"</b><br>Score "+Math.round((b.e.overall_score||0)*100)+"%"+(b.e.rubric_id?"<br>"+esc(b.e.rubric_id):"")+(b.e.timestamp?"<br>"+fmtDate(b.e.timestamp):"")+(b.e.learning?"<br>"+esc(b.e.learning):""));
});
$("#eval-chart").addEventListener("mouseleave",hideTip);

/* Communication */
async function loadComms(){
  const d=await load("/api/communication");if(!d)return;
  $("#comm-style").innerHTML=[["Warmth",d.warmth],["Verbosity",d.verbosity],["Humor",d.humor_style],["Emoji Usage",d.emoji_usage]].map(([k,v])=>'<div class="comm-item"><div class="ck">'+k+'</div><div class="cv">'+esc(titleCase(v))+'</div></div>').join("");
  const b=d.biorhythms||{};
  $("#bio-meters").innerHTML='<div class="meter"><div class="lbl"><span>Chronotype</span><b>'+esc(b.chronotype?titleCase(b.chronotype):"-")+'</b></div></div>'
    +meter("Mood Inertia",(b.mood_inertia||0)*100,"warn")+meter("Mood Sensitivity",(b.mood_sensitivity||0)*100,"warn");
}
async function loadSelfModel(){
  const d=await load("/api/self-model");if(!d)return;
  const e=Object.entries(d.self_images||{}).sort((a,b)=>(b[1].confidence||0)-(a[1].confidence||0));
  $("#self-model").innerHTML=e.map(([k,v])=>{const p=Math.round(pct((v.confidence||0)*100));return '<div class="trait" title="'+esc(v.evidence_count||0)+' Pieces of Evidence"><div class="label">'+esc(titleCase(k))+'</div><div class="track"><div class="fill" style="width:'+p+'%"></div></div><div class="val">'+p+'%</div></div>';}).join("")||empty("No Self-Model Data Yet");
}

/* Trust chain */
let chain=[],chainFilter="all",chainOpen=new Set();
function chainKind(a){const k=String(a||"").split(".")[0];return["remember","observe","bond","graph"].includes(k)?k:"other";}
async function loadTrust(){const d=await load("/api/trust-chain");if(!d)return;chain=d.entries||[];$("#tc-count").textContent=d.total||chain.length;renderTrust();}
function renderTrust(){
  const kinds=["all","remember","observe","bond","graph","other"],q=$("#tc-search").value.trim().toLowerCase();
  const cnt={all:chain.length};kinds.slice(1).forEach(k=>cnt[k]=chain.filter(e=>chainKind(e.action)===k).length);
  $("#tc-filters").innerHTML=kinds.filter(k=>k==="all"||cnt[k]).map(k=>'<button type="button" class="fbtn" data-k="'+k+'" aria-pressed="'+(chainFilter===k)+'">'+k[0].toUpperCase()+k.slice(1)+'<span class="n">'+cnt[k]+'</span></button>').join("");
  $$("#tc-filters .fbtn").forEach(b=>b.addEventListener("click",()=>{chainFilter=b.dataset.k;renderTrust();}));
  const list=chain.filter(e=>(chainFilter==="all"||chainKind(e.action)===chainFilter)&&(!q||String(e.action).toLowerCase().includes(q)));
  $("#timeline").innerHTML=list.map(e=>{const open=chainOpen.has(e.seq),h=String(e.hash||"");
    return '<li class="'+chainKind(e.action)+'"><button type="button" class="tl-row" data-s="'+esc(e.seq)+'" aria-expanded="'+open+'"><span class="tl-act">'+esc(cap(e.action))+'</span><span class="tl-time">'+fmtDate(e.timestamp)+'</span></button>'
      +(open?'<div class="tl-detail"><div>Sequence <b>'+esc(e.seq)+'</b>, Algorithm <b>'+esc(e.algorithm||"-")+'</b></div><div class="hash">'+esc(h)+'</div><button type="button" class="btn ghost" data-h="'+esc(h)+'">Copy Hash</button></div>':"")+'</li>';}).join("")||'<li class="none">'+empty(chain.length?"No entries match this filter":"No trust chain entries")+'</li>';
  $$("#timeline .tl-row").forEach(b=>b.addEventListener("click",()=>{const s=Number(b.dataset.s);chainOpen.has(s)?chainOpen.delete(s):chainOpen.add(s);renderTrust();}));
  $$("#timeline [data-h]").forEach(b=>b.addEventListener("click",()=>copy(b.dataset.h,"Hash copied")));
}
$("#tc-search").addEventListener("input",renderTrust);

/* Metadata */
async function loadMeta(){
  const d=await load("/api/metadata");if(!d)return;
  $("#meta-table").innerHTML=[["Version",d.version],["DID",d.did],["Lifecycle",titleCase(d.lifecycle)],["Incarnation",d.incarnation],["Encrypted",d.encrypted?"Yes":"No"]].map(([k,v])=>kv(k,v)).join("");
  const m=d.memory_config||{};
  $("#mem-config").innerHTML=[["Max Episodic",m.episodic_max_entries],["Max Semantic",m.semantic_max_facts],["Importance Threshold",m.importance_threshold],["Consolidation Interval",m.consolidation_interval]].map(([k,v])=>kv(k,v==null?"-":v)).join("");
}

/* Refresh loop */
let busy=false,timer=null;
async function refresh(manual){
  if(busy)return;busy=true;online=true;
  const btn=$("#refresh");btn.disabled=true;
  await Promise.all([loadIdentity(),loadState(),loadStats(),loadPersonality(),loadMemories(),loadTopMemories(),loadSkills(),loadEvolution(),loadEvaluations(),loadComms(),loadSelfModel(),loadTrust(),loadMeta()]);
  $("#updated").innerHTML='<span class="dot'+(online?"":" off")+'"></span>'+(online?"Updated "+new Date().toLocaleTimeString():"Connection lost, retrying");
  btn.disabled=false;busy=false;
  if(manual&&online)toast("Refreshed");
}
function schedule(){
  clearInterval(timer);timer=null;
  if(!$("#auto").checked)return;
  timer=setInterval(()=>{if(!document.hidden)refresh();},Number($("#interval").value)*1000);
}
$("#refresh").addEventListener("click",()=>refresh(true));
$("#auto").addEventListener("change",e=>{store.set("auto",e.target.checked?"1":"0");schedule();});
$("#interval").addEventListener("change",e=>{store.set("interval",e.target.value);schedule();});
document.addEventListener("visibilitychange",()=>{if(!document.hidden&&$("#auto").checked)refresh();});
addEventListener("resize",()=>{drawRadar();drawEval();});
addEventListener("hashchange",()=>showTab(location.hash.slice(1)));

/* Keyboard */
addEventListener("keydown",e=>{
  if(e.metaKey||e.ctrlKey||e.altKey)return;
  const typing=/^(INPUT|SELECT|TEXTAREA)$/.test(document.activeElement.tagName);
  if(e.key==="Escape"){if($$(".scrim.open").length){closeDlgs();}else if(typing){document.activeElement.blur();}return;}
  if($("#modal").classList.contains("open")){
    if(e.key==="ArrowLeft"){showMem(memIdx-1);}else if(e.key==="ArrowRight"){showMem(memIdx+1);}
    return;
  }
  if(typing)return;
  if(e.key>="1"&&e.key<="6"){showTab(TABS[Number(e.key)-1]);}
  else if(e.key==="/"){e.preventDefault();showTab("memories");$("#search").focus();}
  else if(e.key==="r"){refresh(true);}
  else if(e.key==="t"){cycleTheme();}
  else if(e.key==="?"){openDlg("#help");}
});

/* Init */
$("#auto").checked=store.get("auto","1")==="1";
$("#interval").value=store.get("interval","30");
$("#mem-sort").value=store.get("memsort","importance");
$("#skill-sort").value=store.get("skillsort","level");
applyTheme(document.documentElement.dataset.pref||"system");
showTab(location.hash.slice(1)||store.get("tab","overview"));
schedule();
refresh();
</script>
</body>
</html>
"""
