"""The single notes page (served at `/`) and the CSS shared with the login page.

Built from DOM calls only: note text and tags are inserted with `textContent` / `value`,
never as HTML. The server ranks the results; the highlighting here is cosmetic.
UI text lives in `i18n.py`: `[[key]]` markers are filled in on the server, the script reads the
same strings from the embedded `I18N` object.
"""

import html
import re
from collections.abc import Mapping
from urllib.parse import quote

from compass.ui import core
from compass.ui.chatpanel import CHAT_CSS, CHAT_JS
from compass.ui.editor import EDITOR_CSS, EDITOR_PURE_JS, EDITOR_UI_JS
from compass.ui.i18n import STRINGS
from compass.ui.reader import READER_CSS, READER_PURE_JS, READER_UI_JS

# The tab icon: the logo (compass on the brand gradient) as an inline SVG data URI, so the page
# still makes no external request and needs no extra route.
_FAVICON_SVG = (
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'>"
    "<defs><linearGradient id='g' x1='0' y1='0' x2='1' y2='1'>"
    "<stop offset='0' stop-color='#477bff'/><stop offset='1' stop-color='#765bff'/></linearGradient></defs>"
    "<rect width='32' height='32' rx='8' fill='url(#g)'/>"
    "<g transform='translate(5 5) scale(.917)' fill='none' stroke='white' stroke-width='2' "
    "stroke-linecap='round' stroke-linejoin='round'><circle cx='12' cy='12' r='10'/>"
    "<polygon points='16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76'/></g></svg>"
)
FAVICON_LINK = (
    '<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,'
    + quote(_FAVICON_SVG, safe="/:='")
    + '">'
)

COMMON_CSS = r"""
:root{
  --bg:#101116; --side:#151722; --panel:#1b1d2a; --raise:#222538; --line:rgba(255,255,255,.07); --line-strong:rgba(99,125,255,.85);
  --accent:#5275ff; --accent-2:#795cff; --accent-light:#7295ff; --accent-soft:rgba(82,117,255,.16);
  --ink:#f5f5fa; --muted:#a3a5b5; --faint:#777b90; --mark:rgba(121,92,255,.38); --ok:#22c55e; --danger:#f87171; --danger-soft:rgba(248,113,113,.12);
  --grad:linear-gradient(135deg,#477bff,#765bff); --r:14px; --shadow:0 1px 2px rgba(0,0,0,.4),0 12px 32px rgba(0,0,0,.35);
  --sk-a:#222538; --sk-b:#30354d;
  --ai1:#a855f7; --ai2:#ec4899; --ai-soft:rgba(168,85,247,.14);
  --glow:0 0 0 1px rgba(99,125,255,.55),0 8px 30px rgba(82,117,255,.22); --ease:.18s ease-out;
}
:root[data-theme=light]{
  --bg:#f4f5fa; --side:#ffffff; --panel:#ffffff; --raise:#eef0f8; --line:rgba(20,24,50,.09); --line-strong:rgba(82,117,255,.9);
  --accent:#4263eb; --accent-light:#4263eb; --accent-soft:rgba(82,117,255,.12); --ink:#16182a; --muted:#5b5f75; --faint:#8a8ea3;
  --sk-a:#e8eaf4; --sk-b:#f6f7fc; --mark:rgba(255,214,10,.45); --ok:#15803d; --danger:#dc2626; --danger-soft:rgba(220,38,38,.08);
  --shadow:0 1px 2px rgba(20,24,50,.05),0 12px 32px rgba(20,24,50,.08); --glow:0 0 0 1px rgba(82,117,255,.5),0 8px 26px rgba(82,117,255,.16);
}
.aiframe,.scard.aiframe{border-radius:16px;border:1.5px solid transparent;background:linear-gradient(var(--panel),var(--panel)) padding-box,linear-gradient(135deg,var(--ai1),var(--ai2)) border-box}
.aitag{display:inline-flex;align-items:center;gap:4px;font-size:10.5px;font-weight:700;letter-spacing:.06em;line-height:1.5;padding:1px 8px;border-radius:999px;color:#fff;background:linear-gradient(135deg,var(--ai1),var(--ai2));vertical-align:middle}
.aitag .ic,.aitag svg{color:#fff!important}
.logo .aitag{margin-left:6px}
.aipad{margin:16px 14px 20px;overflow:hidden}
.aipad .aihd{flex-wrap:wrap}.aihd .grow{flex:1}
.aibody{padding:0}.aipad .aierr{padding:16px 18px;font-size:14px}
.aithink{display:flex;flex-direction:column;align-items:center;gap:12px;padding:40px 18px;color:var(--muted);font-size:14px}
.aithink svg{color:var(--ai1);animation:aipulse 1.4s ease-in-out infinite}
@keyframes aipulse{0%,100%{transform:scale(.8) rotate(0);opacity:.55}50%{transform:scale(1.15) rotate(20deg);opacity:1}}
@media (prefers-reduced-motion:reduce){.aithink svg{animation:none}}
.aihd{display:flex;align-items:center;gap:10px;padding:12px 16px;background:var(--ai-soft);font-size:13px;font-weight:600;color:var(--ink)}
.aihd .ic,.aihd svg{color:var(--ai1)}
.aistrip{display:flex;align-items:center;gap:8px;flex-wrap:wrap;padding:12px 22px 0}
.aistrip .grow{flex:1}
.aibtn{padding:7px 13px;font-size:13px;gap:7px;border-radius:999px;border:1.5px solid transparent;color:var(--ink);background:linear-gradient(var(--panel),var(--panel)) padding-box,linear-gradient(135deg,var(--ai1),var(--ai2)) border-box}
.aibtn:hover,.aibtn.act{background:linear-gradient(var(--raise),var(--raise)) padding-box,linear-gradient(135deg,var(--ai1),var(--ai2)) border-box}
.aibtn svg{color:var(--ai1)}
.aibtn.act{box-shadow:0 0 0 3px var(--ai-soft)}
.sumwrap{padding:14px 22px 0}
.aisum .aihd{flex-wrap:wrap;row-gap:8px}
.aihd>svg{flex:none}
.aisum .aihd .btn{padding:5px 10px;font-size:12px}
.aisum .aihd .btn.icon{padding:5px 8px}
.aisum .stale{font-size:11px;font-weight:600;padding:3px 9px;border-radius:999px;background:var(--danger-soft);color:var(--danger);white-space:nowrap}
.aisum .chev svg{transition:transform var(--ease)}
.aisum.collapsed .chev svg{transform:rotate(-90deg)}
.aisum.collapsed>:not(.aihd){display:none}
.aisum .aithink{flex-direction:row;padding:14px 18px;gap:10px}
.aisum .aisumbody{padding:14px 18px 16px;font-size:14.5px;line-height:1.65}
.aisum .aisumbody h1,.aisum .aisumbody h2,.aisum .aisumbody h3{margin:14px 0 4px;padding:0;border:0;font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:.06em;color:var(--faint)}
.aisum .aisumbody>:first-child{margin-top:0}
.aisum .aisumbody p,.aisum .aisumbody ul,.aisum .aisumbody ol{margin:0 0 4px}
*{box-sizing:border-box}
html{color-scheme:dark}
html[data-theme=light]{color-scheme:light}
body{margin:0;font-family:Inter,Geist,system-ui,-apple-system,"Segoe UI",sans-serif;background:var(--bg);color:var(--ink);font-size:14px;line-height:1.5;-webkit-font-smoothing:antialiased}
button{font:inherit;cursor:pointer;color:inherit}
input,textarea,select{font:inherit;color:var(--ink)}
[hidden]{display:none!important}
mark{background:var(--mark);color:inherit;border-radius:4px;padding:0 2px}
kbd{font-family:ui-monospace,"JetBrains Mono",monospace;font-size:11px;border:1px solid var(--line);border-radius:6px;padding:1px 6px;color:var(--muted);background:rgba(255,255,255,.04)}
.krow{display:flex;justify-content:space-between;align-items:center;gap:16px;padding:12px 20px;border-bottom:1px solid var(--line)}
.krow:last-child{border-bottom:0}
.keys{display:flex;gap:6px;align-items:center;flex:none}
dialog{border:1px solid var(--line);border-radius:20px;padding:22px;width:min(520px,calc(100% - 32px));background:var(--panel);color:var(--ink);box-shadow:var(--shadow)}
dialog::backdrop{background:rgba(5,6,12,.6);backdrop-filter:blur(2px)}
.dlg-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:14px}
.dlg-head h3{margin:0;font-size:18px}
.kdlg h3{margin:0;font-size:18px}.kdlg .krow:first-of-type{border-top:1px solid var(--line)}.kdlg .krow{padding:10px 4px}
.kdlg .kfoot{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-top:14px}
.sidepair{display:flex;gap:6px}.sidepair .sidebtn:first-child{flex:1}
.muted{color:var(--muted)}
.ic{display:inline-flex;align-items:center;justify-content:center;flex:none}
.btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;border:1px solid var(--line);background:var(--panel);color:var(--ink);border-radius:12px;padding:8px 14px;font-size:13px;font-weight:500;transition:background var(--ease),border-color var(--ease),transform var(--ease),filter var(--ease)}
.btn:hover{border-color:rgba(99,125,255,.5);background:var(--raise)}
.btn:active{transform:translateY(1px)}
.btn:focus-visible,.chip:focus-visible,.res:focus-visible,.catlist .cat:focus-visible,.linkbtn:focus-visible{outline:2px solid var(--accent-light);outline-offset:2px}
.btn.primary{background:var(--grad);border-color:transparent;color:#fff;box-shadow:0 6px 18px rgba(82,117,255,.28)}
.btn.primary:hover{filter:brightness(1.1);background:var(--grad)}
.btn.danger{border-color:rgba(248,113,113,.45);color:var(--danger);background:transparent}
.btn.danger:hover{background:var(--danger-soft);border-color:var(--danger)}
.btn.icon{padding:8px 11px}
.btn.on{background:var(--grad);border-color:transparent;color:#fff;font-weight:600}
.langs{display:flex;gap:6px}
.chip{display:inline-flex;align-items:center;gap:6px;border:1px solid var(--line);background:rgba(255,255,255,.03);color:var(--ink);border-radius:999px;padding:4px 12px;font-size:13px;transition:background var(--ease),border-color var(--ease),color var(--ease)}
.chip:hover{border-color:rgba(99,125,255,.5);background:var(--accent-soft)}
.chip.on{background:var(--grad);border-color:transparent;color:#fff;box-shadow:0 4px 14px rgba(82,117,255,.3)}
.chip .n{display:inline-grid;place-items:center;min-width:22px;height:20px;padding:0 6px;border-radius:999px;background:rgba(255,255,255,.08);color:var(--muted);font-size:11px}
.chip.on .n{background:rgba(255,255,255,.22);color:#fff}
.chip.ghost{border-style:dashed;color:var(--muted)}
.chip.mini{font-size:12px;padding:2px 10px;border-color:transparent;background:color-mix(in srgb,var(--ink) 8%,transparent);color:var(--muted)}
.chip.mini.on{background:var(--grad);color:#fff;border-color:transparent}
.chips{display:flex;flex-wrap:wrap;gap:8px}
.badge{display:inline-flex;align-items:center;font-size:11px;font-weight:600;border-radius:999px;padding:1px 9px;border:1px solid var(--line);color:var(--muted)}
.badge.cat{color:var(--accent-light);border-color:rgba(99,125,255,.4);background:var(--accent-soft)}
.panel .meta{font-size:12px;color:var(--muted)}
.panel h2{margin:4px 0 10px;font-size:24px;letter-spacing:-.01em}
.panel .actions,.panel .confirm,.panel .row{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.panel .confirm{background:var(--danger-soft);border:1px solid rgba(248,113,113,.5);border-radius:12px;padding:12px 14px;margin-top:14px}
.panel .confirm.warn{background:var(--accent-soft);border-color:rgba(99,125,255,.5)}
.form{display:grid;gap:8px}
.form label{font-size:11px;font-weight:600;color:var(--faint);text-transform:uppercase;letter-spacing:.06em;margin-top:8px}
.form input,.form textarea,.form select{width:100%;border:1px solid var(--line);border-radius:12px;padding:10px 12px;background:var(--bg);transition:border-color var(--ease),box-shadow var(--ease)}
.form input:focus,.form textarea:focus,.form select:focus{outline:0;border-color:var(--line-strong);box-shadow:0 0 0 3px var(--accent-soft)}
.form textarea{min-height:160px;resize:vertical;line-height:1.6}
.err{color:var(--danger);font-size:13px;min-height:1em}
.empty{color:var(--muted);text-align:center;padding:40px 14px}
.aiveil{position:fixed;inset:0;z-index:50;backdrop-filter:blur(6px);-webkit-backdrop-filter:blur(6px);background:color-mix(in srgb,var(--bg) 40%,transparent)}
.toast{position:fixed;bottom:22px;left:50%;transform:translateX(-50%) translateY(6px);background:var(--raise);color:var(--ink);border:1px solid var(--line);box-shadow:var(--shadow);padding:9px 18px;border-radius:999px;font-size:13px;opacity:0;transition:opacity .2s ease-out,transform .2s ease-out;pointer-events:none;z-index:60}
.toast.show{opacity:1;transform:translateX(-50%)}
.toast.ok{border-color:rgba(34,197,94,.45);color:var(--ok)}
.toast.bad{border-color:rgba(248,113,113,.5);color:var(--danger)}
.login{min-height:100vh;display:grid;place-items:center;padding:20px;background:radial-gradient(900px 500px at 70% -10%,rgba(82,117,255,.14),transparent),var(--bg)}
.login .card{width:min(380px,100%);background:var(--panel);border:1px solid var(--line);border-radius:20px;padding:28px;box-shadow:var(--shadow)}
.login h1{margin:0 0 4px;font-size:22px}
.logo{display:flex;align-items:center;gap:12px;font-weight:700;font-size:20px;letter-spacing:-.01em}
.logo .dot{width:40px;height:40px;border-radius:12px;background:var(--grad);display:grid;place-items:center;color:#fff;font-size:20px;box-shadow:0 6px 18px rgba(82,117,255,.35)}
.protonote{font-size:12px;color:var(--muted);border-left:3px solid var(--accent);padding-left:10px;margin-top:14px}
.sk{display:block;flex:none;max-width:100%;border-radius:8px;background:linear-gradient(100deg,var(--sk-a) 30%,var(--sk-b) 50%,var(--sk-a) 70%);background-size:240% 100%;animation:shimmer 1.7s ease-in-out infinite}
.sk.round{border-radius:50%}
.sk.pill{border-radius:999px}
@keyframes shimmer{from{background-position:120% 0}to{background-position:-120% 0}}
@media (prefers-reduced-motion:reduce){*,*::before,*::after{transition:none!important;animation:none!important}}
.sidebtn{margin-top:4px;justify-content:center;background:rgba(255,255,255,.03);padding:10px 12px;border-radius:12px}
.newbtn{padding:13px 14px;border-radius:14px;font-size:14px;font-weight:600}
.logo .dot svg{display:block}
.tagline{font-size:12px;font-weight:400;color:var(--faint);line-height:1.2;margin-top:3px}
"""

