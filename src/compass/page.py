"""The single notes page (served at `/`) and the CSS shared with the login page.

Built from DOM calls only: note text and tags are inserted with `textContent` / `value`,
never as HTML. The server ranks the results; the highlighting here is cosmetic.
UI text lives in `i18n.py`: `[[key]]` markers are filled in on the server, the script reads the
same strings from the embedded `I18N` object.
"""

import html
import json
import re

from compass.i18n import STRINGS

COMMON_CSS = r"""
:root{
  --bg:#101116; --side:#151722; --panel:#1b1d2a; --raise:#222538; --line:rgba(255,255,255,.07); --line-strong:rgba(99,125,255,.85);
  --accent:#5275ff; --accent-2:#795cff; --accent-light:#7295ff; --accent-soft:rgba(82,117,255,.16);
  --ink:#f5f5fa; --muted:#a3a5b5; --faint:#777b90; --mark:rgba(121,92,255,.38); --ok:#22c55e; --danger:#f87171; --danger-soft:rgba(248,113,113,.12);
  --grad:linear-gradient(135deg,#477bff,#765bff); --r:14px; --shadow:0 1px 2px rgba(0,0,0,.4),0 12px 32px rgba(0,0,0,.35);
  --glow:0 0 0 1px rgba(99,125,255,.55),0 8px 30px rgba(82,117,255,.22); --ease:.18s ease-out;
}
:root[data-theme=light]{
  --bg:#f4f5fa; --side:#ffffff; --panel:#ffffff; --raise:#eef0f8; --line:rgba(20,24,50,.09); --line-strong:rgba(82,117,255,.9);
  --accent:#4263eb; --accent-light:#4263eb; --accent-soft:rgba(82,117,255,.12); --ink:#16182a; --muted:#5b5f75; --faint:#8a8ea3;
  --mark:rgba(255,214,10,.45); --ok:#15803d; --danger:#dc2626; --danger-soft:rgba(220,38,38,.08);
  --shadow:0 1px 2px rgba(20,24,50,.05),0 12px 32px rgba(20,24,50,.08); --glow:0 0 0 1px rgba(82,117,255,.5),0 8px 26px rgba(82,117,255,.16);
}
*{box-sizing:border-box}
html{color-scheme:dark}
html[data-theme=light]{color-scheme:light}
body{margin:0;font-family:Inter,Geist,system-ui,-apple-system,"Segoe UI",sans-serif;background:var(--bg);color:var(--ink);font-size:14px;line-height:1.5;-webkit-font-smoothing:antialiased}
button{font:inherit;cursor:pointer;color:inherit}
input,textarea,select{font:inherit;color:var(--ink)}
[hidden]{display:none!important}
mark{background:var(--mark);color:inherit;border-radius:4px;padding:0 2px}
kbd{font-family:ui-monospace,"JetBrains Mono",monospace;font-size:11px;border:1px solid var(--line);border-radius:6px;padding:1px 6px;color:var(--muted);background:rgba(255,255,255,.04)}
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
.toast{position:fixed;bottom:22px;left:50%;transform:translateX(-50%) translateY(6px);background:var(--raise);color:var(--ink);border:1px solid var(--line);box-shadow:var(--shadow);padding:9px 18px;border-radius:999px;font-size:13px;opacity:0;transition:opacity .2s ease-out,transform .2s ease-out;pointer-events:none;z-index:60}
.toast.show{opacity:1;transform:translateX(-50%)}
.login{min-height:100vh;display:grid;place-items:center;padding:20px;background:radial-gradient(900px 500px at 70% -10%,rgba(82,117,255,.14),transparent),var(--bg)}
.login .card{width:min(380px,100%);background:var(--panel);border:1px solid var(--line);border-radius:20px;padding:28px;box-shadow:var(--shadow)}
.login h1{margin:0 0 4px;font-size:22px}
.logo{display:flex;align-items:center;gap:12px;font-weight:700;font-size:20px;letter-spacing:-.01em}
.logo .dot{width:40px;height:40px;border-radius:12px;background:var(--grad);display:grid;place-items:center;color:#fff;font-size:20px;box-shadow:0 6px 18px rgba(82,117,255,.35)}
.protonote{font-size:12px;color:var(--muted);border-left:3px solid var(--accent);padding-left:10px;margin-top:14px}
@media (prefers-reduced-motion:reduce){*,*::before,*::after{transition:none!important;animation:none!important}}
"""

