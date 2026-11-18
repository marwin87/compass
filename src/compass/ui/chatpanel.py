"""The chat with the notes (AI): its panel in the detail column, embedded into the notes page.

One panel lives for the whole page session (the page keeps it, so opening a source note and coming back
loses nothing). A conversation is created on the first question, so no empty ones are saved. Rules:
`docs/STYLE_GUIDE.md` section 9.
"""

CHAT_CSS = r"""
.chatcard{display:flex;flex-direction:column;height:100%;min-height:440px}
.chat{display:flex;flex-direction:column;flex:1;min-height:0}
.chat .aihd{flex-wrap:wrap;padding:12px 18px}
.dd{position:relative;flex:1 1 130px;min-width:110px;max-width:230px}
.ddbtn{width:100%;display:flex;align-items:center;justify-content:space-between;gap:8px;padding:6px 10px 6px 12px;font-size:13px;font-weight:600;color:var(--ink);background:var(--panel);border:1px solid var(--line);border-radius:12px;cursor:pointer;transition:border-color var(--ease),box-shadow var(--ease)}
.ddbtn span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.ddbtn svg{flex:none;color:var(--muted);transition:transform var(--ease)}
.ddbtn:hover{border-color:var(--line-strong)}
.ddbtn:focus-visible,.dd.open .ddbtn{outline:0;border-color:var(--line-strong);box-shadow:0 0 0 3px var(--ai-soft)}
.dd.open .ddbtn svg{transform:rotate(180deg)}
.chat .chatname{flex:1 1 130px;min-width:110px;max-width:230px;padding:6px 12px;font-size:13px;font-weight:600;color:var(--ink);background:var(--panel);border:1px solid var(--line-strong);border-radius:12px;box-shadow:0 0 0 3px var(--ai-soft);outline:0}
.ddmenu{position:absolute;z-index:5;left:0;top:calc(100% + 6px);min-width:100%;width:max-content;max-width:min(380px,80vw);max-height:260px;overflow:auto;padding:6px;margin:0;list-style:none;background:var(--panel);border:1px solid var(--line);border-radius:16px;box-shadow:var(--shadow);scrollbar-width:thin}
.ddmenu[hidden]{display:none}
.ddopt{display:flex;align-items:center;gap:8px;padding:8px 12px;font-size:13px;font-weight:500;border-radius:10px;cursor:pointer;color:var(--ink);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.ddopt.hot{background:var(--ai-soft)}
.ddopt[aria-selected=true]{font-weight:700}
.ddopt[aria-selected=true]::before{content:"";flex:none;width:6px;height:6px;border-radius:50%;background:linear-gradient(135deg,var(--ai1),var(--ai2))}
.ddopt:not([aria-selected=true])::before{content:"";flex:none;width:6px}
.chat .aihd .btn{padding:5px 10px;font-size:12px}
.chat .aihd .btn.icon{padding:5px 8px}
.chat .chatask{display:flex;align-items:center;gap:10px;padding:10px 18px;font-size:13px;border-bottom:1px solid var(--line)}
.chatlog{flex:1;min-height:0;overflow:auto;padding:18px;display:flex;flex-direction:column;gap:14px;scrollbar-width:thin}
.chatempty{margin:auto;max-width:420px;text-align:center;color:var(--muted);font-size:14px;line-height:1.6}
.chatempty svg{color:var(--ai1);margin-bottom:8px}
.chatmsg{max-width:min(720px,100%);font-size:14.5px;line-height:1.65;overflow-wrap:anywhere}
.chatmsg.user{align-self:flex-end;background:var(--ai-soft);border-radius:16px 16px 4px 16px;padding:9px 14px;white-space:pre-wrap}
.chatmsg.bot{align-self:flex-start;background:var(--raise);border:1px solid var(--line);border-radius:16px 16px 16px 4px;padding:12px 16px;min-width:0}
.chatmsg.bot .md{font-size:14.5px}
.chatmsg.bot .md>:first-child{margin-top:0}.chatmsg.bot .md>:last-child{margin-bottom:0}
.chatmsg .aithink{flex-direction:row;padding:2px 0;gap:10px}
.chatmsg .aierr{padding:0}
.chatmsg .aierr .btn{margin-left:10px;padding:4px 10px;font-size:12px}
.chatsrc{display:flex;flex-wrap:wrap;align-items:center;gap:6px;margin-top:10px;padding-top:9px;border-top:1px solid var(--line)}
.chatsrc .lbl{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--faint);margin-right:2px}
.srcchip{display:inline-flex;align-items:center;gap:6px;max-width:100%;padding:3px 10px;font:inherit;font-size:12.5px;color:var(--ink);background:var(--panel);border:1px solid var(--line);border-radius:999px;cursor:pointer;transition:border-color var(--ease)}
.srcchip:hover{border-color:var(--line-strong)}
.srcchip b{color:var(--ai1)}
.srcchip.gone{cursor:default;color:var(--faint);text-decoration:line-through}
.chatform{padding:12px 18px 6px;border-top:1px solid var(--line)}
.chatbox{display:flex;flex-direction:column;gap:6px;padding:12px 12px 10px 16px;background:var(--bg);border:1px solid var(--line);border-radius:18px;transition:border-color var(--ease),box-shadow var(--ease)}
.chatbox:focus-within{border-color:var(--line-strong);box-shadow:0 0 0 3px var(--ai-soft)}
.chatbox textarea{display:block;width:100%;min-height:72px;max-height:220px;resize:none;margin:0;padding:0;border:0;outline:0;background:none;font-size:15.5px;line-height:1.55}
.chatbox textarea::placeholder{color:var(--faint)}
.chatbox .chatbar{display:flex;justify-content:flex-end}
.chatbox .btn{border-radius:12px;padding:8px 20px}
.chatnote{padding:0 18px 12px;font-size:12px;color:var(--faint)}
@media (max-width:900px){.chatcard{min-height:calc(100dvh - 120px)}}
"""