APP_CSS = r"""
body{overflow:hidden}
.app{display:grid;grid-template-columns:250px minmax(0,1fr);height:100vh}
aside{scrollbar-width:thin;scrollbar-color:rgba(128,132,160,.35) transparent;background:var(--side);border-right:1px solid var(--line);padding:22px 16px 16px;overflow:auto;display:flex;flex-direction:column;gap:4px;scrollbar-width:thin}
aside .logo{margin-bottom:20px}
.wide{width:100%}
h4{display:flex;justify-content:space-between;align-items:center;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.07em;color:var(--faint);margin:22px 4px 8px}
.legend{list-style:none;margin:0;padding:0;font-size:12.5px;display:grid;gap:10px}
.legend li{display:flex;gap:12px;align-items:flex-start;line-height:1.35}
.legend .ic{color:var(--accent-light);margin-top:1px}
aside>*{flex:none}
aside>.spacer{flex:1 0 12px}
.sep{border-top:1px solid var(--line);margin:20px 0 0}
.sep+h4{margin-top:18px}
.row{display:flex;gap:8px;align-items:center}
.row form{margin:0}
a.btn{text-decoration:none}
.msg{font-size:12px;min-height:1em;margin-top:2px}
.msg.ok{color:var(--ok)}
.msg.bad{color:var(--danger)}
main{display:flex;flex-direction:column;min-width:0;height:100vh;padding:18px 24px 0 22px;background:radial-gradient(1100px 520px at 75% -12%,rgba(82,117,255,.11),transparent 70%),radial-gradient(700px 500px at 0% 100%,rgba(121,92,255,.06),transparent 70%),var(--bg)}
.topbar{display:flex;gap:12px;align-items:center}
.menubtn{display:none}
.searchbar{flex:1;display:flex;align-items:center;gap:12px;height:50px;background:linear-gradient(180deg,var(--panel),var(--side));border:1px solid var(--line);border-radius:16px;padding:0 14px;color:var(--muted);transition:border-color var(--ease),box-shadow var(--ease)}
.btn.aibtn.askbtn{position:relative;flex:none;border:1.5px solid transparent;border-radius:12px;padding:7px 14px;font-weight:600;background:linear-gradient(var(--panel),var(--panel)) padding-box,linear-gradient(135deg,var(--ai1),var(--ai2)) border-box;box-shadow:0 2px 12px rgba(168,85,247,.28)}
.btn.aibtn.askbtn:hover{background:linear-gradient(var(--raise),var(--raise)) padding-box,linear-gradient(135deg,var(--ai1),var(--ai2)) border-box}
.askbtn .aitag{position:absolute;top:-9px;right:-7px;font-size:9px;padding:0 6px;gap:3px;box-shadow:0 1px 4px rgba(0,0,0,.35)}
.askbtn[hidden]{display:none}
.searchbar:focus-within{border-color:var(--line-strong);box-shadow:0 0 0 3px var(--accent-soft)}
.searchbar input{flex:1;min-width:0;border:0;outline:0;background:none;font-size:15.5px}
.searchbar input::placeholder{color:var(--faint)}
.filters{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:14px 2px 12px}
.pill{display:inline-flex;align-items:center;gap:7px;border:1px solid var(--line);background:rgba(255,255,255,.03);border-radius:999px;padding:5px 13px;font-size:12.5px;color:var(--muted);transition:background var(--ease),border-color var(--ease),color var(--ease)}
.pill:hover{border-color:rgba(99,125,255,.5);color:var(--ink)}
.pill.on{background:var(--grad);border-color:transparent;color:#fff}
.hint{margin-left:auto;color:var(--faint);opacity:.75;font-size:12px;display:flex;gap:14px;flex-wrap:wrap}
.grid{flex:1;min-height:0;display:grid;grid-template-columns:minmax(300px,455px) minmax(0,1fr);gap:20px}
.listcol,.detailcol{min-height:0;overflow:auto;padding:2px 4px 22px 2px;scrollbar-width:thin;scrollbar-color:rgba(128,132,160,.35) transparent}
.count{color:var(--muted);font-size:13px;margin:0 4px}
.listhead{display:flex;justify-content:space-between;align-items:center;gap:10px;margin:0 0 10px}
.sortsel{display:inline-flex;align-items:center;gap:6px;flex:none;border:1px solid var(--line);border-radius:999px;padding:2px 6px 2px 10px;color:var(--muted);background:rgba(255,255,255,.03);transition:border-color var(--ease),color var(--ease)}
.sortsel:hover,.sortsel:focus-within{border-color:rgba(99,125,255,.5);color:var(--ink)}
.sortsel.on{border-color:rgba(99,125,255,.55);color:var(--accent-light);background:var(--accent-soft)}
.sortsel select{border:0;background:none;color:inherit;font-size:12.5px;padding:3px 2px;cursor:pointer;outline:0;max-width:170px}
.sortsel select option{background:var(--panel);color:var(--ink)}
.withbtn{display:flex;justify-content:space-between;align-items:center}
.linkbtn{text-decoration:none;display:inline-flex;align-items:center;gap:6px;border:0;background:none;color:var(--muted);font-size:12px;padding:0;text-transform:none;letter-spacing:0;font-weight:500}
.linkbtn:hover{color:var(--accent-light)}
.catlist{display:flex;flex-direction:column;gap:2px;flex:none;position:relative;overflow:hidden;transition:max-height .22s ease-out}
.catlist .cat{display:flex;justify-content:space-between;align-items:center;gap:8px;width:100%;border:1px solid transparent;background:none;padding:5px 10px;border-radius:10px;font-size:13px;text-align:left;color:var(--muted);transition:background var(--ease),color var(--ease)}
.catlist .cat:hover{background:rgba(255,255,255,.04);color:var(--ink)}
.catlist .cat.on{background:var(--accent-soft);color:var(--ink);border-color:rgba(99,125,255,.35);font-weight:600}
.catlist .cat .n{color:var(--faint);font-size:12px;font-weight:400}
.catfield{display:grid;gap:8px}
.qrow{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.tagbar{gap:6px;flex:none;position:relative;overflow:hidden;transition:max-height .22s ease-out}
.moretags{display:flex;align-items:center;gap:6px;margin:10px auto 0;border:0;background:none;color:var(--muted);font-size:12px}
.moretags:hover{color:var(--ink)}
.moretags .ic{transition:transform .22s ease-out}
.moretags.open .ic{transform:rotate(180deg)}
.results{display:flex;flex-direction:column;gap:10px}
.res{position:relative;display:grid;grid-template-columns:40px minmax(0,1fr) 16px;gap:13px;align-items:start;width:100%;text-align:left;padding:14px 16px;border-radius:16px;border:1px solid var(--line);background:linear-gradient(180deg,var(--panel),color-mix(in srgb,var(--panel) 80%,var(--bg)));color:var(--ink);transition:transform var(--ease),border-color var(--ease),background var(--ease),box-shadow var(--ease)}
.res:hover{transform:translateY(-1px);border-color:rgba(255,255,255,.16);background:var(--raise)}
.res.on{border-color:var(--line-strong);box-shadow:var(--glow);background:var(--raise)}
.res .ico{width:40px;height:40px;border-radius:12px;display:grid;place-items:center;background:var(--accent-soft);color:var(--accent-light)}
.res .top{display:flex;justify-content:space-between;gap:10px;align-items:baseline}
.res .t{font-weight:600;font-size:15.5px;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.res .date{color:var(--faint);font-size:12px;white-space:nowrap}
.res .s{color:var(--muted);font-size:13.5px;line-height:1.45;margin:2px 0 9px;display:-webkit-box;-webkit-line-clamp:1;-webkit-box-orient:vertical;overflow:hidden}
.searching .res .s{-webkit-line-clamp:2}
.res .meta{display:flex;gap:6px;flex-wrap:wrap;align-items:center;overflow:hidden;max-height:25px}
.res .meta>*{flex:none}
.res .badge.cat{border-color:transparent;background:none;padding-left:0;color:var(--accent-light);font-weight:600}
.res .chev{color:var(--faint);opacity:.55;margin-top:2px;transition:opacity var(--ease),transform var(--ease)}
.res:hover .chev,.res.on .chev{opacity:1;transform:translateX(2px)}
.skcard{display:grid;grid-template-columns:40px minmax(0,1fr);gap:13px;padding:14px 16px;border-radius:16px;border:1px solid var(--line);background:var(--panel)}
.skbody{display:grid;gap:9px;min-width:0}
.sktop{display:flex;justify-content:space-between;align-items:center;gap:12px}
.sktags{display:flex;gap:6px;margin-top:2px}
.skhero{padding:20px 26px 38px;background:linear-gradient(135deg,#232857,#171b3e)}
.skhero .sk{background:linear-gradient(100deg,rgba(255,255,255,.07) 30%,rgba(255,255,255,.15) 50%,rgba(255,255,255,.07) 70%);background-size:240% 100%}
.skhero .sktags{margin-top:14px}
.sklines{display:grid;gap:12px;padding:26px}
.reveal .res{animation:fadein .2s ease-out both}
@keyframes fadein{from{opacity:0;transform:translateY(3px)}to{opacity:1;transform:none}}
.card{background:var(--panel);border:1px solid var(--line);border-radius:20px;overflow:hidden;overflow:clip;box-shadow:var(--shadow);animation:rise .2s ease-out}
@keyframes rise{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:none}}
.panel[data-mode=edit],.panel[data-mode=del],.panel[data-mode=confirm],.panel.pad{padding:24px 26px}
.card:has(.panel[data-mode=read]){border-color:rgba(255,255,255,.08);background:radial-gradient(560px 340px at 100% 0%,rgba(112,92,255,.5),transparent 72%),radial-gradient(460px 320px at 85% 38%,rgba(66,104,240,.22),transparent 72%),linear-gradient(180deg,#1b1f46 0%,#161a38 38%,#12142a 100%)}
.hero{position:relative;padding:20px 26px 38px;color:#fff}
.hero .wave{position:absolute;right:0;top:0;width:78%;height:100%;pointer-events:none}
.hero>*:not(.wave){position:relative}
.hero .bar{display:flex;justify-content:space-between;gap:10px;align-items:center;margin-bottom:16px}
.hero .left{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.hero .datebadge{display:inline-flex;gap:8px;align-items:center;background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.12);border-radius:999px;padding:5px 12px;font-size:12.5px;color:#e6e8ff}
.hero .badge.cat{background:rgba(255,255,255,.1);border-color:rgba(255,255,255,.18);color:#e6e8ff}
.hero .iconbtn{width:36px;height:36px;display:grid;place-items:center;border:1px solid rgba(255,255,255,.14);background:rgba(255,255,255,.08);border-radius:12px;color:#fff;transition:background var(--ease)}
.hero .iconbtn:hover{background:rgba(255,255,255,.18)}
.hero .iconbtn.back{display:none}
.hero .tools{display:flex;gap:8px}
.hero .iconbtn.del:hover{background:rgba(248,113,113,.28);border-color:rgba(248,113,113,.6)}
.hero h2{margin:0 0 14px;font-size:29px;font-weight:700;letter-spacing:-.02em;line-height:1.2;overflow-wrap:anywhere}
.hero .chip{background:rgba(255,255,255,.1);border-color:rgba(255,255,255,.14);color:#fff}
.hero .chip:hover{background:rgba(255,255,255,.2)}
.hero .chip.on{background:var(--grad);border-color:transparent}
.sheet{position:relative;margin-top:-16px;border-radius:22px 22px 0 0;border-top:1px solid rgba(255,255,255,.1);background:rgba(12,14,30,.6);backdrop-filter:blur(8px);min-height:120px}
:root[data-theme=light] .sheet{background:var(--panel)}
.panel .actions{padding:14px 26px 26px}
.panel .err{padding:0 26px}
.panel[data-mode=edit] .err,.panel.pad .err{padding:0}
@media (max-width:1200px){.app{grid-template-columns:220px minmax(0,1fr)}.grid{grid-template-columns:minmax(260px,380px) minmax(0,1fr)}.hint{display:none}}
@media (max-width:900px){
  .app{grid-template-columns:1fr}
  aside{position:fixed;left:0;top:0;bottom:0;width:270px;z-index:40;transform:translateX(-100%);transition:transform .2s ease-out;box-shadow:var(--shadow)}
  .app.menu aside{transform:none}
  .scrim{position:fixed;inset:0;background:rgba(5,6,12,.55);z-index:30}
  .menubtn{display:inline-flex}
  #shortcut{display:none}
  .askbtn{padding:7px 10px}.askbtn .asklbl{display:none}
  main{padding:14px 14px 0}
  .grid{grid-template-columns:1fr}
  .app[data-view=detail] .listcol,.app:not([data-view=detail]) .detailcol{display:none}
  .hero .iconbtn.back{display:grid}
  .hero{padding:16px 18px 18px}
  .hero h2{font-size:24px}
  .panel .body,.panel .actions,.panel .err{padding-left:18px;padding-right:18px}
}
"""

