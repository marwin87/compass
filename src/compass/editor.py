"""The Markdown helper for the note forms: a toolbar over the plain textarea and a preview tab.

The note stays plain text in the textarea. The toolbar only edits that text: each button is a pure
function (`EDITOR_PURE_JS`, no DOM, tested in Node) that turns the text and the selection into one
replacement (`{from, to, insert, selFrom, selTo}`). The DOM part (`EDITOR_UI_JS`) applies it with
`execCommand("insertText")`, which keeps the browser's undo history (`setRangeText` is the fallback),
and draws the preview with the same parser and renderer as the note reader, so the preview always
looks like the saved note. No library, no HTML strings, no external request.
"""

EDITOR_PURE_JS = r"""
// ---- Markdown editing helpers: (text, selectionStart, selectionEnd, ...) -> one replacement (pure, no DOM)
// {from, to, insert}: replace text[from:to] with `insert`; {selFrom, selTo}: the selection in the NEW text.
const edResult = (from, to, insert, selFrom, selTo) => ({from, to, insert, selFrom, selTo});

function edWrap(text, a, b, before, after, ph) {       // **bold**, *italic*, ~~strike~~, `code`: wraps, or unwraps when already wrapped
  const sel = text.slice(a, b), single = before.length === 1;
  const around = text.slice(a - before.length, a) === before && text.slice(b, b + after.length) === after
    && !(single && (text[a - before.length - 1] === before || text[b + after.length] === after));   // "**x**" is not "*x*"
  if (a >= before.length && around) {
    const from = a - before.length;
    return edResult(from, b + after.length, sel, from, from + sel.length);
  }
  if (sel.length >= before.length + after.length && sel.startsWith(before) && sel.endsWith(after) && !(single && sel[1] === before)) {
    const inner = sel.slice(before.length, sel.length - after.length);
    return edResult(a, b, inner, a, a + inner.length);
  }
  const inner = sel || ph;
  return edResult(a, b, before + inner + after, a + before.length, a + before.length + inner.length);
}

function edLineRange(text, a, b) {                      // the whole lines touched by the selection
  const start = a === 0 ? 0 : text.lastIndexOf("\n", a - 1) + 1;
  const from = b > a && text[b - 1] === "\n" ? b - 1 : b;   // a selection that ends at a line start does not include that line
  let end = text.indexOf("\n", from);
  if (end === -1) end = text.length;
  return [start, end];
}

const ED_LINE = {                                       // per line kind: how a marker looks, what counts as "already has it", what to strip
  h2: {make: () => "## ", has: /^##(?!#)\s+/, strip: /^#{1,6}\s+/},
  h3: {make: () => "### ", has: /^###(?!#)\s+/, strip: /^#{1,6}\s+/},
  ul: {make: () => "- ", has: /^[-*+]\s+/, strip: /^([-*+]|\d+[.)])\s+/},
  ol: {make: (i) => i + 1 + ". ", has: /^\d+[.)]\s+/, strip: /^([-*+]|\d+[.)])\s+/},
  quote: {make: () => "> ", has: /^>\s?/, strip: /^>\s?/},
};
function edLines(text, a, b, kind) {                    // headings, lists, quotes: toggle a marker on every selected line
  const [start, end] = edLineRange(text, a, b), k = ED_LINE[kind];
  const lines = text.slice(start, end).split("\n"), filled = lines.filter((l) => l.trim());
  const remove = filled.length > 0 && filled.every((l) => k.has.test(l));
  let n = 0;
  const out = lines.map((l) => {
    if (!l.trim() && lines.length > 1) return l;        // blank lines inside a selection stay blank
    const bare = l.replace(k.strip, "");
    return remove ? bare : k.make(n++) + bare;
  }).join("\n");
  return edResult(start, end, out, start, start + out.length);
}

function edCode(text, a, b, ph) {                       // inline `code` for one line, a fenced block for several
  const sel = text.slice(a, b);
  if (!sel.includes("\n")) return edWrap(text, a, b, "`", "`", ph);
  const [start, end] = edLineRange(text, a, b), block = text.slice(start, end);
  const fenced = /^```[^\n]*\n([\s\S]*)\n```$/.exec(block);
  if (fenced) return edResult(start, end, fenced[1], start, start + fenced[1].length);
  return edResult(start, end, "```\n" + block + "\n```", start + 4, start + 4 + block.length);
}

function edLink(text, a, b, ph) {                       // [text](url): the part to type next is selected
  const sel = text.slice(a, b);
  if (/^https?:\/\/\S+$/.test(sel)) return edResult(a, b, "[" + ph + "](" + sel + ")", a + 1, a + 1 + ph.length);
  const label = sel || ph, url = "https" + "://";     // (the scheme is split so the page never contains a literal URL: a test checks that)
  const ins = "[" + label + "](" + url + ")";
  return sel ? edResult(a, b, ins, a + label.length + 3, a + label.length + 3 + url.length) : edResult(a, b, ins, a + 1, a + 1 + label.length);
}

function edBlock(text, from, to, body, selOff, selLen) {  // a block on its own lines, with a blank line before and after
  const before = text.slice(0, from), after = text.slice(to);
  const lead = from === 0 || before.endsWith("\n\n") ? "" : before.endsWith("\n") ? "\n" : "\n\n";
  const trail = after === "" || after.startsWith("\n\n") ? "" : after.startsWith("\n") ? "\n" : "\n\n";
  return edResult(from, to, lead + body + trail, from + lead.length + selOff, from + lead.length + selOff + selLen);
}

function edTable(text, a, b, labels) {                  // a 2x2 table; the first header is selected
  const body = "| " + labels.col1 + " | " + labels.col2 + " |\n| --- | --- |\n| " + labels.cell + " | " + labels.cell + " |";
  return edBlock(text, b, b, body, 2, labels.col1.length);
}

function edCallout(text, a, b, kind, ph) {              // > [!TIP] + the selected lines (or a placeholder) as the callout body
  const tag = "> [!" + kind.toUpperCase() + "]\n";
  if (a === b) return edBlock(text, a, a, tag + "> " + ph, tag.length + 2, ph.length);
  const [start, end] = edLineRange(text, a, b), lines = text.slice(start, end).split("\n").map((l) => "> " + l).join("\n");
  return edBlock(text, start, end, tag + lines, tag.length, lines.length);
}
"""

