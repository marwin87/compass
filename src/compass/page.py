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
  --bg:#f6f5f2; --panel:#ffffff; --ink:#1d1d1f; --muted:#6b6b70; --line:#e6e4df;
  --accent:#2f5bea; --accent-soft:#eaf0ff; --mark:#fff1a8; --ok:#1e8a4c; --danger:#c62828; --danger-soft:#fdeaea;
  --r:12px; --shadow:0 1px 2px rgba(0,0,0,.04),0 8px 24px rgba(0,0,0,.06);
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme=light]){ --bg:#131316; --panel:#1c1c20; --ink:#ececef; --muted:#9a9aa3; --line:#2c2c33;
    --accent:#7d9bff; --accent-soft:#1f2741; --mark:#5b4e10; --danger:#ff8a80; --danger-soft:#3a2020; --shadow:0 1px 2px rgba(0,0,0,.4),0 8px 24px rgba(0,0,0,.4); }
}
:root[data-theme=dark]{ --bg:#131316; --panel:#1c1c20; --ink:#ececef; --muted:#9a9aa3; --line:#2c2c33;
  --accent:#7d9bff; --accent-soft:#1f2741; --mark:#5b4e10; --danger:#ff8a80; --danger-soft:#3a2020; --shadow:0 1px 2px rgba(0,0,0,.4),0 8px 24px rgba(0,0,0,.4); }
*{box-sizing:border-box}
html{color-scheme:light dark}
body{margin:0;font-family:Inter,system-ui,-apple-system,"Segoe UI",sans-serif;background:var(--bg);color:var(--ink);font-size:14px;line-height:1.5}
button{font:inherit;cursor:pointer}
input,textarea{font:inherit;color:var(--ink)}
[hidden]{display:none!important}
mark{background:var(--mark);color:inherit;border-radius:3px;padding:0 1px}
kbd{font-family:ui-monospace,"JetBrains Mono",monospace;font-size:11px;border:1px solid var(--line);border-bottom-width:2px;border-radius:5px;padding:1px 5px;color:var(--muted);background:var(--bg)}
.muted{color:var(--muted)}
.btn{border:1px solid var(--line);background:var(--panel);color:var(--ink);border-radius:8px;padding:6px 12px;font-size:13px}
.btn:hover{border-color:var(--accent)}
.btn.primary{background:var(--accent);border-color:var(--accent);color:#fff}
.btn.danger{border-color:var(--danger);color:var(--danger)}
.btn.danger:hover{background:var(--danger-soft)}
.btn.icon{padding:6px 9px}
.btn.on{background:var(--accent-soft);border-color:var(--accent);color:var(--accent);font-weight:600}
.langs{display:flex;gap:4px}
.chip{display:inline-flex;align-items:center;gap:4px;border:1px solid var(--line);background:var(--panel);color:var(--ink);border-radius:999px;padding:2px 10px;font-size:12px}
.chip:hover{border-color:var(--accent)}
.chip.on{background:var(--accent);border-color:var(--accent);color:#fff}
.chip .n{color:var(--muted);font-size:11px}
.chip.on .n{color:#dfe6ff}
.chip.ghost{border-style:dashed;color:var(--muted)}
.chip.mini{font-size:11px;padding:0 8px;background:var(--bg);color:var(--muted)}
.chip.mini.on{background:var(--accent);color:#fff}
.chips{display:flex;flex-wrap:wrap;gap:6px}
.badge{font-size:10px;font-weight:600;border-radius:4px;padding:0 6px;border:1px solid var(--line);color:var(--muted);text-transform:uppercase;letter-spacing:.04em}
.badge.tag{color:var(--ok);border-color:var(--ok)}
.badge.title{color:var(--accent);border-color:var(--accent)}
.panel .meta{font-size:12px;color:var(--muted)}
.panel h2{margin:4px 0 10px;font-size:24px;letter-spacing:-.01em}
.panel .body{white-space:pre-wrap;font-size:15px;margin:0 0 14px}
.panel .actions,.panel .confirm,.panel .row{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-top:14px}
.panel .confirm{background:var(--danger-soft);border:1px solid var(--danger);border-radius:10px;padding:10px 12px}
.panel .confirm.warn{background:var(--accent-soft);border-color:var(--accent)}
.form{display:grid;gap:8px}
.form label{font-size:11px;font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:.05em;margin-top:6px}
.form input,.form textarea{width:100%;border:1px solid var(--line);border-radius:8px;padding:9px 11px;background:var(--bg)}
.form input:focus,.form textarea:focus{outline:2px solid var(--accent-soft);border-color:var(--accent)}
.form textarea{min-height:130px;resize:vertical}
.err{color:var(--danger);font-size:13px;min-height:1em}
.empty{color:var(--muted);text-align:center;padding:36px 10px}
.toast{position:fixed;bottom:20px;left:50%;transform:translateX(-50%);background:var(--ink);color:var(--bg);padding:8px 16px;border-radius:999px;font-size:13px;opacity:0;transition:opacity .2s;pointer-events:none;z-index:50}
.toast.show{opacity:1}
.login{min-height:100vh;display:grid;place-items:center;padding:20px}
.login .card{width:min(380px,100%);background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:28px;box-shadow:var(--shadow)}
.login h1{margin:0 0 4px;font-size:22px}
.logo{display:flex;align-items:center;gap:10px;font-weight:700;font-size:18px}
.logo .dot{width:26px;height:26px;border-radius:8px;background:var(--accent);display:grid;place-items:center;color:#fff;font-size:14px}
.protonote{font-size:12px;color:var(--muted);border-left:3px solid var(--accent);padding-left:10px;margin-top:14px}
"""

APP_CSS = r"""
.app{display:grid;grid-template-columns:250px 1fr;min-height:100vh}
aside{border-right:1px solid var(--line);padding:18px 14px;background:var(--panel);position:sticky;top:0;height:100vh;overflow:auto;display:flex;flex-direction:column;gap:6px}
.tagline{font-size:12px;margin-bottom:14px}
.wide{width:100%;padding:9px 12px}
h4{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin:18px 4px 6px}
.legend{margin:0;padding-left:18px;font-size:12px}
.spacer{flex:1}
.row{display:flex;gap:8px;align-items:center}
.row form{margin:0}
main{padding:22px 28px;max-width:1240px;width:100%}
.searchbar{display:flex;align-items:center;gap:10px;background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:10px 14px;box-shadow:0 1px 2px rgba(0,0,0,.03)}
.searchbar:focus-within{border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-soft)}
.searchbar input{flex:1;border:0;outline:0;background:none;font-size:17px}
.hint{color:var(--muted);font-size:12px;margin:8px 4px 16px;display:flex;gap:14px;flex-wrap:wrap}
.grid{display:grid;grid-template-columns:minmax(280px,400px) 1fr;gap:18px;align-items:start}
.count{color:var(--muted);font-size:12px;margin:0 4px 6px}
.results{display:flex;flex-direction:column;gap:8px}
.res{background:var(--panel);border:1px solid var(--line);border-radius:var(--r);padding:12px 14px;text-align:left;color:var(--ink);width:100%}
.res:hover{border-color:#c9c6bf}
.res.on{border-color:var(--accent);box-shadow:0 0 0 2px var(--accent-soft)}
.res .t{font-weight:600}
.res .s{color:var(--muted);font-size:13px;margin:3px 0 7px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.res .meta{display:flex;gap:5px;flex-wrap:wrap;align-items:center}
.card{background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:22px 24px;position:sticky;top:16px;box-shadow:var(--shadow)}
@media (max-width:900px){.app{grid-template-columns:1fr}aside{position:static;height:auto}.grid{grid-template-columns:1fr}.card{position:static}main{padding:16px}}
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
<div class="app">
  <aside>
    <div class="logo"><div class="dot">🧭</div>Compass</div>
    <div class="muted tagline">[[tagline]]</div>
    <button type="button" class="btn primary wide" id="new">[[new_note]]</button>
    <h4>[[tags_h]]</h4>
    <div class="chips" id="tagbar"></div>
    <h4>[[how_h]]</h4>
    <ul class="legend muted">
      <li>[[legend1]]</li>
      <li>[[legend2]]</li>
      <li>[[legend3]]</li>
    </ul>
    <div class="spacer"></div>
    <div class="row">
      <button type="button" class="btn icon" id="theme" title="[[theme_title]]">◐</button>
      <div class="row langs" role="group" aria-label="[[lang_label]]">
        <button type="button" class="btn icon" data-lang="pl">PL</button>
        <button type="button" class="btn icon" data-lang="en">EN</button>
      </div>
    </div>
    <form method="post" action="/logout"><button class="btn wide">[[logout]]</button></form>
  </aside>
  <main>
    <div class="searchbar">🔎<input id="q" placeholder="[[search_ph]]" autocomplete="off" autofocus><kbd>/</kbd></div>
    <div class="hint">
      <span><kbd>↑</kbd><kbd>↓</kbd> [[hint_select]]</span><span><kbd>N</kbd> [[hint_new]]</span><span><kbd>Esc</kbd> [[hint_clear]]</span>
    </div>
    <div class="grid">
      <div><div class="count" id="count"></div><div class="results" id="results"></div></div>
      <div id="detail"></div>
    </div>
  </main>
</div>
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
function toast(msg) { const t = $("#toast"); t.textContent = msg; t.classList.add("show"); clearTimeout(t._h); t._h = setTimeout(() => t.classList.remove("show"), 1800); }

// --- state and server calls
const state = {q: "", sel: new Set(), cur: null, mode: "view", list: [], tags: []};
let seq = 0, timer;
async function api(path, opts) {
  const r = await fetch(path, opts);
  if (r.status === 401) { location.href = "/login"; throw new Error("not authenticated"); }
  return r;
}
const json = (method, body) => ({method, headers: {"content-type": "application/json"}, body: JSON.stringify(body)});
const tokens = () => words(state.q);
const SAVE_ERROR = tr("save_error");

async function loadTags() {
  state.tags = await (await api("/api/tags")).json();
  for (const t of [...state.sel]) if (!state.tags.some((x) => x.name === t)) state.sel.delete(t);
  renderTagbar();
}
async function load(keepDetail = false) {
  const mine = ++seq, had = state.cur;
  const params = new URLSearchParams({q: state.q});
  for (const t of state.sel) params.append("tag", t);
  const list = await (await api("/api/notes?" + params)).json();
  if (mine !== seq) return;
  state.list = list;
  if (state.mode === "view" && !list.some((n) => n.id === state.cur)) state.cur = list.length ? list[0].id : null;
  renderList();
  if (!keepDetail || had !== state.cur) renderDetail();
}
function toggleTag(t) { state.sel.has(t) ? state.sel.delete(t) : state.sel.add(t); renderTagbar(); load(); }
function openNew() { state.mode = "new"; state.cur = null; renderList(); renderDetail(); }
function select(id) { state.cur = id; state.mode = "view"; renderList(); renderDetail(); }

// --- rendering
function renderTagbar() {
  $("#tagbar").replaceChildren(...state.tags.map((t) => h("button", {class: "chip" + (state.sel.has(t.name) ? " on" : ""), onclick: () => toggleTag(t.name)}, "#" + t.name, h("span", {class: "n"}, t.count))));
}
function renderList() {
  const tk = tokens(), n = state.list.length;
  $("#count").textContent = n === 50 ? tr("top50") : n + " " + T.count[new Intl.PluralRules(LANG).select(n)] + (state.sel.size ? " · " + [...state.sel].map((t) => "#" + t).join(" ") : "");
  $("#results").replaceChildren(...(n ? state.list.map((note) => h("button", {class: "res" + (note.id === state.cur && state.mode === "view" ? " on" : ""), onclick: () => select(note.id)},
    h("div", {class: "t"}, hlNodes(note.title, tk)),
    h("div", {class: "s"}, hlNodes(note.body.replace(/\s+/g, " ").slice(0, 160), tk)),
    h("div", {class: "meta"}, note.tags.map((t) => h("span", {class: "chip mini" + (state.sel.has(t) ? " on" : ""), onclick: (e) => { e.stopPropagation(); toggleTag(t); }}, "#" + t))))) : [h("div", {class: "empty"}, tr("no_results"))]));
}
function renderDetail() {
  const d = $("#detail");
  if (state.mode === "new") {
    d.replaceChildren(h("div", {class: "card"}, newPanel({
      onCancel: () => { state.mode = "view"; load(); },
      onCreated: async (n) => { state.q = ""; $("#q").value = ""; state.sel.clear(); state.mode = "view"; state.cur = n.id; await loadTags(); await load(); toast(tr("toast_created")); }})));
    return;
  }
  const n = state.list.find((x) => x.id === state.cur);
  if (!n) { d.replaceChildren(h("div", {class: "card"}, h("div", {class: "empty"}, tr("pick_or_add")))); return; }
  d.replaceChildren(h("div", {class: "card"}, notePanel(n, {
    onChange: async () => { await loadTags(); await load(true); toast(tr("toast_saved")); },
    onDeleted: async () => { state.cur = null; await loadTags(); await load(); toast(tr("toast_deleted")); }})));
}

// --- forms and the note panel (edit and delete each need a second, explicit confirmation)
function suggestions(input) {
  return h("div", {class: "chips"}, state.tags.slice(0, 24).map((t) => h("button", {type: "button", class: "chip ghost", onclick: () => {
    const have = readTags(input.value).tags;
    if (!have.includes(t.name)) input.value = have.concat(t.name).join(", ");
    input.focus();
  }}, t.name)));
}
function noteForm(init, message) {
  const title = h("input", {value: init.title, maxlength: 200, placeholder: tr("label_title")});
  const body = h("textarea", {value: init.body, placeholder: tr("label_body"), maxlength: 20000});
  const tags = h("input", {value: init.tags.join(", "), placeholder: tr("label_tags"), autocomplete: "off"});
  const err = h("div", {class: "err"}, message);
  const el = h("div", {class: "form"}, h("label", {}, tr("label_title")), title, h("label", {}, tr("label_body")), body, h("label", {}, tr("label_tags")), tags, suggestions(tags), err);
  return {el, err, focus: () => title.focus(), values() {
    const t = readTags(tags.value), ti = title.value.trim();
    err.textContent = !ti ? tr("empty_title") : t.error;
    return err.textContent ? null : {title: ti, body: body.value, tags: t.tags};
  }};
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
    if (mode === "read") {
      const tk = tokens();
      root.replaceChildren(
        h("div", {class: "meta"}, tr("created") + " " + note.created_at.slice(0, 10)),
        h("h2", {}, hlNodes(note.title, tk)),
        h("div", {class: "body"}, hlNodes(note.body, tk)),
        h("div", {class: "chips"}, note.tags.map((t) => h("button", {class: "chip" + (state.sel.has(t) ? " on" : ""), onclick: () => toggleTag(t)}, "#" + t))),
        h("div", {class: "actions"},
          h("button", {class: "btn", onclick: () => { draft = {title: note.title, body: note.body, tags: [...note.tags]}; msg = ""; mode = "edit"; draw(); }}, tr("edit")),
          h("button", {class: "btn danger", onclick: () => { msg = ""; mode = "del"; draw(); }}, tr("delete"))),
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
  const f = noteForm({title: "", body: "", tags: []}, "");
  const root = h("div", {class: "panel"}, h("h2", {}, tr("new_note_h")), f.el, h("div", {class: "row"},
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
document.querySelectorAll("[data-lang]").forEach((b) => {
  b.classList.toggle("on", b.dataset.lang === LANG);
  b.addEventListener("click", () => { document.cookie = "lang=" + b.dataset.lang + "; path=/; max-age=31536000; SameSite=Lax"; location.reload(); });
});
$("#theme").addEventListener("click", () => {
  const d = document.documentElement, dark = d.dataset.theme ? d.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
  d.dataset.theme = dark ? "light" : "dark";
});
document.addEventListener("keydown", (e) => {
  const typing = /INPUT|TEXTAREA/.test(document.activeElement.tagName), q = $("#q");
  if (e.key === "/" && !typing) { e.preventDefault(); q.focus(); }
  else if ((e.key === "n" || e.key === "N") && !typing) { e.preventDefault(); openNew(); }
  else if (e.key === "Escape") { state.q = ""; q.value = ""; state.sel.clear(); state.mode = "view"; renderTagbar(); load(); q.focus(); }
  else if ((e.key === "ArrowDown" || e.key === "ArrowUp") && document.activeElement === q && state.list.length) {
    const i = state.list.findIndex((x) => x.id === state.cur);
    const next = state.list[Math.max(0, Math.min(state.list.length - 1, i + (e.key === "ArrowDown" ? 1 : -1)))];
    e.preventDefault(); select(next.id);
  }
});
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