APP_CSS = r"""
body{overflow:hidden}
.app{display:grid;grid-template-columns:250px minmax(0,1fr);height:100vh}
aside{scrollbar-width:thin;scrollbar-color:rgba(128,132,160,.35) transparent;background:var(--side);border-right:1px solid var(--line);padding:22px 16px 16px;overflow:auto;display:flex;flex-direction:column;gap:4px;scrollbar-width:thin}
.logo .dot svg{display:block}
.tagline{font-size:12px;font-weight:400;color:var(--faint);line-height:1.2;margin-top:3px}
aside .logo{margin-bottom:20px}
.wide{width:100%}
.newbtn{padding:13px 14px;border-radius:14px;font-size:14px;font-weight:600}
h4{display:flex;justify-content:space-between;align-items:center;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.07em;color:var(--faint);margin:22px 4px 8px}
.legend{list-style:none;margin:0;padding:0;font-size:12.5px;display:grid;gap:10px}
.legend li{display:flex;gap:12px;align-items:flex-start;line-height:1.35}
.legend .ic{color:var(--accent-light);margin-top:1px}
aside>*{flex:none}
aside>.spacer{flex:1 0 12px}
.sep{border-top:1px solid var(--line);margin:20px 0 0}
.sep+h4{margin-top:18px}
.sidebtn{margin-top:4px}
.row{display:flex;gap:8px;align-items:center}
.row form{margin:0}
a.btn{text-decoration:none}
.sidebtn{justify-content:center;background:rgba(255,255,255,.03);padding:10px 12px;border-radius:12px}
.importask{display:grid;gap:8px;margin-top:6px;padding:10px;border:1px solid rgba(248,113,113,.4);border-radius:12px;background:var(--danger-soft)}
.msg{font-size:12px;min-height:1em;margin-top:2px}
.msg.ok{color:var(--ok)}
.msg.bad{color:var(--danger)}
main{display:flex;flex-direction:column;min-width:0;height:100vh;padding:18px 24px 0 22px;background:radial-gradient(1100px 520px at 75% -12%,rgba(82,117,255,.11),transparent 70%),radial-gradient(700px 500px at 0% 100%,rgba(121,92,255,.06),transparent 70%),var(--bg)}
.topbar{display:flex;gap:12px;align-items:center}
.menubtn{display:none}
.searchbar{flex:1;display:flex;align-items:center;gap:12px;height:50px;background:linear-gradient(180deg,var(--panel),var(--side));border:1px solid var(--line);border-radius:16px;padding:0 14px;color:var(--muted);transition:border-color var(--ease),box-shadow var(--ease)}
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
.count{color:var(--muted);font-size:13px;margin:0 4px 10px}
.withbtn{display:flex;justify-content:space-between;align-items:center}
.linkbtn{display:inline-flex;align-items:center;gap:6px;border:0;background:none;color:var(--muted);font-size:12px;padding:0;text-transform:none;letter-spacing:0;font-weight:500}
.linkbtn:hover{color:var(--accent-light)}
dialog{border:1px solid var(--line);border-radius:20px;padding:22px;width:min(520px,calc(100% - 32px));background:var(--panel);color:var(--ink);box-shadow:var(--shadow)}
dialog::backdrop{background:rgba(5,6,12,.6);backdrop-filter:blur(2px)}
.dlg-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:14px}
.dlg-head h3{margin:0;font-size:18px}
.catrows{list-style:none;margin:12px 0 0;padding:0;max-height:50vh;overflow:auto}
.catrow{display:flex;gap:8px;align-items:center;flex-wrap:wrap;padding:10px 0;border-top:1px solid var(--line)}
.catrow .name{flex:1;min-width:120px;font-weight:600}
.catrow .n{color:var(--muted);font-size:12px}
.catrow input,.qrow input{flex:1;min-width:120px;border:1px solid var(--line);border-radius:10px;padding:8px 11px;background:var(--bg)}
.catrow input:focus,.qrow input:focus{outline:0;border-color:var(--line-strong);box-shadow:0 0 0 3px var(--accent-soft)}
.small{font-size:12px}
.catlist{display:flex;flex-direction:column;gap:2px}
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
.skel{height:104px;border-radius:16px;border:1px solid var(--line);background:linear-gradient(100deg,var(--panel) 30%,var(--raise) 50%,var(--panel) 70%);background-size:200% 100%;animation:shimmer 1.3s linear infinite}
@keyframes shimmer{to{background-position:-200% 0}}
.card{background:var(--panel);border:1px solid var(--line);border-radius:20px;overflow:hidden;box-shadow:var(--shadow);animation:rise .2s ease-out}
@keyframes rise{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:none}}
.panel[data-mode=edit],.panel[data-mode=del],.panel[data-mode=confirm],.panel.pad{padding:24px 26px}
.hero{position:relative;overflow:hidden;padding:20px 26px 22px;color:#fff;background:linear-gradient(135deg,#2c2070 0%,#1d2468 55%,#161d46 100%);border-bottom:1px solid var(--line)}
.hero .wave{position:absolute;right:-20px;bottom:-30px;width:70%;height:auto;opacity:.5;pointer-events:none}
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
.panel .body{white-space:pre-wrap;font-size:15.5px;line-height:1.7;padding:24px 26px 28px;margin:0;color:var(--ink);opacity:.94;overflow-wrap:anywhere}
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
<html lang="[[lang]]">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Compass</title>
<style>"""
    + COMMON_CSS
    + APP_CSS
    + r"""</style>
</head>
<body>"""
    + r"""
<div class="app" id="app" data-view="list">
  <aside id="side">
    <div class="logo"><div class="dot"><span class="ic" data-icon="compass" data-size="22"></span></div><div><div>Compass</div><div class="tagline">[[tagline]]</div></div></div>
    <button type="button" class="btn primary wide newbtn" id="new">[[new_note]]</button>
    <h4><span>[[categories_h]]</span><button type="button" class="linkbtn" id="managecats" title="[[manage_title]]">[[manage_categories]]<span class="ic" data-icon="settings" data-size="15"></span></button></h4>
    <div class="catlist" id="catbar"></div>
    <h4><span>[[tags_h]]</span></h4>
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
    <div class="row">
      <div class="row langs" role="group" aria-label="[[lang_label]]">
        <button type="button" class="btn icon" data-lang="pl">PL</button>
        <button type="button" class="btn icon" data-lang="en">EN</button>
      </div>
      <button type="button" class="btn icon" id="theme" title="[[theme_title]]" aria-label="[[theme_title]]"><span class="ic" data-icon="moon"></span></button>
    </div>
    <button type="button" class="btn wide sidebtn" id="import" title="[[import_title]]"><span class="ic" data-icon="upload"></span>[[import]]</button>
    <input type="file" id="importfile" accept=".json,application/json" hidden>
    <a class="btn wide sidebtn" href="/api/export" download title="[[export_title]]"><span class="ic" data-icon="download"></span>[[export]]</a>
    <div id="importask" class="importask" hidden><div class="msg bad" id="importasktext"></div><div class="qrow"><button type="button" class="btn danger" id="importyes">[[import_replace]]</button><button type="button" class="btn" id="importno">[[cancel]]</button></div></div>
    <div id="importmsg" class="msg" role="status"></div>
    <form method="post" action="/logout"><button class="btn wide sidebtn"><span class="ic" data-icon="logout"></span>[[logout]]</button></form>
  </aside>
  <div class="scrim" id="scrim" hidden></div>
  <main>
    <div class="topbar">
      <button type="button" class="btn icon menubtn" id="menu" aria-label="[[menu_open]]"><span class="ic" data-icon="menu"></span></button>
      <div class="searchbar"><span class="ic" data-icon="search" data-size="20"></span><input id="q" placeholder="[[search_ph]]" autocomplete="off" autofocus><kbd id="shortcut">/</kbd></div>
    </div>
    <div class="filters">
      <button type="button" class="pill" id="f-all"><span class="ic" data-icon="layers" data-size="14"></span>[[category_all]]</button>
      <button type="button" class="pill" id="f-clear"><span class="ic" data-icon="filter-x" data-size="14"></span>[[filter_clear]]</button>
      <div class="hint"><span><kbd>↑</kbd><kbd>↓</kbd> [[hint_select]]</span><span><kbd>N</kbd> [[hint_new]]</span><span><kbd>Esc</kbd> [[hint_clear]]</span></div>
    </div>
    <div class="grid">
      <div class="listcol"><div class="count" id="count"></div><div class="results" id="results"></div></div>
      <div class="detailcol" id="detail"></div>
    </div>
  </main>
</div>
<dialog id="catdialog" aria-labelledby="catdialog-h">
  <div class="dlg-head"><h3 id="catdialog-h">[[manage_title]]</h3><button type="button" class="btn icon" id="catclose" aria-label="[[manage_close]]"><span class="ic" data-icon="x" data-size="16"></span></button></div>
  <div class="qrow"><input id="catnew" placeholder="[[category_new_ph]]" maxlength="60" autocomplete="off"><button type="button" class="btn primary" id="catadd">[[category_add]]</button></div>
  <div class="err" id="catmsg" role="alert"></div>
  <ul class="catrows" id="catrows"></ul>
</dialog>
<div class="toast" id="toast" role="status"></div>
"""
    + r"""<script>"""
    + r"""
/*I18N*/
const LANG = I18N.lang, T = I18N.strings;
const tr = (key, vars = {}) => T[key].replace(/\{(\w+)\}/g, (_, k) => vars[k]);
const $ = (s) => document.querySelector(s);
function h(tag, props, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(props || {})) {
    if (k === "class") el.className = v;
    else if (k.startsWith("on")) el[k] = v;
    else if (k in el) el[k] = v;
    else el.setAttribute(k, v);
  }
  for (const kid of kids.flat()) if (kid != null && kid !== false) el.append(kid);
  return el;
}

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
// --- icons (Lucide-style line icons, drawn with DOM calls; no external requests)
const SVGNS = "http://www.w3.org/2000/svg";
const ICONS = {
  compass: [["circle", {cx: 12, cy: 12, r: 10}], ["polygon", {points: "16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76"}]],
  plus: [["path", {d: "M5 12h14"}], ["path", {d: "M12 5v14"}]],
  search: [["circle", {cx: 11, cy: 11, r: 8}], ["path", {d: "m21 21-4.3-4.3"}]],
  zap: [["polygon", {points: "13 2 3 14 12 14 11 22 21 10 12 10 13 2"}]],
  star: [["polygon", {points: "12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"}]],
  settings: [["path", {d: "M20 7h-9"}], ["path", {d: "M14 17H5"}], ["circle", {cx: 17, cy: 17, r: 3}], ["circle", {cx: 7, cy: 7, r: 3}]],
  upload: [["path", {d: "M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"}], ["polyline", {points: "17 8 12 3 7 8"}], ["line", {x1: 12, y1: 3, x2: 12, y2: 15}]],
  download: [["path", {d: "M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"}], ["polyline", {points: "7 10 12 15 17 10"}], ["line", {x1: 12, y1: 15, x2: 12, y2: 3}]],
  logout: [["path", {d: "M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"}], ["polyline", {points: "16 17 21 12 16 7"}], ["line", {x1: 21, y1: 12, x2: 9, y2: 12}]],
  moon: [["path", {d: "M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"}]],
  sun: [["circle", {cx: 12, cy: 12, r: 4}], ["path", {d: "M12 2v2"}], ["path", {d: "M12 20v2"}], ["path", {d: "m4.93 4.93 1.41 1.41"}], ["path", {d: "m17.66 17.66 1.41 1.41"}], ["path", {d: "M2 12h2"}], ["path", {d: "M20 12h2"}], ["path", {d: "m6.34 17.66-1.41 1.41"}], ["path", {d: "m19.07 4.93-1.41 1.41"}]],
  menu: [["path", {d: "M4 6h16"}], ["path", {d: "M4 12h16"}], ["path", {d: "M4 18h16"}]],
  x: [["path", {d: "M18 6 6 18"}], ["path", {d: "m6 6 12 12"}]],
  "chevron-right": [["path", {d: "m9 18 6-6-6-6"}]],
  "chevron-left": [["path", {d: "m15 18-6-6 6-6"}]],
  "chevron-down": [["path", {d: "m6 9 6 6 6-6"}]],
  pencil: [["path", {d: "M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"}], ["path", {d: "m15 5 4 4"}]],
  copy: [["rect", {x: 8, y: 8, width: 14, height: 14, rx: 2}], ["path", {d: "M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"}]],
  trash: [["path", {d: "M3 6h18"}], ["path", {d: "M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"}], ["path", {d: "M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"}]],
  calendar: [["rect", {x: 3, y: 4, width: 18, height: 18, rx: 2}], ["path", {d: "M16 2v4"}], ["path", {d: "M8 2v4"}], ["path", {d: "M3 10h18"}]],
  layers: [["polygon", {points: "12 2 2 7 12 12 22 7 12 2"}], ["polyline", {points: "2 17 12 22 22 17"}], ["polyline", {points: "2 12 12 17 22 12"}]],
  "filter-x": [["path", {d: "M13.013 3H2l8 9.46V19l4 2v-8.54l.9-1.055"}], ["path", {d: "m22 3-5 5"}], ["path", {d: "m17 3 5 5"}]],
  message: [["path", {d: "M7.9 20A9 9 0 1 0 4 16.1L2 22Z"}]],
  branch: [["line", {x1: 6, y1: 3, x2: 6, y2: 15}], ["circle", {cx: 18, cy: 6, r: 3}], ["circle", {cx: 6, cy: 18, r: 3}], ["path", {d: "M18 9a9 9 0 0 1-9 9"}]],
  code: [["polyline", {points: "16 18 22 12 16 6"}], ["polyline", {points: "8 6 2 12 8 18"}]],
  book: [["path", {d: "M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"}], ["path", {d: "M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"}]],
  database: [["ellipse", {cx: 12, cy: 5, rx: 9, ry: 3}], ["path", {d: "M3 5V19A9 3 0 0 0 21 19V5"}], ["path", {d: "M3 12A9 3 0 0 0 21 12"}]],
  chart: [["path", {d: "M12 20V10"}], ["path", {d: "M18 20V4"}], ["path", {d: "M6 20v-4"}]],
  binary: [["rect", {x: 14, y: 14, width: 4, height: 6, rx: 2}], ["rect", {x: 6, y: 4, width: 4, height: 6, rx: 2}], ["path", {d: "M6 20h4"}], ["path", {d: "M14 10h4"}], ["path", {d: "M6 14h2v6"}], ["path", {d: "M14 4h2v6"}]],
  file: [["path", {d: "M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"}], ["path", {d: "M14 2v4a2 2 0 0 0 2 2h4"}], ["path", {d: "M10 9H8"}], ["path", {d: "M16 13H8"}], ["path", {d: "M16 17H8"}]],
};
function svg(spec, attrs) {
  const s = document.createElementNS(SVGNS, "svg");
  for (const [k, v] of Object.entries(attrs)) s.setAttribute(k, v);
  for (const [tag, a] of spec) { const e = document.createElementNS(SVGNS, tag); for (const [k, v] of Object.entries(a)) e.setAttribute(k, v); s.append(e); }
  return s;
}
const icon = (name, size = 18) => svg(ICONS[name], {viewBox: "0 0 24 24", width: size, height: size, fill: "none", stroke: "currentColor", "stroke-width": 2, "stroke-linecap": "round", "stroke-linejoin": "round", "aria-hidden": "true"});
const fillIcons = (root = document) => root.querySelectorAll("[data-icon]").forEach((el) => el.replaceChildren(icon(el.dataset.icon, +el.dataset.size || 18)));
const TOPICS = [[/rozmow|interview|soft/, "message"], [/\bgit\b/, "branch"], [/algorytm|algorithm|big o/, "binary"], [/sql|baz|database|data/, "database"],
  [/statyst|mediana|wartosc p/, "chart"], [/kod|code|program|api|docker|devops|rest/, "code"], [/nauk|learn|biolog|fotosint/, "book"], [/pomysl|idea|wskazowk/, "star"]];
const noteIcon = (note) => { const hay = fold(note.title + " " + note.tags.join(" ")); const hit = TOPICS.find(([re]) => re.test(hay)); return hit ? hit[1] : "file"; };
const shortDate = (iso) => new Date(iso).toLocaleDateString(LANG, {day: "numeric", month: "short"});
const longDate = (iso) => new Date(iso).toLocaleDateString(LANG, {day: "numeric", month: "short", year: "numeric"});
function toast(msg) { const t = $("#toast"); t.textContent = msg; t.classList.add("show"); clearTimeout(t._h); t._h = setTimeout(() => t.classList.remove("show"), 1800); }

// --- state and server calls
const state = {q: "", sel: new Set(), category: null, cur: null, mode: "view", list: [], tags: [], categories: [], total: 0};
let seq = 0, timer;
async function api(path, opts) {
  const r = await fetch(path, opts);
  if (r.status === 401) { location.href = "/login"; throw new Error("not authenticated"); }
  return r;
}
const json = (method, body) => ({method, headers: {"content-type": "application/json"}, body: JSON.stringify(body)});
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
  $("#results").replaceChildren(h("div", {class: "empty"}, h("div", {}, tr("load_failed")), h("button", {type: "button", class: "btn", style: "margin-top:12px", onclick: () => { skeleton(); load(); }}, tr("retry"))));
}
function skeleton() { $("#results").replaceChildren(...[0, 1, 2, 3, 4].map(() => h("div", {class: "skel"}))); }
async function load(keepDetail = false) {
  const mine = ++seq, had = state.cur;
  const params = new URLSearchParams({q: state.q});
  for (const t of state.sel) params.append("tag", t);
  if (state.category !== null) params.set("category_id", state.category);
  let list;
  try {
    const r = await api("/api/notes?" + params);
    if (!r.ok) throw new Error("load");
    list = await r.json();
  } catch (e) {
    if (mine === seq && e.message !== "not authenticated") showLoadError();
    return;
  }
  if (mine !== seq) return;
  state.total = state.categories.reduce((sum, c) => sum + c.count, 0);
  state.list = list;
  if (state.mode === "view" && !list.some((n) => n.id === state.cur)) state.cur = list.length ? list[0].id : null;
  renderList();
  if (!keepDetail || had !== state.cur) renderDetail();
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
function renderCategories() {
  renderFilters();
  const total = state.categories.reduce((sum, c) => sum + c.count, 0);
  const entry = (label, count, on, handler) => h("button", {type: "button", class: "cat" + (on ? " on" : ""), onclick: handler}, h("span", {}, label), h("span", {class: "n"}, count));
  $("#catbar").replaceChildren(
    entry(tr("category_all"), total, state.category === null, () => { state.category = null; renderCategories(); load(); }),
    ...state.categories.map((c) => entry(catLabel(c), c.count, state.category === c.id, () => toggleCategory(c.id))));
}
const TAG_PREVIEW = 9;
let tagsOpen = false;
function fitTags() {                    // collapsed: just the first rows; open: everything; the height change is animated
  const bar = $("#tagbar"), kids = bar.children, many = kids.length > TAG_PREVIEW;
  $("#tagmore").hidden = !many;
  $("#tagmore").classList.toggle("open", tagsOpen);
  $("#tagmoretext").textContent = tagsOpen ? tr("tags_less") : tr("tags_more");
  if (!many) { bar.style.maxHeight = ""; return; }
  const last = kids[TAG_PREVIEW - 1];
  bar.style.maxHeight = (tagsOpen ? bar.scrollHeight : last.offsetTop + last.offsetHeight) + "px";
}
function renderTagbar() {
  renderFilters();
  $("#tagbar").replaceChildren(...state.tags.map((t) => h("button", {type: "button", class: "chip" + (state.sel.has(t.name) ? " on" : ""), onclick: () => toggleTag(t.name)}, "#" + t.name, h("span", {class: "n"}, t.count))));
  fitTags();
}
function categoryBadge(id) {          // the default category is not shown on cards (less noise)
  const c = state.categories.find((x) => x.id === id);
  return c && !c.default ? h("span", {class: "badge cat"}, c.name) : null;
}
function renderList() {
  const tk = tokens(), n = state.list.length;
  $("#results").classList.toggle("searching", !!state.q);   // one line of text per card, two while searching so the match shows
  $("#count").textContent = n === 50 ? tr("top50") : n + " " + T.count[new Intl.PluralRules(LANG).select(n)] + (state.category !== null ? " • " + catName(state.category) : "") + (state.sel.size ? " • " + [...state.sel].map((t) => "#" + t).join(" ") : "");
  const none = !n && !state.q && !state.sel.size && state.category === null && state.total === 0;
  $("#results").replaceChildren(...(n ? state.list.map((note) => h("button", {type: "button", class: "res" + (note.id === state.cur && state.mode === "view" ? " on" : ""), onclick: () => select(note.id)},
    h("div", {class: "ico"}, icon(noteIcon(note), 20)),
    h("div", {},
      h("div", {class: "top"}, h("span", {class: "t"}, hlNodes(note.title, tk)), h("span", {class: "date"}, shortDate(note.created_at))),
      h("div", {class: "s"}, hlNodes(note.body.replace(/\s+/g, " ").slice(0, 160), tk)),
      h("div", {class: "meta"}, categoryBadge(note.category_id), note.tags.map((t) => h("span", {class: "chip mini" + (state.sel.has(t) ? " on" : ""), onclick: (e) => { e.stopPropagation(); toggleTag(t); }}, "#" + t)))),
    h("span", {class: "chev"}, icon("chevron-right", 16)))) : [h("div", {class: "empty"}, tr(none ? "empty_none" : "no_results"))]));
}
function renderDetail() {
  const d = $("#detail");
  if (state.mode === "new") {
    d.replaceChildren(h("div", {class: "card"}, newPanel({
      onCancel: () => { state.mode = "view"; setView("list"); load(); },
      onCreated: async (n) => { state.q = ""; $("#q").value = ""; state.sel.clear(); state.category = null; state.mode = "view"; state.cur = n.id; await loadCategories(); await loadTags(); await load(); toast(tr("toast_created")); }})));
    return;
  }
  const n = state.list.find((x) => x.id === state.cur);
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
const CATEGORY_ERRORS = {
  name_invalid: "category_err_name_invalid", name_reserved: "category_err_name_reserved", name_taken: "category_err_name_taken",
  default_category: "category_err_default_category", not_empty: "category_err_not_empty", not_found: "category_err_not_found",
};
function categoryError(detail) {
  const d = detail && typeof detail === "object" ? detail : {};
  const key = CATEGORY_ERRORS[d.code];
  return key ? tr(key, {count: d.count ?? "?"}) : tr("category_err_failed");
}
// A <select> of the categories plus a quick way to add one without leaving the form.
function categoryField(selectedId) {
  const select = h("select", {"aria-label": tr("label_category")});
  const fill = (id) => { select.replaceChildren(...state.categories.map((c) => h("option", {value: String(c.id)}, catLabel(c)))); select.value = String(id); };
  fill(selectedId);
  window.addEventListener("categorieschanged", function refresh() {   // the management window changed the list
    if (!select.isConnected) { window.removeEventListener("categorieschanged", refresh); return; }
    const keep = Number(select.value);
    fill(state.categories.some((c) => c.id === keep) ? keep : defaultId());
  });
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
  const tags = h("input", {value: init.tags.join(", "), placeholder: tr("label_tags"), autocomplete: "off"});
  const category = categoryField(init.category_id);
  const err = h("div", {class: "err"}, message);
  const el = h("div", {class: "form"}, h("label", {}, tr("label_title")), title, h("label", {}, tr("label_body")), body, h("label", {}, tr("label_tags")), tags, suggestions(tags), h("label", {}, tr("label_category")), category.el, err);
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
  const back = () => { mode = "read"; draft = null; msg = ""; draw(); };
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
  function draw() {
    root.dataset.mode = mode;
    if (mode === "read") {
      const tk = tokens();
      const edit = () => { draft = {title: note.title, body: note.body, tags: [...note.tags], category_id: note.category_id}; msg = ""; mode = "edit"; draw(); };
      const catBadge = h("span", {class: "badge cat"}, catName(note.category_id));
      root.replaceChildren(
        h("div", {class: "hero"},
          svg([["path", {d: "M0 150 C 90 100, 170 200, 270 140 S 390 60, 400 95 V200 H0 Z", fill: "rgba(121,92,255,.35)"}], ["path", {d: "M0 185 C 110 140, 200 210, 300 170 S 380 130, 400 150 V200 H0 Z", fill: "rgba(82,117,255,.3)"}]], {class: "wave", viewBox: "0 0 400 200", "aria-hidden": "true"}),
          h("div", {class: "bar"},
            h("div", {class: "left"},
              h("button", {type: "button", class: "iconbtn back", "aria-label": tr("back"), onclick: () => setView("list")}, icon("chevron-left", 18)),
              h("span", {class: "datebadge"}, icon("calendar", 15), tr("created") + ": " + longDate(note.created_at)),
              catBadge),
            h("div", {class: "tools"},
              h("button", {type: "button", class: "iconbtn", "aria-label": tr("copy"), title: tr("copy"), onclick: () => copyNote(note)}, icon("copy", 17)),
              h("button", {type: "button", class: "iconbtn", "aria-label": tr("edit"), title: tr("edit"), onclick: edit}, icon("pencil", 17)),
              h("button", {type: "button", class: "iconbtn del", "aria-label": tr("delete"), title: tr("delete"), onclick: () => { msg = ""; mode = "del"; draw(); }}, icon("trash", 17)))),
          h("h2", {}, hlNodes(note.title, tk)),
          h("div", {class: "chips"}, note.tags.map((t) => h("button", {type: "button", class: "chip" + (state.sel.has(t) ? " on" : ""), onclick: () => toggleTag(t)}, "#" + t)))),
        h("div", {class: "body"}, hlNodes(note.body, tk)),
        h("div", {class: "err"}, msg));
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

// --- managing categories (a modal dialog; adding also exists as quick add in the note forms)
const manage = {editing: null, deleting: null};
const setCatMsg = (text) => { $("#catmsg").textContent = text; };
async function categoriesChanged() {
  await loadCategories();
  window.dispatchEvent(new Event("categorieschanged"));   // open note forms refill their category lists
  await load(true);
  const panel = $("#detail .panel");
  if (state.mode === "view" && panel && panel.dataset.mode === "read") renderDetail();   // never touches a form being filled in
  renderManage();
}
async function categoryCall(path, method, body) {
  const r = await api(path, body === undefined ? {method} : json(method, body));
  const data = (await r.json().catch(() => null)) || {};   // 204 has no body
  return {r, detail: data.detail};
}
function renderManage() {
  $("#catrows").replaceChildren(...state.categories.map((c) => {
    const li = h("li", {class: "catrow"});
    if (c.default) {
      li.append(h("span", {class: "name"}, catLabel(c)), h("span", {class: "n"}, c.count), h("span", {class: "muted small"}, tr("manage_default_note")));
    } else if (manage.editing === c.id) {
      const input = h("input", {value: c.name, maxlength: 60, "aria-label": tr("manage_rename")});
      const save = async () => {
        const {r, detail} = await categoryCall("/api/categories/" + c.id, "PUT", {name: input.value});
        if (r.ok) { manage.editing = null; setCatMsg(""); await categoriesChanged(); }
        else if (r.status === 404) { manage.editing = null; await categoriesChanged(); }
        else setCatMsg(categoryError(detail));
      };
      input.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); save(); } });
      li.append(input, h("button", {type: "button", class: "btn primary", onclick: save}, tr("save")), h("button", {type: "button", class: "btn", onclick: () => { manage.editing = null; setCatMsg(""); renderManage(); }}, tr("cancel")));
      setTimeout(() => input.focus());
    } else if (manage.deleting === c.id) {
      const remove = async () => {
        const {r, detail} = await categoryCall("/api/categories/" + c.id, "DELETE");
        manage.deleting = null;
        if (r.status === 204 || r.status === 404) { setCatMsg(""); await categoriesChanged(); }   // already gone is fine
        else { setCatMsg(categoryError(detail)); renderManage(); }
      };
      li.append(h("span", {class: "name"}, tr("manage_confirm_delete", {name: c.name})), h("button", {type: "button", class: "btn danger", onclick: remove}, tr("yes_delete")), h("button", {type: "button", class: "btn", onclick: () => { manage.deleting = null; renderManage(); }}, tr("back")));
    } else {
      li.append(h("span", {class: "name"}, c.name), h("span", {class: "n"}, c.count),
        h("button", {type: "button", class: "btn", onclick: () => { manage.editing = c.id; manage.deleting = null; setCatMsg(""); renderManage(); }}, tr("manage_rename")),
        h("button", {type: "button", class: "btn danger", onclick: () => { manage.deleting = c.id; manage.editing = null; setCatMsg(""); renderManage(); }}, tr("delete")));
    }
    return li;
  }));
}
async function addCategory() {
  const input = $("#catnew");
  const {r, detail} = await categoryCall("/api/categories", "POST", {name: input.value});
  if (r.status === 201) { input.value = ""; setCatMsg(""); await categoriesChanged(); input.focus(); }
  else setCatMsg(categoryError(detail));    // here an existing name is an error (the note forms just select it)
}
function openManage() {
  manage.editing = manage.deleting = null;
  setCatMsg("");
  renderManage();
  $("#catdialog").showModal();
  $("#catnew").focus();
}

// --- import (the server validates the whole file and answers with a code we translate)
const IMPORT_ERRORS = {
  not_json: "import_err_not_json", not_an_export: "import_err_not_an_export",
  invalid_file: "import_err_invalid_file",
  count_mismatch: "import_err_count_mismatch", invalid_note: "import_err_invalid_note",
  file_too_large: "import_err_file_too_large",
};
const FIELD_NAMES = {title: "field_title", body: "field_body", tags: "field_tags", created_at: "field_created_at", category: "field_category", note: "field_note"};
function importError(detail) {
  const d = detail && typeof detail === "object" ? detail : {};
  const key = IMPORT_ERRORS[d.code];
  if (!key) return tr("import_err_failed");
  const field = FIELD_NAMES[d.field] ? tr(FIELD_NAMES[d.field]) : "";
  return tr(key, {expected: d.expected ?? "?", actual: d.actual ?? "?", index: d.index ?? "?", field, mb: d.limit_mb ?? "?"});
}
async function importFile(file) {
  const show = (text, ok) => { const m = $("#importmsg"); m.textContent = text; m.className = "msg " + (ok ? "ok" : "bad"); };
  let r;
  try {
    r = await api("/api/import", {method: "POST", headers: {"content-type": "application/json"}, body: await file.text()});
  } catch (e) {
    if (e.message !== "not authenticated") show(tr("import_err_failed"), false);
    return;
  }
  const body = await r.json().catch(() => ({}));
  if (!r.ok) { show(importError(body.detail), false); return; }
  show(tr("import_done", {n: body.imported}), true);
  state.category = null; state.sel.clear(); state.cur = null; state.mode = "view";
  await loadCategories();
  await loadTags();
  await load();
}

// --- wiring
$("#q").addEventListener("input", () => { state.q = $("#q").value; clearTimeout(timer); timer = setTimeout(() => { state.mode = "view"; load(); }, 100); });
$("#new").addEventListener("click", openNew);
$("#managecats").addEventListener("click", openManage);
$("#catclose").addEventListener("click", () => $("#catdialog").close());
$("#catadd").addEventListener("click", addCategory);
$("#catnew").addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); addCategory(); } });
$("#catdialog").addEventListener("click", (e) => { if (e.target === e.currentTarget) e.currentTarget.close(); });   // click on the backdrop
let pending = null;
$("#import").addEventListener("click", () => $("#importfile").click());
$("#importfile").addEventListener("change", async (e) => {
  const file = e.target.files[0];
  e.target.value = "";          // so choosing the same file again fires another change
  if (!file) return;
  pending = file;     // importing replaces everything, so ask first
  $("#importmsg").textContent = "";
  $("#importasktext").textContent = tr("import_ask");
  $("#importask").hidden = false;
  $("#importyes").focus();
});
$("#importyes").addEventListener("click", async () => {
  const file = pending; pending = null; $("#importask").hidden = true;
  if (file) await importFile(file);
});
$("#importno").addEventListener("click", () => { pending = null; $("#importask").hidden = true; });
document.querySelectorAll("[data-lang]").forEach((b) => {
  b.classList.toggle("on", b.dataset.lang === LANG);
  b.addEventListener("click", () => { document.cookie = "lang=" + b.dataset.lang + "; path=/; max-age=31536000; SameSite=Lax"; location.reload(); });
});
const applyTheme = (t) => {
  document.documentElement.dataset.theme = t;
  $("#theme").replaceChildren(icon(t === "light" ? "moon" : "sun"));   // the icon shows what a click switches to
};
let savedTheme = "dark";
try { savedTheme = localStorage.getItem("theme") === "light" ? "light" : "dark"; } catch (e) {}
applyTheme(savedTheme);
$("#theme").addEventListener("click", () => {
  const next = document.documentElement.dataset.theme === "light" ? "dark" : "light";
  applyTheme(next);
  try { localStorage.setItem("theme", next); } catch (e) {}
});
$("#f-all").addEventListener("click", () => { state.sel.clear(); state.category = null; state.mode = "view"; renderTagbar(); renderCategories(); load(); });
$("#f-clear").addEventListener("click", () => resetFilters(true));
$("#tagmore").addEventListener("click", () => { tagsOpen = !tagsOpen; fitTags(); });
const openMenu = (on) => { $("#app").classList.toggle("menu", on); $("#scrim").hidden = !on; };
$("#menu").addEventListener("click", () => openMenu(true));
$("#scrim").addEventListener("click", () => openMenu(false));
$("#shortcut").textContent = /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent) ? "⌘ K" : "Ctrl K";
document.addEventListener("keydown", (e) => {
  if ($("#catdialog").open) return;   // the dialog handles its own keys (Esc closes it natively)
  const typing = /INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName), q = $("#q");
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); q.focus(); q.select(); }
  else if (e.key === "/" && !typing) { e.preventDefault(); q.focus(); }
  else if ((e.key === "n" || e.key === "N") && !typing) { e.preventDefault(); openNew(); }
  else if (e.key === "Escape") { openMenu(false); resetFilters(true); q.focus(); }
  else if ((e.key === "ArrowDown" || e.key === "ArrowUp") && document.activeElement === q && state.list.length) {
    const i = state.list.findIndex((x) => x.id === state.cur);
    const next = state.list[Math.max(0, Math.min(state.list.length - 1, i + (e.key === "ArrowDown" ? 1 : -1)))];
    e.preventDefault(); select(next.id);
  }
});
fillIcons();
skeleton();
loadCategories();
loadTags();
load();
"""
    + r"""</script>
</body>
</html>
"""
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


def render_index(lang: str) -> str:
    payload = json.dumps({"lang": lang, "strings": STRINGS[lang]}, ensure_ascii=False)
    return fill(INDEX_HTML, lang).replace(
        "/*I18N*/", "const I18N = " + payload.replace("</", "<\\/") + ";"
    )