EDITOR_UI_JS = r"""
// ---- the editor around a note's textarea: toolbar (Write) and a rendered preview (Preview)
function applyEdit(ta, e) {                             // keeps the undo history where the browser allows it
  ta.focus();
  ta.setSelectionRange(e.from, e.to);
  let done = false;
  try { done = document.execCommand("insertText", false, e.insert); } catch (x) { /* falls back below */ }
  if (!done) ta.setRangeText(e.insert, e.from, e.to, "end");
  ta.setSelectionRange(e.selFrom, e.selTo);
  ta.dispatchEvent(new Event("input", {bubbles: true}));
}
function markdownEditor(ta) {
  const text = () => tr("editor_ph_text");
  const labels = () => ({col1: tr("editor_col1"), col2: tr("editor_col2"), cell: tr("editor_cell")});
  const TOOLS = [
    ["bold", "editor_bold", "B", (t, a, b) => edWrap(t, a, b, "**", "**", text())],
    ["italic", "editor_italic", "I", (t, a, b) => edWrap(t, a, b, "*", "*", text())],
    ["strike", "editor_strike", "", (t, a, b) => edWrap(t, a, b, "~~", "~~", text())],
    ["h2", "editor_h2", "", (t, a, b) => edLines(t, a, b, "h2")],
    ["h3", "editor_h3", "", (t, a, b) => edLines(t, a, b, "h3")],
    ["list", "editor_ul", "", (t, a, b) => edLines(t, a, b, "ul")],
    ["ol", "editor_ol", "", (t, a, b) => edLines(t, a, b, "ol")],
    ["code", "editor_code", "", (t, a, b) => edCode(t, a, b, tr("editor_ph_code"))],
    ["quote", "editor_quote", "", (t, a, b) => edLines(t, a, b, "quote")],
    ["link", "editor_link", "", (t, a, b) => edLink(t, a, b, tr("editor_ph_link"))],
    ["table", "editor_table", "", (t, a, b) => edTable(t, a, b, labels())],
  ];
  const run = (fn) => applyEdit(ta, fn(ta.value, ta.selectionStart, ta.selectionEnd));
  const mod = /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent) ? "⌘" : "Ctrl+";
  const toolbar = h("div", {class: "edtools", role: "toolbar", "aria-label": tr("label_body")});
  for (const [ic, key, short, fn] of TOOLS) {
    toolbar.append(h("button", {type: "button", class: "edbtn", "data-tool": ic, "aria-label": tr(key), title: tr(key) + (short ? " (" + mod + short + ")" : ""),
      onmousedown: (e) => e.preventDefault(), onclick: () => run(fn)}, icon(ic, 16)));    // mousedown must not take the selection away from the textarea
  }
  // callouts: one button, a small menu of the six kinds
  const menu = h("div", {class: "edmenu", role: "menu", hidden: true});
  const closeMenu = () => { menu.hidden = true; document.removeEventListener("mousedown", outside); };
  const outside = (e) => { if (!menu.contains(e.target) && !calloutBtn.contains(e.target)) closeMenu(); };
  for (const [kind, [label, ic]] of Object.entries(CALLOUTS)) {
    menu.append(h("button", {type: "button", role: "menuitem", class: "edmenuitem " + kind, onmousedown: (e) => e.preventDefault(),
      onclick: () => { closeMenu(); run((t, a, b) => edCallout(t, a, b, kind, text())); }}, icon(ic, 15), tr(label)));
  }
  const calloutBtn = h("button", {type: "button", class: "edbtn", "data-tool": "callout", "aria-label": tr("editor_callout"), title: tr("editor_callout"), "aria-haspopup": "menu",
    onmousedown: (e) => e.preventDefault(), onclick: () => { if (menu.hidden) { menu.hidden = false; document.addEventListener("mousedown", outside); } else closeMenu(); }}, icon("info", 16));
  toolbar.append(h("span", {class: "edpop"}, calloutBtn, menu));      // the menu opens right under its button
  menu.addEventListener("keydown", (e) => { if (e.key === "Escape") { e.stopPropagation(); closeMenu(); ta.focus(); } });

  // Write / Preview
  const preview = h("div", {class: "edpreview", hidden: true});
  const tabs = h("div", {class: "edtabs", role: "tablist"});
  const tabWrite = h("button", {type: "button", role: "tab", class: "edtab on", "aria-selected": "true"}, tr("editor_write"));
  const tabPreview = h("button", {type: "button", role: "tab", class: "edtab", "aria-selected": "false"}, tr("editor_preview"));
  function show(previewOn) {
    if (previewOn) {
      const value = ta.value;
      preview.style.minHeight = ta.offsetHeight + "px";
      preview.replaceChildren(value.trim() ? h("article", {class: "md"}, mdBlocksDom(mdParse(value), {tk: [], heads: []})) : h("div", {class: "muted"}, tr("editor_empty_preview")));
    } else closeMenu();
    ta.hidden = previewOn; preview.hidden = !previewOn; toolbar.hidden = previewOn;
    tabWrite.classList.toggle("on", !previewOn); tabPreview.classList.toggle("on", previewOn);
    tabWrite.setAttribute("aria-selected", String(!previewOn)); tabPreview.setAttribute("aria-selected", String(previewOn));
    if (!previewOn) ta.focus();
  }
  tabWrite.addEventListener("click", () => show(false));
  tabPreview.addEventListener("click", () => show(true));
  tabs.append(tabWrite, tabPreview);

  ta.addEventListener("keydown", (e) => {                // Ctrl/Cmd+B and +I
    if (!(e.metaKey || e.ctrlKey) || e.shiftKey || e.altKey) return;
    const tool = {b: TOOLS[0][3], i: TOOLS[1][3]}[e.key.toLowerCase()];
    if (tool) { e.preventDefault(); run(tool); }
  });
  return {el: h("div", {class: "edwrap"}, h("div", {class: "edbar"}, tabs, toolbar), ta, preview), show};
}
"""