INDEX_HTML = (
    r"""<!doctype html>
<html lang="[[lang]]" data-theme="dark">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Compass</title>
"""
    + FAVICON_LINK
    + r"""
<style>"""
    + COMMON_CSS
    + APP_CSS
    + READER_CSS
    + EDITOR_CSS
    + CHAT_CSS
    + r"""</style>
</head>
<body>"""
    + r"""
<div class="app" id="app" data-view="list">
  <aside id="side">
    <div class="logo"><div class="dot"><span class="ic" data-icon="compass" data-size="22"></span></div><div><div>Compass <span class="aitag" data-ai hidden><span class="ic" data-icon="spark" data-size="10"></span>AI</span></div><div class="tagline">[[tagline]]</div></div></div>
    <button type="button" class="btn primary wide newbtn" id="new">[[new_note]]</button>
    <h4><span>[[categories_h]]</span><a class="linkbtn" href="/settings#categories" title="[[manage_title]]">[[manage_categories]]<span class="ic" data-icon="settings" data-size="15"></span></a></h4>
    <div class="catlist" id="catbar"></div>
    <button type="button" class="moretags" id="catmore" hidden><span id="catmoretext"></span><span class="ic" data-icon="chevron-down" data-size="15"></span></button>
    <h4><span>[[tags_h]]</span><a class="linkbtn" href="/settings#tags" title="[[tags_manage_title]]">[[manage_categories]]<span class="ic" data-icon="settings" data-size="15"></span></a></h4>
    <div class="chips tagbar" id="tagbar"></div>
    <button type="button" class="moretags" id="tagmore" hidden><span id="tagmoretext"></span><span class="ic" data-icon="chevron-down" data-size="15"></span></button>
    <div class="sep"></div>
    <h4><span>[[how_h]]</span></h4>
    <ul class="legend muted">
      <li><span class="ic" data-icon="search"></span><span>[[legend1]]</span></li>
      <li><span class="ic" data-icon="zap"></span><span>[[legend2]]</span></li>
      <li><span class="ic" data-icon="star"></span><span>[[legend3]]</span></li>
    </ul>
    <div class="spacer"></div>
    <div class="sidepair"><a class="btn sidebtn" href="/settings"><span class="ic" data-icon="cog"></span>[[settings_title]]</a><button type="button" class="btn sidebtn" id="kbbtn" aria-label="[[sc_help]]" title="[[sc_help]]"><span class="ic" data-icon="keyboard"></span></button></div>
    <form method="post" action="/logout"><button class="btn wide sidebtn"><span class="ic" data-icon="logout"></span>[[logout]]</button></form>
  </aside>
  <div class="scrim" id="scrim" hidden></div>
  <main>
    <div class="readbar" id="readbar">
      <span class="lbl"><span class="ic" data-icon="book" data-size="16"></span>[[reading_mode]]</span>
      <div class="rtools">
        <button type="button" class="btn" id="r-smaller" aria-label="[[font_smaller]]" title="[[font_smaller]]">A−</button>
        <button type="button" class="btn" id="r-larger" aria-label="[[font_larger]]" title="[[font_larger]]">A+</button>
        <button type="button" class="btn icon" id="r-width" aria-label="[[width_toggle]]" title="[[width_toggle]]"><span class="ic" data-icon="move-h" data-size="16"></span></button>
        <button type="button" class="btn" id="r-exit" aria-label="[[reading_exit]]" title="[[reading_exit]]"><kbd>Esc</kbd>[[reading_exit]]</button>
      </div>
    </div>
    <div class="topbar">
      <button type="button" class="btn icon menubtn" id="menu" aria-label="[[menu_open]]"><span class="ic" data-icon="menu"></span></button>
      <div class="searchbar"><span class="ic" data-icon="search" data-size="20"></span><input id="q" placeholder="[[search_ph]]" autocomplete="off" autofocus><kbd id="shortcut">/</kbd><button type="button" class="btn aibtn askbtn" id="chatbtn" data-ai hidden aria-label="[[chat_btn]]" title="[[chat_btn]]"><span class="ic" data-icon="chat-compass" data-size="18"></span><span class="asklbl">[[chat_btn]]</span><span class="aitag"><span class="ic" data-icon="spark" data-size="9"></span>AI</span></button></div>
    </div>
    <div class="filters">
      <button type="button" class="pill" id="f-all"><span class="ic" data-icon="layers" data-size="14"></span>[[category_all]]</button>
      <button type="button" class="pill" id="f-clear"><span class="ic" data-icon="filter-x" data-size="14"></span>[[filter_clear]]</button>
      <div class="hint"><span><kbd>↑</kbd><kbd>↓</kbd> [[hint_select]]</span><span><kbd>N</kbd> [[hint_new]]</span><span><kbd>Esc</kbd> [[hint_clear]]</span></div>
    </div>
    <div class="grid">
      <div class="listcol">
        <div class="listhead">
          <div class="count" id="count"></div>
          <label class="sortsel" id="sortbox" title="[[sort_label]]"><span class="ic" data-icon="sort" data-size="14"></span><select id="sort" aria-label="[[sort_label]]"></select></label>
        </div>
        <div class="results" id="results"></div>
      </div>
      <div class="detailcol" id="detail"></div>
    </div>
  </main>
</div>
<div class="toast" id="toast" role="status"></div>
"""
    + r"""<script>"""
    + r"""
/*CORE*/
/*READER_PURE*/
/*EDITOR_PURE*/

// --- text helpers, used only to highlight matches (the server does the searching and ranking)
const fold1 = (c) => (c.length > 1 ? c : c === "ł" || c === "Ł" ? "l" : c.normalize("NFD")[0].toLowerCase());
const fold = (s) => Array.from(s).map(fold1).join("");
const words = (s) => fold(s).match(/[\p{L}\p{N}]+/gu) || [];
const limitFor = (n) => (n < 4 ? 0 : n < 8 ? 1 : 2);
function dist(a, b, k) {            // optimal string alignment; an adjacent swap is one edit
  if (Math.abs(a.length - b.length) > k) return k + 1;
  let before = null, row = Array.from({length: b.length + 1}, (_, j) => j);
  for (let i = 1; i <= a.length; i++) {
    const cur = [i];
    for (let j = 1; j <= b.length; j++) {
      let v = Math.min(row[j] + 1, cur[j - 1] + 1, row[j - 1] + (a[i - 1] !== b[j - 1] ? 1 : 0));
      if (before && i > 1 && j > 1 && a[i - 1] === b[j - 2] && a[i - 2] === b[j - 1]) v = Math.min(v, before[j - 2] + 1);
      cur[j] = v;
    }
    if (Math.min(...cur) > k) return k + 1;
    before = row; row = cur;
  }
  return row[b.length];
}
function hlNodes(text, tokens) {     // marks prefix and typo hits; builds text nodes, never HTML
  const f = fold(text), marks = [];
  if (tokens.length) for (const m of f.matchAll(/[\p{L}\p{N}]+/gu)) {
    for (const t of tokens) {
      const w = m[0], k = limitFor(t.length);
      if (w === t || w.startsWith(t)) { marks.push([m.index, m.index + Math.min(t.length, w.length)]); break; }
      if (k && Math.abs(w.length - t.length) <= k && dist(t, w, k) <= k) { marks.push([m.index, m.index + w.length]); break; }
    }
  }
  const out = []; let last = 0;
  for (const [a, b] of marks) { if (a < last) continue; out.push(text.slice(last, a), h("mark", {}, text.slice(a, b))); last = b; }
  out.push(text.slice(last));
  return out;
}
function readTags(v) {               // "SQL, Soft  Skills" -> ["soft skills", "sql"]; limits match the server
  const tags = [...new Set(v.split(",").map((t) => t.trim().toLowerCase().replace(/\s+/g, " ")).filter(Boolean))].sort((a, b) => a.localeCompare(b, "pl"));
  const error = tags.some((t) => t.length > 30) ? tr("tag_long", {n: 30}) : tags.length > 10 ? tr("tag_many", {n: 10}) : "";
  return {tags, error};
}
const TOPICS = [[/rozmow|interview|soft/, "message"], [/\bgit\b/, "branch"], [/algorytm|algorithm|big o/, "binary"], [/sql|baz|database|data/, "database"],
  [/statyst|mediana|wartosc p/, "chart"], [/kod|code|program|api|docker|devops|rest/, "code"], [/nauk|learn|biolog|fotosint/, "book"], [/pomysl|idea|wskazowk/, "star"]];
const noteIcon = (note) => { const hay = fold(note.title + " " + note.tags.join(" ")); const hit = TOPICS.find(([re]) => re.test(hay)); return hit ? hit[1] : "file"; };
const shortDate = (iso) => new Date(iso).toLocaleDateString(LANG, {day: "numeric", month: "short"});
const longDate = (iso) => new Date(iso).toLocaleDateString(LANG, {day: "numeric", month: "short", year: "numeric"});

/*READER_UI*/
/*EDITOR_UI*/
/*CHAT_UI*/
// --- state and server calls
const state = {q: "", sel: new Set(), category: null, cur: null, mode: "view", list: [], tags: [], categories: [], total: 0, reading: false, sort: ""};
let seq = 0, timer;
const tokens = () => words(state.q);
const SAVE_ERROR = tr("save_error");

const defaultId = () => (state.categories.find((c) => c.default) || {id: 1}).id;
const catLabel = (c) => (c.default ? tr("category_default") : c.name);
const catName = (id) => { const c = state.categories.find((x) => x.id === id); return c ? catLabel(c) : ""; };
async function loadCategories() {
  state.categories = await (await api("/api/categories")).json();
  if (state.category !== null && !state.categories.some((c) => c.id === state.category)) state.category = null;
  renderCategories();
}

async function loadTags() {
  state.tags = await (await api("/api/tags")).json();
  for (const t of [...state.sel]) if (!state.tags.some((x) => x.name === t)) state.sel.delete(t);
  renderTagbar();
}
const setView = (v) => { $("#app").dataset.view = v; };
function showLoadError() {
  $("#count").textContent = "";
  $("#results").replaceChildren(h("div", {class: "empty"}, h("div", {}, tr("load_failed")), h("button", {type: "button", class: "btn", style: "margin-top:12px", onclick: () => load()}, tr("retry"))));
  if (state.mode === "view") $("#detail").replaceChildren(h("div", {class: "card"}, h("div", {class: "empty"}, tr("load_failed"))));
}
// --- skeleton loading: one block (`sk`) and a few variants built from it; shown only while we really wait
const SK_CARDS = [{t: 58, a: 92, b: 64, tags: [54, 70, 46]}, {t: 72, a: 84, b: 52, tags: [62, 48]}, {t: 46, a: 96, b: 70, tags: [44, 66, 58]},
  {t: 64, a: 78, b: 40, tags: [58, 52, 72]}, {t: 52, a: 90, b: 58, tags: [66, 46]}, {t: 68, a: 82, b: 48, tags: [50, 60, 44]}];
function skeletonCard(i) {
  const v = SK_CARDS[i % SK_CARDS.length];
  return h("div", {class: "skcard", "aria-hidden": "true"}, sk("40px", 40, "round"),
    h("div", {class: "skbody"}, h("div", {class: "sktop"}, sk(v.t + "%", 15), sk("36px", 10)), sk(v.a + "%", 11), sk(v.b + "%", 11),
      h("div", {class: "sktags"}, v.tags.map((w) => sk(w + "px", 20, "pill")))));
}
function skeletonPanel() {
  return h("div", {class: "card skdetail", "aria-hidden": "true"},
    h("div", {class: "skhero"}, h("div", {class: "sktop"}, sk("170px", 28, "pill"), sk("120px", 36, "pill")), h("div", {style: "margin-top:18px"}, sk("64%", 30)),
      h("div", {class: "sktags"}, sk("58px", 26, "pill"), sk("92px", 26, "pill"), sk("70px", 26, "pill"))),
    h("div", {class: "sheet"}, h("div", {class: "sklines"}, sk("96%"), sk("88%"), sk("92%"), sk("60%"), sk("100%", 96))));
}
let skTimer = 0, skShown = false, loaded = false;
function showSkeleton(withPanel) {
  skShown = true;
  $("#results").setAttribute("aria-busy", "true");
  $("#results").replaceChildren(...[0, 1, 2, 3, 4, 5].map(skeletonCard));
  if (withPanel && state.mode === "view") $("#detail").replaceChildren(skeletonPanel());
}
function loadingStarted() {            // first load: at once; later loads: only if the answer is slow (no flicker)
  clearTimeout(skTimer);
  if (!loaded) showSkeleton(true); else skTimer = setTimeout(() => showSkeleton(false), 350);
}
function loadingDone() {               // true when a skeleton was on screen, so the real cards should fade in
  clearTimeout(skTimer);
  $("#results").removeAttribute("aria-busy");
  const was = skShown; skShown = false;
  return was;
}
async function load(keepDetail = false) {
  const mine = ++seq, had = state.cur;
  const params = new URLSearchParams({q: state.q});
  for (const t of state.sel) params.append("tag", t);
  if (state.category !== null) params.set("category_id", state.category);
  if (state.sort) params.set("sort", state.sort);
  let list;
  loadingStarted();
  try {
    const r = await api("/api/notes?" + params);
    if (!r.ok) throw new Error("load");
    list = await r.json();
  } catch (e) {
    if (mine === seq && e.message !== "not authenticated") { loadingDone(); loaded = false; showLoadError(); }
    return;
  }
  if (mine !== seq) return;
  const reveal = loadingDone();
  loaded = true;
  state.total = state.categories.reduce((sum, c) => sum + c.count, 0);
  state.list = list;
  if (state.mode === "view" && !list.some((n) => n.id === state.cur)) state.cur = list.length ? list[0].id : null;
  renderList();
  if (reveal) { $("#results").classList.add("reveal"); setTimeout(() => $("#results").classList.remove("reveal"), 400); }
  if (!keepDetail || had !== state.cur || reveal) renderDetail();
}
function toggleCategory(id) { state.category = state.category === id ? null : id; renderCategories(); load(); }
function toggleTag(t) { state.sel.has(t) ? state.sel.delete(t) : state.sel.add(t); renderTagbar(); load(); }
function openNew() { state.mode = "new"; state.cur = null; setView("detail"); renderList(); renderDetail(); }
function select(id) { state.cur = id; state.mode = "view"; setView("detail"); renderList(); renderDetail(); }
function resetFilters(all) { state.sel.clear(); state.category = null; if (all) { state.q = ""; $("#q").value = ""; } state.mode = "view"; renderTagbar(); renderCategories(); load(); }

// --- rendering
function renderFilters() {
  const none = state.sel.size === 0 && state.category === null;
  $("#f-all").classList.toggle("on", none);
}
const CAT_PREVIEW = 6;
let catsOpen = false;
function renderCategories() {
  renderFilters();
  const total = state.categories.reduce((sum, c) => sum + c.count, 0);
  const entry = (label, count, on, handler) => h("button", {type: "button", class: "cat" + (on ? " on" : ""), onclick: handler}, h("span", {}, label), h("span", {class: "n"}, count));
  $("#catbar").replaceChildren(
    entry(tr("category_all"), total, state.category === null, () => { state.category = null; renderCategories(); load(); }),
    ...state.categories.map((c) => entry(catLabel(c), c.count, state.category === c.id, () => toggleCategory(c.id))));
  fitList("cat", CAT_PREVIEW + 1, catsOpen);   // +1: the "All" entry
}
const TAG_PREVIEW = 9;
let tagsOpen = false;
// Collapsed: the first `preview` items; open: everything. The height change is animated (tags and categories alike).
function fitList(name, preview, open) {
  const bar = $("#" + name + "bar"), more = $("#" + name + "more"), kids = bar.children, many = kids.length > preview;
  more.hidden = !many;
  more.classList.toggle("open", open);
  $("#" + name + "moretext").textContent = open ? tr("tags_less") : tr("tags_more");
  if (!many) { bar.style.maxHeight = ""; return; }
  const last = kids[preview - 1];
  bar.style.maxHeight = (open ? bar.scrollHeight : last.offsetTop + last.offsetHeight) + "px";
}
const fitTags = () => fitList("tag", TAG_PREVIEW, tagsOpen);
function renderTagbar() {
  renderFilters();
  $("#tagbar").replaceChildren(...state.tags.map((t) => h("button", {type: "button", class: "chip" + (state.sel.has(t.name) ? " on" : ""), onclick: () => toggleTag(t.name)}, "#" + t.name, h("span", {class: "n"}, t.count))));
  fitTags();
}
function categoryBadge(id) {          // the default category is not shown on cards (less noise)
  const c = state.categories.find((x) => x.id === id);
  return c && !c.default ? h("span", {class: "badge cat"}, c.name) : null;
}
// A card shows the start of the text without Markdown markers; the note itself is never changed.
const snippet = (body) => body.replace(/^\s*>\s*\[!\w+\]\s*/gm, "").replace(/```\w*/g, " ").replace(/^\s*#{1,6}\s+/gm, "").replace(/\*\*|__|~~|`/g, "").replace(/\s+/g, " ").trim().slice(0, 160);
function renderList() {
  const tk = tokens(), n = state.list.length;
  $("#results").classList.toggle("searching", !!state.q);   // one line of text per card, two while searching so the match shows
  $("#count").textContent = n === 50 ? tr("top50") : n + " " + T.count[new Intl.PluralRules(LANG).select(n)] + (state.category !== null ? " • " + catName(state.category) : "") + (state.sel.size ? " • " + [...state.sel].map((t) => "#" + t).join(" ") : "");
  const none = !n && !state.q && !state.sel.size && state.category === null && state.total === 0;
  $("#results").replaceChildren(...(n ? state.list.map((note) => h("button", {type: "button", class: "res" + (note.id === state.cur && state.mode === "view" ? " on" : ""), onclick: () => select(note.id)},
    h("div", {class: "ico"}, icon(noteIcon(note), 20)),
    h("div", {},
      h("div", {class: "top"}, h("span", {class: "t"}, hlNodes(note.title, tk)), h("span", {class: "date"}, shortDate(note.created_at))),
      h("div", {class: "s"}, hlNodes(snippet(note.body), tk)),
      h("div", {class: "meta"}, categoryBadge(note.category_id), note.tags.map((t) => h("span", {class: "chip mini" + (state.sel.has(t) ? " on" : ""), onclick: (e) => { e.stopPropagation(); toggleTag(t); }}, "#" + t)))),
    h("span", {class: "chev"}, icon("chevron-right", 16)))) : [h("div", {class: "empty"}, tr(none ? "empty_none" : "no_results"))]));
}
let chat = null;      // the chat panel, made on first use and kept: opening a source note must not lose the conversation
function openChat() {
  if (!AI_READY) return;
  chat = chat || makeChat({openNote: openSource, close: closeChat});
  exitReading(); state.mode = "chat"; setView("detail"); renderList(); renderDetail(); chat.show();
}
function closeChat() { state.mode = "view"; setView("list"); renderList(); renderDetail(); }   // the panel is kept: "Ask" brings the conversation back
async function openSource(id, title) {       // a note named in an answer: found through its title, so it is in the (limited) list
  state.q = title; $("#q").value = title; state.sel.clear(); state.category = null; state.mode = "view"; state.cur = id;
  setView("detail"); renderTagbar(); renderCategories(); await load();
}
function renderDetail() {
  const d = $("#detail");
  if (state.mode === "chat") { d.replaceChildren(h("div", {class: "card chatcard"}, chat.el)); return; }
  if (state.mode === "new") {
    exitReading();
    d.replaceChildren(h("div", {class: "card"}, newPanel({
      onCancel: () => { state.mode = "view"; setView("list"); load(); },
      onCreated: async (n) => { state.q = ""; $("#q").value = ""; state.sel.clear(); state.category = null; state.mode = "view"; state.cur = n.id; await loadCategories(); await loadTags(); await load(); toast(tr("toast_created")); }})));
    return;
  }
  const n = state.list.find((x) => x.id === state.cur);
  if (!n) exitReading();
  if (!n) { d.replaceChildren(h("div", {class: "card"}, h("div", {class: "empty"}, tr("pick_or_add")))); return; }
  d.replaceChildren(h("div", {class: "card"}, notePanel(n, {
    onChange: async () => { await loadCategories(); await loadTags(); await load(true); toast(tr("toast_saved")); },
    onDeleted: async () => { state.cur = null; setView("list"); await loadCategories(); await loadTags(); await load(); toast(tr("toast_deleted")); }})));
}

// --- forms and the note panel (edit and delete each need a second, explicit confirmation)
function suggestions(input) {
  return h("div", {class: "chips"}, state.tags.slice(0, 24).map((t) => h("button", {type: "button", class: "chip ghost", onclick: () => {
    const have = readTags(input.value).tags;
    if (!have.includes(t.name)) input.value = have.concat(t.name).join(", ");
    input.focus();
  }}, t.name)));
}
// A <select> of the categories plus a quick way to add one without leaving the form.
function categoryField(selectedId) {
  const select = h("select", {"aria-label": tr("label_category")});
  const fill = (id) => { select.replaceChildren(...state.categories.map((c) => h("option", {value: String(c.id)}, catLabel(c)))); select.value = String(id); };
  fill(selectedId);
  const err = h("div", {class: "err"});
  const name = h("input", {placeholder: tr("category_new_ph"), maxlength: 60, autocomplete: "off"});
  const quick = h("div", {class: "qrow", hidden: true});
  const close = () => { quick.hidden = true; name.value = ""; err.textContent = ""; };
  async function add() {
    err.textContent = "";
    const r = await api("/api/categories", json("POST", {name: name.value}));
    const body = (await r.json().catch(() => null)) || {};
    if (r.status === 201) { await loadCategories(); fill(body.id); }
    else if (r.status === 409 && body.detail && body.detail.code === "name_taken") fill(body.detail.id);   // already exists: just use it
    else { err.textContent = categoryError(body.detail); return; }
    close(); select.focus();
  }
  name.addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); e.stopPropagation(); add(); }
    else if (e.key === "Escape") { e.stopPropagation(); close(); select.focus(); }
  });
  quick.append(name, h("button", {type: "button", class: "btn primary", onclick: add}, tr("category_add")), h("button", {type: "button", class: "btn", onclick: () => { close(); select.focus(); }}, tr("cancel")));
  const row = h("div", {class: "qrow"}, select, h("button", {type: "button", class: "btn", onclick: () => { quick.hidden = false; name.focus(); }}, tr("category_new")));
  select.style.flex = "1";
  return {el: h("div", {class: "catfield"}, row, quick, err), value: () => Number(select.value)};
}
function noteForm(init, message) {
  const title = h("input", {value: init.title, maxlength: 200, placeholder: tr("label_title")});
  const body = h("textarea", {value: init.body, placeholder: tr("label_body"), maxlength: 20000});
  const mdHint = h("div", {class: "hint2"}, tr("md_hint"));
  const editor = markdownEditor(body);        // the toolbar and the preview tab around the same textarea
  const tags = h("input", {value: init.tags.join(", "), placeholder: tr("label_tags"), autocomplete: "off"});
  const category = categoryField(init.category_id);
  const err = h("div", {class: "err"}, message);
  const el = h("div", {class: "form"}, h("label", {}, tr("label_title")), title, h("label", {}, tr("label_body")), editor.el, mdHint, h("label", {}, tr("label_tags")), tags, suggestions(tags), h("label", {}, tr("label_category")), category.el, err);
  return {el, err, focus: () => title.focus(), values() {
    const t = readTags(tags.value), ti = title.value.trim();
    err.textContent = !ti ? tr("empty_title") : t.error;
    return err.textContent ? null : {title: ti, body: body.value, tags: t.tags, category_id: category.value()};
  }};
}
async function copyNote(note) {
  try { await navigator.clipboard.writeText(note.title + "\n\n" + note.body); toast(tr("copied")); }
  catch (e) { toast(tr("copy_failed")); }
}
function notePanel(note, cb) {
  const root = h("div", {class: "panel"});
  let mode = "read", draft = null, msg = "";
  let preview = null, sum = null, tjob = 0, sjob = 0, swapped = false;    // preview: the translation, shown in place of the note: {state: "loading"|"done"|"error", text, msg}; swapped: the user turned its direction around; sum: the summary, shown above the note: {state, text, msg, collapsed}; the counters drop a late answer
  const dropAi = () => { tjob++; sjob++; preview = null; sum = null; swapped = false; };
  const back = () => { dropAi(); mode = "read"; draft = null; msg = ""; draw(); loadSummary(); };   // the kept summary comes back (stale if the note changed)
  async function save() {
    const r = await api("/api/notes/" + note.id, json("PUT", draft));
    if (!r.ok) { msg = SAVE_ERROR; mode = "edit"; draw(); return; }
    Object.assign(note, await r.json()); back(); cb.onChange();
  }
  async function remove() {
    const r = await api("/api/notes/" + note.id, {method: "DELETE"});
    if (r.status !== 204 && r.status !== 404) { msg = tr("delete_failed"); mode = "read"; draw(); return; }
    cb.onDeleted();       // a 404 means it is already gone, which is the state the user wanted
  }
  const target = () => ((noteLang(note.body) === "pl") !== swapped ? "en" : "pl");   // the language to translate into
  // Translation: a preview in place of the note. Leaves the note untouched, saves nothing.
  async function translate() {
    const mine = ++tjob, to = target();
    preview = {state: "loading", minH: Math.max(160, (root.querySelector(".sheet") || {offsetHeight: 0}).offsetHeight - 50)}; draw();
    aiBusy(() => root.querySelector(".aipad"));
    let next;
    try {
      const r = await api("/api/notes/" + note.id + "/translate?to=" + to, {method: "POST"});
      if (r.ok) { const d = await r.json(); next = {state: "done", text: d.text, lang: d.lang}; }
      else { const d = (await r.json().catch(() => ({}))).detail; next = {state: "error", msg: tr(AI_ERRORS[d && d.code] || "ai_err_failed")}; }
    } catch (e) {
      if (e.message === "not authenticated") return;
      next = {state: "error", msg: tr("ai_err_failed")};
    }
    if (mine !== tjob || !preview) return;
    aiBusy(null);
    preview = {...next, minH: preview.minH}; draw();
  }
  const closeTranslation = () => { tjob++; preview = null; swapped = false; draw(); };
  const openTranslation = () => { swapped = false; translate(); };
  const swap = () => { swapped = !swapped; translate(); };
  async function copyAiText(text) {
    try { await navigator.clipboard.writeText(text); toast(tr("copied")); }
    catch (e) { toast(tr("copy_failed")); }
  }
  function translationBlock(tk) {
    const head = h("div", {class: "aihd"}, icon("spark", 16), h("span", {}, translateLabel(target())),
      preview.state === "loading" ? null : h("button", {type: "button", class: "btn icon", "aria-label": tr("translate_swap"), title: tr("translate_swap"), onclick: swap}, icon("swap", 16)),
      h("span", {class: "grow"}),
      preview.state === "done" ? h("button", {type: "button", class: "btn", onclick: () => copyAiText(preview.text)}, icon("copy", 16), tr("copy_translation")) : null,
      preview.state === "error" ? h("button", {type: "button", class: "btn primary", onclick: translate}, tr("retry")) : null,
      h("button", {type: "button", class: "btn", onclick: closeTranslation}, tr("back")));
    const body = preview.state === "loading" ? h("div", {class: "aithink", role: "status"}, icon("spark", 30), h("span", {}, tr("translating")))
      : preview.state === "error" ? h("div", {class: "err aierr"}, preview.msg)
      : h("div", {class: "aibody"}, readerBody({body: preview.text}, tk, preview.lang));   // the same layout as the note: contents, width, font
    return h("div", {class: "aiframe aipad", style: preview.state === "done" ? "" : "min-height:" + preview.minH + "px"}, head, body);   // loading and errors keep the height of the note, so the page does not jump
  }
  // Summary: a block above the note (the note stays below it). Saves nothing.
  async function summarize() {
    const mine = ++sjob;
    sum = {state: "loading", collapsed: false}; draw();
    aiBusy(() => root.querySelector(".aisum"));
    let next;
    try {
      const r = await api("/api/notes/" + note.id + "/summarize", {method: "POST"});
      if (r.ok) {
        const d = await r.json();
        next = d.text ? {state: "done", text: d.text, created_at: d.created_at, stale: false} : {state: "error", msg: tr("summary_empty")};
      }
      else { const d = (await r.json().catch(() => ({}))).detail; next = {state: "error", msg: tr(SUMMARY_ERRORS[d && d.code] || "ai_err_failed_summary")}; }
    } catch (e) {
      if (e.message === "not authenticated") return;
      next = {state: "error", msg: tr("ai_err_failed_summary")};
    }
    if (mine !== sjob || !sum) return;
    aiBusy(null);
    sum = {...next, collapsed: false}; draw();
  }
  // The summary is kept on the server (one per note): it is there when the note is opened again, and goes stale when the note is edited.
  async function loadSummary() {
    if (!AI_READY) return;
    const mine = sjob;
    try {
      const r = await api("/api/notes/" + note.id + "/summary");
      if (!r.ok) return;
      const d = await r.json();
      if (d && mine === sjob && !sum && mode === "read") { sum = {state: "done", text: d.text, created_at: d.created_at, stale: d.stale, collapsed: false}; draw(); }   // open by default
    } catch (e) { /* a convenience: without it the note simply shows no summary */ }
  }
  const toggleSummary = () => { sum.collapsed = !sum.collapsed; draw(); };
  async function removeSummary() {      // the close button deletes a kept summary (collapsing is the chevron); an unsaved one is just dropped
    const kept = !!sum && sum.state === "done";
    sjob++; sum = null; draw();
    if (!kept) return;
    try {
      const r = await api("/api/notes/" + note.id + "/summary", {method: "DELETE"});
      if (r.status !== 204) throw new Error("delete");
    } catch (e) {
      if (e.message !== "not authenticated") toast(tr("summary_delete_failed"), "bad", 4000);
    }
  }
  function summaryBlock(tk) {
    const head = h("div", {class: "aihd"}, icon("spark", 16), h("span", {title: sum.created_at ? tr("summary_from", {date: longDate(sum.created_at)}) : ""}, tr("summary_h")),
      sum.stale ? h("span", {class: "stale", title: tr("summary_stale_hint")}, tr("summary_stale")) : null,
      h("span", {class: "grow"}),
      sum.state === "done" ? h("button", {type: "button", class: "btn", "aria-label": tr("copy_summary"), title: tr("copy_summary"), onclick: () => copyAiText(sum.text)}, icon("copy", 14), tr("copy")) : null,
      sum.state === "loading" ? null : h("button", {type: "button", class: "btn", onclick: summarize}, icon("swap", 14), tr(sum.state === "error" ? "retry" : "ai_refresh")),
      sum.state === "done" ? h("button", {type: "button", class: "btn icon chev", "aria-label": tr(sum.collapsed ? "ai_expand" : "ai_collapse"), title: tr(sum.collapsed ? "ai_expand" : "ai_collapse"), "aria-expanded": sum.collapsed ? "false" : "true", onclick: toggleSummary}, icon("chevron-down", 14)) : null,
      h("button", {type: "button", class: "btn icon", "aria-label": tr(sum.state === "done" ? "summary_delete" : "ai_close"), title: tr(sum.state === "done" ? "summary_delete" : "ai_close"), onclick: removeSummary}, icon("x", 14)));
    const body = sum.state === "loading" ? h("div", {class: "aithink", role: "status"}, icon("spark", 18), h("span", {}, tr("summarizing")))
      : sum.state === "error" ? h("div", {class: "err aierr"}, sum.msg)
      : h("article", {class: "md aisumbody"}, mdBlocksDom(mdParse(sum.text), {tk, heads: [], lang: noteLang(note.body)}));
    return h("div", {class: "sumwrap"}, h("div", {class: "aiframe aisum" + (sum.collapsed ? " collapsed" : "")}, head, body));
  }
  // The AI actions live in one strip at the top of the sheet; its single AI tag marks everything below it (the blocks it opens carry the frame and the spark, not a second tag)
  function aiStrip() {
    if (!AI_READY) return null;
    const act = (on, ic, label, title, onclick) => h("button", {type: "button", class: "btn aibtn" + (on ? " act" : ""), "aria-pressed": on ? "true" : "false", title: title + " (AI)", onclick}, icon(ic, 15), label);
    return h("div", {class: "aistrip"},
      act(!!sum && !sum.collapsed, "align-left", tr("summarize_btn"), tr("summarize"), sum ? (sum.state === "done" ? toggleSummary : removeSummary) : summarize),
      act(!!preview, "languages", translateLabel(target()), translateLabel(target()), preview ? closeTranslation : openTranslation),
      h("span", {class: "grow"}), aiTag());
  }
  function draw() {
    root.dataset.mode = mode;
    if (mode === "read") {
      const tk = tokens();
      const edit = () => { exitReading(); dropAi(); draft = {title: note.title, body: note.body, tags: [...note.tags], category_id: note.category_id}; msg = ""; mode = "edit"; draw(); };
      const catBadge = h("span", {class: "badge cat"}, catName(note.category_id));
      root.replaceChildren(
        h("div", {class: "hero"},
          waveDefs(svg([["defs", {}], ["path", {d: "M0 250 C 110 215, 210 140, 290 78 S 380 8, 400 0 V250 Z", fill: "url(#wv1)"}], ["path", {d: "M110 250 C 210 228, 300 170, 352 112 S 392 60, 400 52 V250 Z", fill: "url(#wv2)"}], ["path", {d: "M230 250 C 300 238, 360 205, 400 165 V250 Z", fill: "url(#wv3)"}]], {class: "wave", viewBox: "0 0 400 250", preserveAspectRatio: "xMaxYMid slice", "aria-hidden": "true"})),
          h("div", {class: "bar"},
            h("div", {class: "left"},
              h("button", {type: "button", class: "iconbtn back", "aria-label": tr("back"), onclick: () => setView("list")}, icon("chevron-left", 18)),
              h("span", {class: "datebadge"}, icon("calendar", 15), tr("created") + ": " + longDate(note.created_at)),
              catBadge),
            h("div", {class: "tools"},
              h("button", {type: "button", class: "iconbtn readtoggle", "aria-label": tr("reading_mode"), "aria-pressed": "false", title: tr("reading_mode"), onclick: toggleReading}, icon("book", 17)),
              h("button", {type: "button", class: "iconbtn", "aria-label": tr("copy"), title: tr("copy"), onclick: () => copyNote(note)}, icon("copy", 17)),
              h("button", {type: "button", class: "iconbtn", "aria-label": tr("edit"), title: tr("edit"), onclick: edit}, icon("pencil", 17)),
              h("button", {type: "button", class: "iconbtn del", "aria-label": tr("delete"), title: tr("delete"), onclick: () => { dropAi(); msg = ""; mode = "del"; draw(); }}, icon("trash", 17)))),
          h("h2", {}, hlNodes(note.title, tk)),
          h("div", {class: "chips"}, note.tags.map((t) => h("button", {type: "button", class: "chip" + (state.sel.has(t) ? " on" : ""), onclick: () => toggleTag(t)}, "#" + t)))),
        h("div", {class: "sheet"}, aiStrip(), preview ? translationBlock(tk) : [sum && AI_READY ? summaryBlock(tk) : null, readerBody(note, tk)], h("div", {class: "err"}, msg)));
      setTimeout(() => { watchToc(root); syncReadButton(); }, 0);   // after the panel is in the page
    } else if (mode === "del") {
      root.replaceChildren(h("h2", {}, note.title), h("div", {class: "confirm"}, h("span", {}, tr("confirm_delete")),
        h("button", {class: "btn danger", onclick: remove}, tr("yes_delete")), h("button", {class: "btn", onclick: back}, tr("back"))));
    } else if (mode === "edit") {
      const f = noteForm(draft, msg);
      root.replaceChildren(f.el, h("div", {class: "row"},
        h("button", {class: "btn primary", onclick: () => { const v = f.values(); if (v) { draft = v; msg = ""; mode = "confirm"; draw(); } }}, tr("save")),
        h("button", {class: "btn", onclick: back}, tr("cancel"))));
      f.focus();
    } else {
      root.replaceChildren(h("h2", {}, draft.title), h("div", {class: "confirm warn"}, h("span", {}, tr("confirm_save")),
        h("button", {class: "btn primary", onclick: save}, tr("yes_overwrite")), h("button", {class: "btn", onclick: () => { mode = "edit"; draw(); }}, tr("back"))));
    }
  }
  draw();
  loadSummary();      // a kept summary is shown at once
  return root;
}
function newPanel(cb) {
  const f = noteForm({title: "", body: "", tags: [], category_id: state.category ?? defaultId()}, "");
  const root = h("div", {class: "panel pad"}, h("h2", {}, tr("new_note_h")), f.el, h("div", {class: "row"},
    h("button", {class: "btn primary", onclick: async () => {
      const v = f.values(); if (!v) return;
      const r = await api("/api/notes", json("POST", v));
      if (!r.ok) { f.err.textContent = SAVE_ERROR; return; }
      cb.onCreated(await r.json());
    }}, tr("save")),
    h("button", {class: "btn", onclick: cb.onCancel}, tr("cancel"))));
  setTimeout(() => f.focus());
  return root;
}

// --- wiring
$("#q").addEventListener("input", () => { state.q = $("#q").value; clearTimeout(timer); timer = setTimeout(() => { state.mode = "view"; load(); }, 100); });
$("#new").addEventListener("click", openNew);
$("#chatbtn").addEventListener("click", () => { openMenu(false); openChat(); });
$("#f-all").addEventListener("click", () => { state.sel.clear(); state.category = null; state.mode = "view"; renderTagbar(); renderCategories(); load(); });
$("#f-clear").addEventListener("click", () => resetFilters(true));
// Sorting: "" is the default (newest first, or by relevance while searching); a chosen order always wins
state.sort = SETTINGS.sort;
$("#sort").replaceChildren(...Object.entries(SORT_LABELS).map(([value, key]) => h("option", {value}, tr(key))));
const syncSort = () => { $("#sort").value = state.sort; $("#sortbox").classList.toggle("on", state.sort !== ""); };
syncSort();
$("#sort").addEventListener("change", async () => {
  const prev = state.sort;
  state.sort = $("#sort").value; syncSort();
  load();
  if (!(await saveSettings({sort: state.sort}))) { state.sort = prev; syncSort(); load(); }
});
applyReader(false);
$("#r-smaller").addEventListener("click", () => { READER.size = Math.max(READ_SIZES[0], READER.size - 1); applyReader(); });
$("#r-larger").addEventListener("click", () => { READER.size = Math.min(READ_SIZES[1], READER.size + 1); applyReader(); });
$("#r-width").addEventListener("click", () => { READER.width = (READER.width + 1) % READ_WIDTHS.length; applyReader(); });
$("#r-exit").addEventListener("click", exitReading);
$("#catmore").addEventListener("click", () => { catsOpen = !catsOpen; fitList("cat", CAT_PREVIEW + 1, catsOpen); });
$("#tagmore").addEventListener("click", () => { tagsOpen = !tagsOpen; fitTags(); });
const openMenu = (on) => { $("#app").classList.toggle("menu", on); $("#scrim").hidden = !on; };
$("#menu").addEventListener("click", () => openMenu(true));
$("#kbbtn").addEventListener("click", () => { openMenu(false); showShortcuts(); });
$("#scrim").addEventListener("click", () => openMenu(false));
$("#shortcut").textContent = /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent) ? "⌘ K" : "Ctrl K";
document.addEventListener("keydown", (e) => {
  if (document.querySelector("dialog[open]") || aiBlocked()) return;   // a dialog handles its own keys (Esc closes it natively); the page is blocked while AI works
  if (state.reading) { if (e.key === "Escape") { e.preventDefault(); exitReading(); } return; }   // reading mode: Esc leaves it, the rest scrolls
  const typing = /INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName), q = $("#q");
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); q.focus(); q.select(); }
  else if (e.key === "/" && !typing) { e.preventDefault(); q.focus(); }
  else if ((e.key === "n" || e.key === "N") && !typing) { e.preventDefault(); openNew(); }
  else if (e.key === "Escape") { openMenu(false); resetFilters(true); q.focus(); }
  else if ((e.key === "ArrowDown" || e.key === "ArrowUp") && state.list.length && !e.altKey && !e.ctrlKey && !e.metaKey
    && (document.activeElement === q || (!typing && state.mode === "view"))) {   // from the search box, or anywhere outside a form
    const i = state.list.findIndex((x) => x.id === state.cur);
    const next = state.list[Math.max(0, Math.min(state.list.length - 1, i + (e.key === "ArrowDown" ? 1 : -1)))];
    e.preventDefault(); select(next.id);
    const on = document.querySelector(".res.on");
    if (on) on.scrollIntoView({block: "nearest"});    // keep the chosen card in view (the list scrolls, not the page)
  }
});
fillIcons();
setAiReady(AI_READY);
loadTags();
loadCategories().then(() => load());   // categories first: the note's category badge and the total need them
"""
    + r"""</script>
</body>
</html>
"""
)

INDEX_HTML = (
    INDEX_HTML.replace("/*CORE*/", core.CORE_JS)
    .replace("/*READER_PURE*/", READER_PURE_JS)
    .replace("/*READER_UI*/", READER_UI_JS)
    .replace("/*EDITOR_PURE*/", EDITOR_PURE_JS)
    .replace("/*EDITOR_UI*/", EDITOR_UI_JS)
    .replace("/*CHAT_UI*/", CHAT_JS)
)

LANG_SWITCH_JS = (
    'document.querySelectorAll("[data-lang]").forEach(function(b){'
    'b.addEventListener("click",function(){document.cookie="lang="+b.dataset.lang+'
    '"; path=/; max-age=31536000; SameSite=Lax";location.reload();});});'
)


def fill(template: str, lang: str) -> str:
    """Replace `[[key]]` markers with the escaped UI strings of `lang` (a missing key is an error)."""
    strings = {**STRINGS[lang], "lang": lang}
    return re.sub(
        r"\[\[(\w+)\]\]",
        lambda m: html.escape(strings[m.group(1)], quote=True),
        template,
    )


def render_index(lang: str, settings: Mapping[str, object] | None = None) -> str:
    return core.inject(fill(INDEX_HTML, lang), lang, settings)