CHAT_JS = r"""
// A dropdown with rounded corners (a native <select> popup cannot be styled): button + listbox, keyboard and outside-click aware.
function dropdown(label, onpick) {
  let items = [], value = "", hot = 0;
  const text = h("span", {}), menu = h("ul", {class: "ddmenu", role: "listbox", "aria-label": label, hidden: true});
  const btn = h("button", {type: "button", class: "ddbtn", "aria-haspopup": "listbox", "aria-expanded": "false", "aria-label": label}, text, icon("chevron-down", 14));
  const el = h("div", {class: "dd"}, btn, menu);
  const isOpen = () => !menu.hidden;
  function paint() {
    menu.replaceChildren(...items.map((o, i) => h("li", {class: "ddopt" + (i === hot ? " hot" : ""), role: "option", "aria-selected": o.value === value ? "true" : "false", title: o.label,
      onmousedown: (e) => e.preventDefault(), onclick: () => pick(i), onmousemove: () => { if (hot !== i) { hot = i; paint(); } }}, o.label)));
    const cur = items.find((o) => o.value === value);
    text.textContent = cur ? cur.label : "";
  }
  function open(on) {
    menu.hidden = !on; el.classList.toggle("open", on); btn.setAttribute("aria-expanded", on ? "true" : "false");
    if (on) { hot = Math.max(0, items.findIndex((o) => o.value === value)); paint(); const h0 = menu.children[hot]; if (h0) h0.scrollIntoView({block: "nearest"}); }
  }
  function pick(i) { open(false); btn.focus(); if (items[i] && items[i].value !== value) onpick(items[i].value); }
  btn.addEventListener("click", () => open(!isOpen()));
  btn.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && isOpen()) { e.preventDefault(); e.stopPropagation(); open(false); }
    else if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      if (!isOpen()) open(true); else { hot = Math.max(0, Math.min(items.length - 1, hot + (e.key === "ArrowDown" ? 1 : -1))); paint(); menu.children[hot].scrollIntoView({block: "nearest"}); }
    }
    else if ((e.key === "Enter" || e.key === " ") && isOpen()) { e.preventDefault(); pick(hot); }
  });
  document.addEventListener("mousedown", (e) => { if (isOpen() && !el.contains(e.target)) open(false); });
  btn.addEventListener("blur", () => setTimeout(() => { if (isOpen() && !el.contains(document.activeElement)) open(false); }, 0));
  return {el, set(list, v) { items = list; value = v; paint(); }, value: () => value};
}
// --- the chat with the notes. cb.openNote(id, title) shows a source note, cb.close() leaves the chat; the page keeps this panel alive
const CHAT_ERRORS = {not_enabled: "ai_err_not_enabled", not_configured: "ai_err_not_configured", timeout: "ai_err_timeout", failed: "ai_err_failed_chat"};
function makeChat(cb) {
  let convs = [], cur = {id: null, messages: []}, run = null;      // run: the question being answered, {ctrl}
  const select = dropdown(tr("chat_list_label"), (v) => openConv(v));
  const del = h("button", {type: "button", class: "btn icon", "aria-label": tr("chat_delete"), title: tr("chat_delete"), onclick: () => askDelete(true)}, icon("trash", 14));
  const nameIn = h("input", {class: "chatname", maxlength: "200", autocomplete: "off", "aria-label": tr("chat_rename"), placeholder: tr("chat_rename"), hidden: true});
  const rename = h("button", {type: "button", class: "btn icon", "aria-label": tr("chat_rename"), title: tr("chat_rename"), onclick: () => editName(true)}, icon("pencil", 14));
  const ask = h("div", {class: "chatask", hidden: true}, h("span", {}, tr("chat_delete_ask")),
    h("button", {type: "button", class: "btn danger", onclick: removeConv}, tr("yes_delete")), h("button", {type: "button", class: "btn", onclick: () => askDelete(false)}, tr("back")));
  const head = h("div", {class: "aihd"},
    icon("spark", 16), h("span", {}, tr("chat_h")), select.el, nameIn, h("button", {type: "button", class: "btn icon", "aria-label": tr("chat_new"), title: tr("chat_new"), onclick: () => openConv("")}, icon("plus", 14)), rename, del, h("span", {class: "grow"}), aiTag(),
    h("button", {type: "button", class: "btn icon", "aria-label": tr("ai_close"), title: tr("ai_close"), onclick: cb.close}, icon("x", 14)));
  const log = h("div", {class: "chatlog", role: "log", "aria-live": "polite"});
  const input = h("textarea", {rows: "3", maxlength: "4000", placeholder: tr("chat_ph"), "aria-label": tr("chat_ph")});
  const send = h("button", {type: "button", class: "btn primary", onclick: () => run ? stop() : ask1(input.value)}, tr("chat_send"));
  const grow = () => { input.style.height = "auto"; input.style.height = Math.min(220, input.scrollHeight) + "px"; };      // the box grows with the text, up to a limit
  input.addEventListener("input", grow);
  input.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); if (!run) ask1(input.value); } });
  const el = h("div", {class: "chat"}, head, ask, log, h("div", {class: "chatform"}, h("div", {class: "chatbox"}, input, h("div", {class: "chatbar"}, send))), h("div", {class: "chatnote"}, tr("chat_hint")));
  const down = () => { log.scrollTop = log.scrollHeight; };
  const askDelete = (on) => { ask.hidden = !on; };
  function editName(on) {          // the dropdown turns into a text field: Enter saves, Esc or leaving cancels
    if (on && !cur.id) return;
    select.el.hidden = on; nameIn.hidden = !on;
    if (on) { nameIn.value = cur.title || ""; nameIn.focus(); nameIn.select(); }
  }
  async function saveName() {
    const title = nameIn.value.trim(), id = cur.id;
    editName(false);
    if (!title || title === cur.title) return;
    try {
      const r = await api("/api/chats/" + id, json("PATCH", {title}));
      if (!r.ok) throw new Error("rename");
      if (cur.id === id) cur.title = title;
    } catch (e) { if (e.message !== "not authenticated") toast(tr("chat_rename_failed"), "bad", 4000); }
    loadList();
  }
  nameIn.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.isComposing) { e.preventDefault(); saveName(); }
    else if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); editName(false); }
  });
  nameIn.addEventListener("blur", () => { if (!nameIn.hidden) editName(false); });
  function fillList(value) {
    select.set([{value: "", label: tr("chat_new")}, ...convs.map((c) => ({value: String(c.id), label: c.title || tr("chat_untitled")}))], value);
    del.hidden = rename.hidden = !cur.id;
  }
  async function loadList() {
    try { const r = await api("/api/chats"); if (r.ok) convs = await r.json(); } catch (e) { /* the list is a convenience: a new chat still works */ }
    const mine = cur.id && convs.find((c) => c.id === cur.id);
    if (mine) cur.title = mine.title;
    fillList(cur.id ? String(cur.id) : "");
  }
  async function openConv(id) {
    if (run) return;      // an answer is being written: the list stays where it is
    askDelete(false); editName(false);
    cur = {id: null, messages: []};
    if (id) {
      try {
        const r = await api("/api/chats/" + id);
        if (!r.ok) throw new Error("chat");
        cur = await r.json();
      } catch (e) { if (e.message !== "not authenticated") toast(tr("load_failed"), "bad"); await loadList(); }
    }
    fillList(cur.id ? String(cur.id) : ""); draw(); input.focus();
  }
  async function removeConv() {
    const id = cur.id; askDelete(false);
    try { const r = await api("/api/chats/" + id, {method: "DELETE"}); if (r.status !== 204 && r.status !== 404) throw new Error("delete"); }
    catch (e) { if (e.message !== "not authenticated") toast(tr("chat_delete_failed"), "bad", 4000); return; }
    cur = {id: null, messages: []}; await loadList(); draw();
  }
  const md = (text) => h("article", {class: "md"}, mdBlocksDom(mdParse(text), {tk: [], heads: [], lang: ""}));
  function sources(list) {
    if (!list.length) return null;
    return h("div", {class: "chatsrc"}, h("span", {class: "lbl"}, tr("chat_sources")), list.map((s, i) => s.deleted
      ? h("span", {class: "srcchip gone", title: tr("chat_source_deleted")}, h("b", {}, String(i + 1)), s.title)
      : h("button", {type: "button", class: "srcchip", onclick: () => cb.openNote(s.id, s.title)}, h("b", {}, String(i + 1)), s.title)));
  }
  const bubble = (m) => m.role === "user" ? h("div", {class: "chatmsg user"}, m.text) : h("div", {class: "chatmsg bot"}, md(m.text), sources(m.sources || []));
  function draw() {
    log.replaceChildren(...(cur.messages.length ? cur.messages.map(bubble) : [h("div", {class: "chatempty"}, icon("chat-compass", 28), h("div", {}, tr("chat_empty")))]));
    down();
  }
  const thinking = (text) => h("div", {class: "aithink", role: "status"}, icon("spark", 16), h("span", {}, text));
  function stop() { if (run) run.ctrl.abort(); }
  async function ask1(raw) {
    const question = raw.trim();
    if (!question || run) return;
    askDelete(false);
    const ctrl = new AbortController(); run = {ctrl}; send.textContent = tr("chat_stop"); input.value = ""; grow();
    const user = h("div", {class: "chatmsg user"}, question), bot = h("div", {class: "chatmsg bot"}, thinking(tr("chat_thinking")));
    if (!cur.messages.length) log.replaceChildren();
    log.append(user, bot); down();
    const fail = (code) => bot.replaceChildren(h("div", {class: "err aierr", role: "alert"}, tr(CHAT_ERRORS[code] || "ai_err_failed_chat"),
      h("button", {type: "button", class: "btn", onclick: () => { user.remove(); bot.remove(); if (!log.children.length) draw(); ask1(question); }}, tr("retry"))));
    aiBusy(() => el);
    let finished = false, text = "", frame = 0;
    const show = () => { frame = 0; bot.replaceChildren(md(text)); down(); };
    try {
      if (!cur.id) {
        const c = await api("/api/chats", {method: "POST"});
        if (!c.ok) throw new Error("chat");
        cur.id = (await c.json()).id;
      }
      const resp = await api("/api/chats/" + cur.id + "/ask", {...json("POST", {question}), signal: ctrl.signal});
      if (!resp.ok) { const d = (await resp.json().catch(() => ({}))).detail; fail(d && d.code); return; }
      const reader = resp.body.getReader(), decoder = new TextDecoder();
      let buffer = "";
      for (;;) {
        const {value, done} = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, {stream: true});
        let nl;
        while ((nl = buffer.indexOf("\n")) >= 0) {
          const line = buffer.slice(0, nl); buffer = buffer.slice(nl + 1);
          if (!line) continue;
          const e = JSON.parse(line);
          if (e.type === "indexing") bot.replaceChildren(thinking(tr("chat_indexing", {done: e.done, total: e.total})));
          else if (e.type === "excerpts") bot.replaceChildren(thinking(tr("chat_reading")));
          else if (e.type === "delta") { text += e.text; if (!frame) frame = requestAnimationFrame(show); }
          else if (e.type === "error") { fail(e.code); return; }
          else if (e.type === "done") {
            cancelAnimationFrame(frame); finished = true;
            cur.messages.push({role: "user", text: question}, {role: "assistant", text: e.text, sources: e.sources});
            draw(); loadList();
          }
        }
      }
      if (!finished) fail("failed");
    } catch (e) {
      if (e.message === "not authenticated") return;
      if (e.name === "AbortError") { cancelAnimationFrame(frame); user.remove(); bot.remove(); input.value = question; grow(); if (!cur.messages.length) draw(); }   // stopped: nothing was saved, the question comes back
      else fail("failed");
    } finally {
      aiBusy(null); run = null; send.textContent = tr("chat_send");
      if (cur.id && !convs.some((c) => c.id === cur.id)) loadList();
    }
  }
  draw(); loadList();
  return {el, show: () => { loadList(); setTimeout(() => input.focus()); }};
}
"""