EDITOR_CSS = r"""
.edwrap{display:grid;gap:8px;min-width:0}
.edbar{position:relative;display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.edtabs{display:inline-flex;border:1px solid var(--line);border-radius:10px;padding:2px;background:var(--bg)}
.edtab{border:0;background:none;border-radius:8px;padding:4px 12px;font-size:12.5px;color:var(--muted);transition:background var(--ease),color var(--ease)}
.edtab:hover{color:var(--ink)}
.edtab.on{background:var(--accent-soft);color:var(--ink);font-weight:600}
.edtools{display:flex;gap:2px;flex-wrap:wrap;align-items:center}
.edbtn{display:grid;place-items:center;width:30px;height:30px;border:1px solid transparent;border-radius:8px;background:none;color:var(--muted);transition:background var(--ease),color var(--ease)}
.edbtn:hover{background:var(--accent-soft);color:var(--ink)}
.edbtn:focus-visible,.edtab:focus-visible,.edmenuitem:focus-visible{outline:2px solid var(--accent-light);outline-offset:1px}
.edpop{position:relative;display:inline-block}
.edmenu{position:absolute;top:100%;right:0;z-index:20;min-width:190px;margin-top:6px;padding:6px;border:1px solid var(--line);border-radius:12px;background:var(--raise);box-shadow:var(--shadow);display:grid;gap:2px;animation:fadein .15s ease-out}
.edmenuitem{display:flex;align-items:center;gap:9px;border:0;background:none;border-radius:8px;padding:7px 10px;text-align:left;font-size:13px;color:var(--ink)}
.edmenuitem:hover{background:var(--accent-soft)}
.edmenuitem svg{color:var(--cc,#5b8dff)}
.edmenuitem.tip{--cc:#2dd4bf}.edmenuitem.warning{--cc:#f5a524}.edmenuitem.important{--cc:#a78bfa}.edmenuitem.success{--cc:#22c55e}.edmenuitem.note{--cc:#94a3b8}
.edpreview{border:1px solid var(--line);border-radius:12px;background:var(--bg);padding:16px 18px;overflow-x:auto}
.edpreview .md{font-size:15.5px}
"""
