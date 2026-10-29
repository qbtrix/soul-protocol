# gateway/_legal.py - Favicon plus the Privacy Policy and Terms and Conditions
#   pages served alongside the Soul dashboard (GET /favicon.svg, /privacy, /terms).
# Created: 2026-10 - Static HTML that follows the dashboard's saved theme. Copy
#   only states what the gateway actually does: binds to 127.0.0.1 by default,
#   has no auth, and only sends data off the machine via /v1/chat/completions.

FAVICON_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
    '<rect width="32" height="32" rx="7" fill="#059669"/>'
    '<circle cx="16" cy="16" r="8" fill="none" stroke="#ffffff" stroke-width="3"/>'
    '<circle cx="16" cy="16" r="2.5" fill="#ffffff"/>'
    "</svg>"
)

_TEMPLATE = r"""<!doctype html>
<html lang="en" data-theme="dark">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__ | Soul Dashboard</title>
<link rel="icon" type="image/svg+xml" href="/favicon.svg">
<script>
(function(){
  var pref='system';
  try{pref=localStorage.getItem('soul-dashboard-theme')||'system';}catch(e){}
  var dark=pref==='dark'||(pref==='system'&&window.matchMedia('(prefers-color-scheme: dark)').matches);
  document.documentElement.dataset.theme=dark?'dark':'light';
})();
</script>
<style>
:root{--bg:#09090b;--panel:#0f0f12;--border:#27272a;--text:#fafafa;--muted:#a1a1aa;--accent-text:#34d399;color-scheme:dark}
:root[data-theme="light"]{--bg:#fafafa;--panel:#ffffff;--border:#e4e4e7;--text:#18181b;--muted:#52525b;--accent-text:#047857;color-scheme:light}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;background:var(--bg);color:var(--text);line-height:1.65;font-size:15px}
main{max-width:760px;margin:0 auto;padding:40px 24px 72px}
a{color:var(--accent-text)}
a:focus-visible{outline:2px solid var(--accent-text);outline-offset:2px}
.back{display:inline-block;font-size:13px;margin-bottom:28px;text-decoration:none}
.back:hover{text-decoration:underline}
h1{font-size:28px;font-weight:600;letter-spacing:-.01em}
.eff{color:var(--muted);font-size:13px;margin:6px 0 28px}
h2{font-size:17px;font-weight:600;margin:28px 0 8px}
p,ul{margin:0 0 12px}
ul{padding-left:20px}
li{margin:4px 0}
code{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:13px;background:var(--panel);border:1px solid var(--border);border-radius:4px;padding:0 5px}
footer{margin-top:40px;padding-top:16px;border-top:1px solid var(--border);font-size:13px;display:flex;gap:16px}
footer a{color:var(--muted)}
</style>
</head>
<body>
<main>
<a class="back" href="/dashboard">Back to Dashboard</a>
<h1>__TITLE__</h1>
<p class="eff">Effective October 1, 2026</p>
__BODY__
<footer><a href="/privacy">Privacy Policy</a><a href="/terms">Terms and Conditions</a></footer>
</main>
</body>
</html>
"""

_PRIVACY_BODY = """
<p>The Soul Dashboard is part of Soul Protocol, open source software that you run yourself.
This page explains what data the dashboard and the Soul gateway handle and where that data goes.</p>

<h2>Where Your Data Lives</h2>
<p>All soul data, including identity, memories, personality, skills, bond and trust chain entries,
is stored in the soul file on the machine running the gateway. The project maintainers do not
operate a server for this dashboard and do not receive any of this data.</p>

<h2>What the Dashboard Reads</h2>
<p>The dashboard only reads from the gateway's own read-only endpoints (<code>/state</code> and
<code>/api/*</code>). It does not change your soul. The Export JSON button saves a file through
your browser; nothing is uploaded.</p>

<h2>Browser Storage</h2>
<p>The dashboard stores your display preferences in your browser's local storage under keys
beginning with <code>soul-dashboard-</code>: theme, last opened section, sort orders and
auto refresh settings. It sets no cookies and loads no analytics, trackers, third party scripts
or web fonts.</p>

<h2>Data Sent to Other Services</h2>
<p>The dashboard itself sends no data off your machine. The gateway's
<code>/v1/chat/completions</code> endpoint is different: when you use it, your messages and
relevant recalled memories are forwarded to the language model provider configured in
<code>SOUL_LLM_BASE_URL</code> (default <code>https://api.openai.com/v1</code>). That provider's
own privacy policy applies to that data.</p>

<h2>Network Access</h2>
<p>By default the gateway listens on <code>127.0.0.1</code>, so only your own machine can reach it.
The gateway has no built in authentication. If you bind it to another address, anyone who can
reach that address can read your soul data.</p>

<h2>Keeping and Deleting Data</h2>
<p>Data stays in your soul file until you remove it. Deleting the soul file removes the data.
To clear dashboard preferences, clear this site's local storage in your browser.</p>

<h2>Changes and Contact</h2>
<p>Changes to this policy are published with the software. Questions can be raised on the
<a href="https://github.com/qbtrix/soul-protocol/issues">project issue tracker</a>.</p>
"""

_TERMS_BODY = """
<p>These terms apply to your use of the Soul Dashboard and the Soul gateway, which are part of
Soul Protocol.</p>

<h2>License</h2>
<p>Soul Protocol is released under the MIT License. You may use, copy, modify and distribute it
under that license. The full license text is in the <code>LICENSE</code> file distributed with
the software.</p>

<h2>No Warranty</h2>
<p>The software is provided "as is", without warranty of any kind, express or implied. The
authors and copyright holders are not liable for any claim, damages or other liability arising
from the software or its use, as set out in the MIT License.</p>

<h2>Your Responsibilities</h2>
<ul>
<li>You are responsible for the content stored in your soul and for having the right to store it.</li>
<li>You are responsible for securing the machine and network the gateway runs on. The gateway
has no built in authentication.</li>
<li>If you connect the gateway to a language model provider, you must follow that provider's terms.</li>
</ul>

<h2>Third Party Services</h2>
<p>Soul Protocol does not control language model providers or any other service you configure,
and is not responsible for how they handle your data.</p>

<h2>Changes</h2>
<p>These terms may be updated in future releases of the software. Questions can be raised on the
<a href="https://github.com/qbtrix/soul-protocol/issues">project issue tracker</a>.</p>
"""


def _page(title: str, body: str) -> str:
    return _TEMPLATE.replace("__TITLE__", title).replace("__BODY__", body)


PRIVACY_HTML = _page("Privacy Policy", _PRIVACY_BODY)
TERMS_HTML = _page("Terms and Conditions", _TERMS_BODY)
