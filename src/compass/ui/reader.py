"""The note reader: a safe Markdown renderer for note bodies, plus its styles.

Notes are stored as plain text and never rewritten. They are *displayed* through a small Markdown
parser (`READER_PURE_JS`, no DOM, unit-tested in `tests/ui/test_reader.py`) and a DOM builder
(`READER_UI_JS`). Nothing here produces HTML strings: every node is created with DOM calls, links
are limited to safe schemes, and raw HTML in a note is shown as text. Single line breaks are kept,
so old plain-text notes look the way they always did.
"""

READER_PURE_JS = r"""
// ---- Markdown: text -> blocks (pure functions, no DOM)
const MD_LIST = /^(\s*)([-*+]|\d{1,9}[.)])\s+(.*)$/;
const MD_HR = /^\s{0,3}(?:(?:\*\s*){3,}|(?:-\s*){3,}|(?:_\s*){3,})$/;
const MD_HEAD = /^\s{0,3}(#{1,6})\s+(.*?)(?:\s+#+)?\s*$/;
const MD_FENCE = /^\s{0,3}(```+|~~~+)\s*([^\s`]*)[^`]*$/;
const MD_QUOTE = /^\s{0,3}>\s?(.*)$/;
const MD_SEP = /^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$/;
const MD_CALLOUT = /^\[!(note|info|tip|warning|caution|important|success)\]\s*(.*)$/i;
const mdIndent = (s) => s.length - s.trimStart().length;

function mdCells(line) {
  let s = line.trim();
  if (s.startsWith("|")) s = s.slice(1);
  if (s.endsWith("|") && !s.endsWith("\\|")) s = s.slice(0, -1);
  return s.split(/(?<!\\)\|/).map((c) => c.trim().replace(/\\\|/g, "|"));
}
function mdTableAt(lines, i) {
  if (i + 1 >= lines.length || !lines[i].includes("|") || !MD_SEP.test(lines[i + 1]) || !lines[i + 1].includes("-")) return false;
  return mdCells(lines[i]).length === mdCells(lines[i + 1]).length;
}
function mdStartsBlock(lines, i) {
  const l = lines[i];
  if (MD_FENCE.test(l) || MD_HR.test(l) || MD_HEAD.test(l) || MD_QUOTE.test(l) || mdTableAt(lines, i)) return true;
  const m = MD_LIST.exec(l);
  return !!m && (!/\d/.test(m[2]) || parseInt(m[2], 10) === 1);   // only "1." may interrupt a paragraph
}

function mdList(lines, i) {
  const first = MD_LIST.exec(lines[i]), base = mdIndent(first[1]), ordered = /\d/.test(first[2]);
  const block = {t: ordered ? "ol" : "ul", start: ordered ? parseInt(first[2], 10) : 1, items: []};
  const n = lines.length;
  while (i < n) {
    const m = MD_LIST.exec(lines[i]);
    if (!m || mdIndent(m[1]) < base || mdIndent(m[1]) > base + 1 || /\d/.test(m[2]) !== ordered) break;
    const body = [m[3]];
    i++;
    let sameList = false;
    while (i < n) {
      const l = lines[i];
      if (!l.trim()) {
        let j = i;
        while (j < n && !lines[j].trim()) j++;
        if (j >= n) { i = j; break; }
        const nm = MD_LIST.exec(lines[j]);
        if (mdIndent(lines[j]) > base + 1) { body.push(""); i++; continue; }          // still inside this item
        if (nm && mdIndent(nm[1]) >= base && /\d/.test(nm[2]) === ordered) { i = j; sameList = true; }   // loose list
        break;
      }
      if (mdIndent(l) > base + 1) { body.push(l.slice(Math.min(mdIndent(l), base + 2))); i++; continue; }
      if (MD_LIST.test(l) || mdStartsBlock(lines, i)) break;
      body.push(l.trim());                                                           // lazy continuation
      i++;
    }
    block.items.push({c: mdBlocks(body)});
    if (!sameList && (i >= n || !MD_LIST.test(lines[i]))) break;
  }
  return {block, next: i};
}

function mdBlocks(lines) {
  const out = [], n = lines.length;
  let i = 0;
  while (i < n) {
    const line = lines[i];
    if (!line.trim()) { i++; continue; }
    let m;
    if ((m = MD_FENCE.exec(line))) {
      const fence = m[1], code = [];
      i++;
      while (i < n && !(new RegExp("^\\s{0,3}" + fence[0] + "{" + fence.length + ",}\\s*$").test(lines[i]))) { code.push(lines[i]); i++; }
      if (i < n) i++;                                   // the closing fence (an unclosed one runs to the end)
      out.push({t: "code", lang: m[2].toLowerCase(), text: code.join("\n")});
    } else if (MD_HR.test(line)) {
      out.push({t: "hr"}); i++;
    } else if ((m = MD_HEAD.exec(line))) {
      out.push({t: "h", level: m[1].length, c: mdInline(m[2])}); i++;
    } else if (MD_QUOTE.test(line)) {
      const inner = [];
      while (i < n && MD_QUOTE.test(lines[i])) { inner.push(MD_QUOTE.exec(lines[i])[1]); i++; }
      const co = MD_CALLOUT.exec(inner[0].trim());
      if (co) {
        const rest = co[2] ? [co[2], ...inner.slice(1)] : inner.slice(1);
        const kind = co[1].toLowerCase();
        out.push({t: "callout", kind: kind === "caution" ? "warning" : kind, c: mdBlocks(rest)});
      } else out.push({t: "quote", c: mdBlocks(inner)});
    } else if (mdTableAt(lines, i)) {
      const head = mdCells(lines[i]).map(mdInline);
      const align = mdCells(lines[i + 1]).map((c) => (c.startsWith(":") && c.endsWith(":") ? "center" : c.endsWith(":") ? "right" : c.startsWith(":") ? "left" : ""));
      i += 2;
      const rows = [];
      while (i < n && lines[i].trim() && lines[i].includes("|") && !mdStartsBlock(lines, i)) {
        const cells = mdCells(lines[i]);
        rows.push(head.map((_, k) => mdInline(cells[k] || "")));
        i++;
      }
      out.push({t: "table", head, align, rows});
    } else if (MD_LIST.test(line)) {
      const r = mdList(lines, i);
      out.push(r.block); i = r.next;
    } else {
      const para = [line.trim()];
      i++;
      while (i < n && lines[i].trim() && !mdStartsBlock(lines, i)) { para.push(lines[i].trim()); i++; }
      out.push({t: "p", c: mdInline(para.join("\n"))});
    }
  }
  return out;
}
const mdParse = (text) => mdBlocks(text.replace(/\r\n?/g, "\n").replace(/\t/g, "    ").split("\n"));

// ---- Markdown: inline text -> nodes
const mdSafeUrl = (u) => /^(https?:\/\/|mailto:|\/|#)/i.test(u);
function mdClose(s, from, d, single) {          // index of a closing delimiter, or -1
  for (let j = s.indexOf(d, from); j !== -1; j = s.indexOf(d, j + 1)) {
    if (/\s/.test(s[j - 1] || " ")) continue;
    if (single && (s[j - 1] === d || s[j + 1] === d)) continue;
    if (d[0] === "_" && /[\p{L}\p{N}]/u.test(s[j + d.length] || " ")) continue;
    return j;
  }
  return -1;
}
function mdInline(s) {
  const out = [];
  let buf = "", i = 0;
  const flush = () => { if (buf) { out.push({t: "text", v: buf}); buf = ""; } };
  while (i < s.length) {
    const c = s[i];
    if (c === "\\" && i + 1 < s.length && /[\\`*_{}\[\]()#+\-.!|~>]/.test(s[i + 1])) { buf += s[i + 1]; i += 2; continue; }
    if (c === "\n") { flush(); out.push({t: "br"}); i++; continue; }
    if (c === "`") {
      let k = i; while (s[k] === "`") k++;
      const run = s.slice(i, k), end = s.indexOf(run, k);
      if (end !== -1) { flush(); let v = s.slice(k, end); if (v.length > 2 && v.startsWith(" ") && v.endsWith(" ")) v = v.slice(1, -1); out.push({t: "code", v}); i = end + run.length; continue; }
      buf += run; i = k; continue;
    }
    if (c === "[") {
      const close = s.indexOf("](", i);
      if (close !== -1) {
        const end = s.indexOf(")", close + 2);
        const url = end === -1 ? "" : s.slice(close + 2, end).trim().split(/\s+/)[0];
        if (end !== -1 && mdSafeUrl(url) && close > i + 1) { flush(); out.push({t: "link", href: url, c: mdInline(s.slice(i + 1, close))}); i = end + 1; continue; }
      }
    }
    if (c === "~" && s[i + 1] === "~" && s[i + 2] && !/\s/.test(s[i + 2])) {
      const end = mdClose(s, i + 2, "~~", false);
      if (end !== -1) { flush(); out.push({t: "del", c: mdInline(s.slice(i + 2, end))}); i = end + 2; continue; }
    }
    if ((c === "*" || c === "_") && s[i + 1] === c && s[i + 2] && !/\s/.test(s[i + 2]) && (c === "*" || !/[\p{L}\p{N}]/u.test(s[i - 1] || " "))) {
      const end = mdClose(s, i + 2, c + c, false);
      if (end !== -1) { flush(); out.push({t: "strong", c: mdInline(s.slice(i + 2, end))}); i = end + 2; continue; }
    }
    if ((c === "*" || c === "_") && s[i + 1] && !/\s/.test(s[i + 1]) && s[i + 1] !== c && (c === "*" || !/[\p{L}\p{N}]/u.test(s[i - 1] || " "))) {
      const end = mdClose(s, i + 1, c, true);
      if (end !== -1) { flush(); out.push({t: "em", c: mdInline(s.slice(i + 1, end))}); i = end + 1; continue; }
    }
    if ((c === "h") && /^https?:\/\//.test(s.slice(i, i + 8)) && !/[\p{L}\p{N}]/u.test(s[i - 1] || " ")) {
      const m = /^https?:\/\/[^\s<>]+/.exec(s.slice(i));
      const url = m[0].replace(/[.,;:!?'")\]]+$/, "");
      flush(); out.push({t: "link", href: url, c: [{t: "text", v: url}]}); i += url.length; continue;
    }
    buf += c; i++;
  }
  flush();
  return out;
}
const mdPlain = (nodes) => nodes.map((n) => (n.t === "text" || n.t === "code" ? n.v : n.t === "br" ? " " : n.c ? mdPlain(n.c) : "")).join("");

// ---- syntax highlighting: code -> [[class, text], ...] (small, dependency free)
const HL_WORDS = (s) => new RegExp("^(?:" + s.split(" ").join("|") + ")\\b");
const HL_LANGS = {
  js: {kw: "const let var function return if else for while do switch case break continue new class extends import export from default async await try catch finally throw typeof instanceof in of delete yield static this super", lit: "true false null undefined NaN Infinity", com: ["//[^\n]*", "/\\*[\\s\\S]*?(?:\\*/|$)"], str: ["`(?:\\\\[\\s\\S]|[^`\\\\])*`?", "\"(?:\\\\.|[^\"\\\\\n])*\"?", "'(?:\\\\.|[^'\\\\\n])*'?"]},
  python: {kw: "def class return if elif else for while in not and or is import from as with try except finally raise lambda yield pass break continue global nonlocal async await del assert self", lit: "True False None", com: ["#[^\n]*"], str: ["\"\"\"[\\s\\S]*?(?:\"\"\"|$)", "'''[\\s\\S]*?(?:'''|$)", "\"(?:\\\\.|[^\"\\\\\n])*\"?", "'(?:\\\\.|[^'\\\\\n])*'?"]},
  sql: {kw: "select from where group by order having insert into values update set delete create table alter drop index join inner left right outer full cross on as and or not in is like between limit offset union all distinct case when then else end primary key foreign references default null unique with begin commit rollback explain count sum avg min max", lit: "", ci: true, com: ["--[^\n]*", "/\\*[\\s\\S]*?(?:\\*/|$)"], str: ["'(?:''|[^'])*'?", "\"[^\"\n]*\"?"]},
  json: {kw: "", lit: "true false null", com: [], str: ["\"(?:\\\\.|[^\"\\\\\n])*\"?"]},
  bash: {kw: "if then else elif fi for while do done case esac function in echo cd ls cat grep sed awk export source sudo docker git npm pip uv make curl mkdir rm cp mv", lit: "", com: ["#[^\n]*"], str: ["\"(?:\\\\.|[^\"\\\\])*\"?", "'[^']*'?"], extra: [["tk-lit", "\\$\\{?[A-Za-z_][\\w]*\\}?"]]},
  yaml: {kw: "", lit: "true false null yes no", com: ["#[^\n]*"], str: ["\"(?:\\\\.|[^\"\\\\\n])*\"?", "'[^'\n]*'?"], extra: [["tk-fn", "[\\w.-]+(?=\\s*:(?:\\s|$))"]]},
  css: {kw: "", lit: "", com: ["/\\*[\\s\\S]*?(?:\\*/|$)"], str: ["\"[^\"\n]*\"?", "'[^'\n]*'?"], extra: [["tk-kw", "@[\\w-]+"], ["tk-fn", "[\\w-]+(?=\\s*:)"], ["tk-num", "#[0-9a-fA-F]{3,8}\\b"]]},
  html: {kw: "", lit: "", com: ["<!--[\\s\\S]*?(?:-->|$)"], str: ["\"[^\"\n]*\"?", "'[^'\n]*'?"], extra: [["tk-tag", "</?[A-Za-z][\\w:-]*"], ["tk-tag", "/?>"], ["tk-attr", "[\\w:-]+(?==)"]]},
};
const HL_ALIAS = {javascript: "js", jsx: "js", ts: "js", tsx: "js", typescript: "js", node: "js", py: "python", python3: "python", sh: "bash", shell: "bash", zsh: "bash", console: "bash",
  yml: "yaml", xml: "html", svg: "html", scss: "css", postgres: "sql", postgresql: "sql", sqlite: "sql", mysql: "sql", json5: "json"};
const HL_LABELS = {js: "JavaScript", python: "Python", sql: "SQL", json: "JSON", bash: "Bash", yaml: "YAML", css: "CSS", html: "HTML"};
const hlLang = (name) => { const n = (name || "").toLowerCase(); return HL_LANGS[HL_ALIAS[n] || n] ? (HL_ALIAS[n] || n) : ""; };
function hlDetect(code) {                        // guess a language when the fence names none
  const t = code.trim();
  if ((t.startsWith("{") || t.startsWith("[")) && t.length < 20000) { try { JSON.parse(t); return "json"; } catch (e) { /* not json */ } }
  if (/^<[!A-Za-z][^>]*>/.test(t) && /<\/[A-Za-z]/.test(t)) return "html";
  if (/^\s*(select|insert\s+into|update|delete\s+from|create\s+table|with)\b[\s\S]*\b(from|into|set|values|table|as)\b/i.test(t)) return "sql";
  if (/^#!.*\b(ba|z)?sh\b/.test(t) || /^\s*\$\s+\S/m.test(t) || /^\s*(sudo|docker|git|npm|pip|uv|curl|cd|ls|mkdir|export)\s+\S/m.test(t)) return "bash";
  if (/^\s*(def|class)\s+\w+.*:\s*$/m.test(t) || /^\s*(import|from)\s+\w+.*$/m.test(t) && /:\s*$/m.test(t) || /\bprint\(/.test(t) && !/;\s*$/m.test(t)) return "python";
  if (/\b(const|let|var|function)\s+[\w$]+|=>|console\.log|\bimport\s.+\sfrom\s/.test(t)) return "js";
  if (/^[\w.-]+:\s*(\S.*)?$/m.test(t) && !/[;{}]/.test(t) && t.split("\n").length > 1) return "yaml";
  if (/[.#]?[\w-]+\s*\{[^}]*:[^}]*\}/.test(t)) return "css";
  return "";
}
const HL_CACHE = {};
function hlRules(lang) {
  if (HL_CACHE[lang]) return HL_CACHE[lang];
  const d = HL_LANGS[lang], rules = [];
  for (const re of d.com) rules.push(["tk-com", new RegExp(re, "y")]);
  for (const re of d.str) rules.push(["tk-str", new RegExp(re, "y")]);
  for (const [cls, re] of d.extra || []) rules.push([cls, new RegExp(re, "y")]);
  rules.push(["tk-num", /(?:0x[0-9a-fA-F]+|\d+(?:\.\d+)?(?:e[+-]?\d+)?)\b/y]);
  if (d.lit) rules.push(["tk-lit", new RegExp("(?:" + d.lit.split(" ").join("|") + ")\\b", "y")]);
  if (d.kw) rules.push(["tk-kw", new RegExp("(?:" + d.kw.split(" ").join("|") + ")\\b", d.ci ? "iy" : "y")]);
  rules.push(["tk-fn", /[A-Za-z_$][\w$]*(?=\()/y]);
  return (HL_CACHE[lang] = rules);
}
function mdHighlight(code, lang) {
  if (!lang || code.length > 30000) return [["", code]];
  const rules = hlRules(lang), out = [];
  let plain = "", i = 0;
  const wordStart = (p) => p === 0 || !/[\w$]/.test(code[p - 1]);
  while (i < code.length) {
    let hit = null;
    for (const [cls, re] of rules) {
      if ((cls === "tk-kw" || cls === "tk-lit" || cls === "tk-num" || cls === "tk-fn") && !wordStart(i)) continue;
      re.lastIndex = i;
      const m = re.exec(code);
      if (m && m[0]) { hit = [cls, m[0]]; break; }
    }
    if (hit) { if (plain) { out.push(["", plain]); plain = ""; } out.push(hit); i += hit[1].length; }
    else { plain += code[i]; i++; }
  }
  if (plain) out.push(["", plain]);
  return out;
}
"""

READER_UI_JS = r"""
// ---- the reader: Markdown blocks -> DOM (DOM calls only, never HTML strings)
const CALLOUTS = {
  info: ["callout_info", "info"], tip: ["callout_tip", "bulb"], warning: ["callout_warning", "alert"],
  important: ["callout_important", "alert-circle"], success: ["callout_success", "check-circle"], note: ["callout_note", "file"],
};
function mdInlineDom(nodes, tk) {
  return nodes.map((n) => {
    if (n.t === "text") return hlNodes(n.v, tk);
    if (n.t === "br") return h("br");
    if (n.t === "code") return h("code", {class: "icode"}, n.v);
    if (n.t === "strong") return h("strong", {}, mdInlineDom(n.c, tk));
    if (n.t === "em") return h("em", {}, mdInlineDom(n.c, tk));
    if (n.t === "del") return h("del", {}, mdInlineDom(n.c, tk));
    if (n.t === "link") return h("a", n.href.startsWith("#") || n.href.startsWith("/") ? {href: n.href} : {href: n.href, target: "_blank", rel: "noopener noreferrer"}, mdInlineDom(n.c, tk));
    return null;
  }).flat();
}
function copyCode(btn, text) {
  navigator.clipboard.writeText(text).then(() => {
    const label = btn.querySelector(".lbl"), old = label.textContent;
    label.textContent = tr("code_copied"); btn.classList.add("done");
    setTimeout(() => { label.textContent = old; btn.classList.remove("done"); }, 1500);
  }, () => toast(tr("copy_failed"), "bad"));
}
function codeBlockDom(b) {
  const lang = hlLang(b.lang) || (b.lang ? "" : hlDetect(b.text));
  const code = h("code", {});
  for (const [cls, text] of mdHighlight(b.text, lang)) code.append(cls ? h("span", {class: cls}, text) : text);
  const copy = h("button", {type: "button", class: "copybtn", "aria-label": tr("code_copy"), onclick: () => copyCode(copy, b.text)}, icon("copy", 14), h("span", {class: "lbl"}, tr("copy")));
  return h("div", {class: "codeblock"}, h("div", {class: "codehead"}, h("span", {class: "codelang"}, HL_LABELS[lang] || b.lang || tr("code_plain")), copy), h("pre", {tabindex: 0}, code));
}
function mdBlocksDom(blocks, ctx) {
  return blocks.map((b) => {
    const inl = (c) => mdInlineDom(c, ctx.tk);
    if (b.t === "p") return h("p", {}, inl(b.c));
    if (b.t === "h") {
      const id = "sec-" + ctx.heads.length + "-" + (fold(mdPlain(b.c)).replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 40) || "x");
      ctx.heads.push({id, level: b.level, text: mdPlain(b.c)});
      return h("h" + b.level, {id}, inl(b.c));
    }
    if (b.t === "code") return codeBlockDom(b);
    if (b.t === "hr") return h("hr");
    if (b.t === "quote") return h("blockquote", {}, mdBlocksDom(b.c, ctx));
    if (b.t === "callout") {
      const [label, ic] = CALLOUTS[b.kind];
      return h("div", {class: "callout " + b.kind, role: "note"}, h("div", {class: "calltitle"}, icon(ic, 16), h("span", {}, ctx.lang && I18N.callouts[ctx.lang] ? I18N.callouts[ctx.lang][label] : tr(label))), h("div", {class: "callbody"}, mdBlocksDom(b.c, ctx)));
    }
    if (b.t === "ul" || b.t === "ol") {
      const list = h(b.t, b.t === "ol" && b.start !== 1 ? {start: b.start} : {});
      for (const it of b.items) list.append(h("li", {}, mdBlocksDom(it.c, ctx)));
      return list;
    }
    if (b.t === "table") {
      const cell = (tag, c, k) => h(tag, b.align[k] ? {style: "text-align:" + b.align[k]} : {}, inl(c));
      return h("div", {class: "tablewrap"}, h("table", {}, h("thead", {}, h("tr", {}, b.head.map((c, k) => cell("th", c, k)))),
        h("tbody", {}, b.rows.map((r) => h("tr", {}, r.map((c, k) => cell("td", c, k)))))));
    }
    return null;
  });
}

// Reading settings (they come from the server settings) and the reading mode itself
const READER = {size: SETTINGS.reader_size, width: SETTINGS.reader_width};
let readerSave = 0;
function applyReader(save = true) {
  const app = $("#app");
  app.style.setProperty("--read-size", READER.size + "px");
  app.style.setProperty("--read-w", READ_WIDTHS[READER.width] + "px");
  if (!save) return;
  clearTimeout(readerSave);                       // several clicks on A+ become one request
  readerSave = setTimeout(() => saveSettings({reader_size: READER.size, reader_width: READER.width}), 400);
}
let tocWatch = null;
function watchToc(root) {                         // highlight the section being read; cheap, one rAF per scroll burst
  if (tocWatch) tocWatch();
  tocWatch = null;
  const links = [...root.querySelectorAll(".toc a")], scroller = $("#detail");
  if (!links.length) return;
  const heads = links.map((a) => root.querySelector("#" + a.dataset.id));
  let queued = false;
  const update = () => {
    queued = false;
    const top = scroller.getBoundingClientRect().top + 96;
    let cur = 0;
    heads.forEach((el, i) => { if (el && el.getBoundingClientRect().top <= top) cur = i; });
    links.forEach((a, i) => a.classList.toggle("on", i === cur));
  };
  const onScroll = () => { if (!queued) { queued = true; requestAnimationFrame(update); } };
  scroller.addEventListener("scroll", onScroll, {passive: true});
  tocWatch = () => scroller.removeEventListener("scroll", onScroll);
  update();
}
function readerBody(note, tk, lang) {             // the rendered note: optional contents + the article; lang names callouts in a translation
  const ctx = {tk, heads: [], lang};
  const article = h("article", {class: "md"}, mdBlocksDom(mdParse(note.body), ctx));
  const tocHeads = ctx.heads.filter((x) => x.level === 2 || x.level === 3);
  const wrap = h("div", {class: "mdwrap"});
  if (tocHeads.length >= 3) {                      // short notes get no contents
    const nav = h("nav", {"aria-label": tr("toc_title")}, tocHeads.map((x) => h("a", {href: "#" + x.id, "data-id": x.id, class: "l" + x.level, onclick: (e) => {
      e.preventDefault();
      document.getElementById(x.id).scrollIntoView({behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start"});
    }}, x.text)));
    wrap.append(h("details", {class: "toc"}, h("summary", {}, icon("list", 15), tr("toc_title")), nav));
  }
  wrap.append(article);
  return wrap;
}
function syncReadButton() {                      // the book icon in the note header is a toggle: lit while reading
  document.querySelectorAll(".readtoggle").forEach((b) => {
    b.classList.toggle("on", state.reading);
    b.setAttribute("aria-pressed", state.reading ? "true" : "false");
    b.title = tr(state.reading ? "reading_exit" : "reading_mode");
  });
}
const toggleReading = () => (state.reading ? exitReading() : enterReading());
function enterReading() {
  state.reading = true; setView("detail"); openMenu(false);
  $("#app").classList.add("reading");
  syncReadButton();
  document.querySelectorAll(".toc").forEach((d) => { d.open = true; });
  $("#detail").scrollTo({top: 0});
}
function exitReading() {
  if (!state.reading) return;
  state.reading = false;
  $("#app").classList.remove("reading");
  syncReadButton();
  document.querySelectorAll(".toc").forEach((d) => { d.open = false; });
}
"""

READER_CSS = r"""
:root{--r-ink:#e7e9f2;--r-head:#f5f6fc;--r-aux:#a3a8bb;--r-link:#829bff;--r-code:#0d0f1e;--r-sel:rgba(121,92,255,.45)}
:root[data-theme=light]{--r-ink:#262a3f;--r-head:#12142a;--r-aux:#5b5f75;--r-link:#3b5bdb;--r-code:#f3f4fa;--r-sel:rgba(82,117,255,.28)}
.mdwrap{padding:26px 26px 30px;min-width:0}
.md{font-size:var(--read-size,16.5px);line-height:1.8;color:var(--r-ink);overflow-wrap:anywhere;min-width:0}
.md>*:first-child{margin-top:0}
.md>*:last-child{margin-bottom:0}
.md ::selection,.md::selection{background:var(--r-sel);color:inherit}
.md p{margin:0 0 1.05em}
.md h1,.md h2,.md h3,.md h4,.md h5,.md h6{color:var(--r-head);line-height:1.3;margin:1.7em 0 .55em;scroll-margin-top:16px;letter-spacing:-.01em}
.md h1{font-size:1.9em;font-weight:700}
.md h2{font-size:1.45em;font-weight:650;padding-bottom:.3em;border-bottom:1px solid var(--line)}
.md h3{font-size:1.15em;font-weight:600}
.md h4{font-size:1em;font-weight:600}
.md h5,.md h6{font-size:.88em;font-weight:600;color:var(--r-aux);text-transform:uppercase;letter-spacing:.06em}
.md strong{color:var(--r-head);font-weight:650}
.md del{color:var(--r-aux)}
.md a{color:var(--r-link);text-decoration:underline;text-decoration-color:color-mix(in srgb,var(--r-link) 45%,transparent);text-underline-offset:3px;transition:text-decoration-color .15s ease-out}
.md a:hover{text-decoration-color:var(--r-link)}
.md ul,.md ol{margin:0 0 1.05em;padding-left:1.5em}
.md li{margin:.28em 0;font-size:.97em}
.md li>p{margin:.3em 0}
.md li>ul,.md li>ol{margin:.3em 0 .3em}
.md li::marker{color:var(--accent-light)}
.md hr{border:0;height:1px;background:var(--line);margin:2em 0}
.md blockquote{margin:0 0 1.05em;padding:.35em 1.1em;border-left:3px solid color-mix(in srgb,var(--accent) 70%,transparent);background:color-mix(in srgb,var(--ink) 4%,transparent);border-radius:0 12px 12px 0;color:var(--r-aux)}
.md blockquote p:last-child{margin-bottom:0}
.md .icode{font-family:ui-monospace,"JetBrains Mono",SFMono-Regular,Menlo,monospace;font-size:.86em;padding:.12em .42em;border-radius:6px;background:var(--r-code);border:1px solid var(--line);color:var(--r-head)}
.codeblock{margin:0 0 1.2em;border:1px solid var(--line);border-radius:14px;background:var(--r-code);overflow:hidden}
.codehead{display:flex;justify-content:space-between;align-items:center;padding:7px 8px 7px 14px;border-bottom:1px solid var(--line);font-size:12px;color:var(--r-aux)}
.codelang{text-transform:uppercase;letter-spacing:.07em;font-weight:600;font-size:11px}
.copybtn{display:inline-flex;align-items:center;gap:6px;border:1px solid transparent;background:none;border-radius:8px;padding:3px 9px;font-size:12px;color:var(--r-aux);transition:background .15s ease-out,color .15s ease-out}
.copybtn:hover{background:color-mix(in srgb,var(--ink) 8%,transparent);color:var(--r-head)}
.copybtn.done{color:var(--ok)}
.codeblock pre{margin:0;padding:14px 16px;overflow-x:auto;font-family:ui-monospace,"JetBrains Mono",SFMono-Regular,Menlo,monospace;font-size:14px;line-height:1.65;tab-size:4;color:var(--r-ink);scrollbar-width:thin}
.codeblock code{font:inherit;white-space:pre}
.tk-kw{color:#b69cff}.tk-str{color:#7fe0a6}.tk-num{color:#ffb86b}.tk-com{color:#6f7590;font-style:italic}.tk-fn{color:#7aa2ff}.tk-lit{color:#5fd8e0}.tk-tag{color:#7aa2ff}.tk-attr{color:#e2b8ff}
:root[data-theme=light] .tk-kw{color:#6d4bd6}:root[data-theme=light] .tk-str{color:#15803d}:root[data-theme=light] .tk-num{color:#b45309}:root[data-theme=light] .tk-com{color:#7b8099}:root[data-theme=light] .tk-fn{color:#2f55d4}:root[data-theme=light] .tk-lit{color:#0e7490}:root[data-theme=light] .tk-tag{color:#2f55d4}:root[data-theme=light] .tk-attr{color:#9333ea}
.tablewrap{margin:0 0 1.2em;max-width:100%;overflow-x:auto;border:1px solid var(--line);border-radius:14px;background:color-mix(in srgb,var(--r-code) 70%,transparent);scrollbar-width:thin}
.md table{border-collapse:collapse;width:100%;font-size:.93em;line-height:1.55}
.md th{background:color-mix(in srgb,var(--ink) 7%,transparent);color:var(--r-head);font-weight:600;text-align:left;white-space:nowrap}
.md th,.md td{padding:10px 14px;border-bottom:1px solid var(--line);vertical-align:top}
.md tbody tr:last-child td{border-bottom:0}
.md tbody tr{transition:background .12s ease-out}
.md tbody tr:hover{background:color-mix(in srgb,var(--accent) 8%,transparent)}
.callout{--cc:#5b8dff;margin:0 0 1.15em;padding:12px 16px 12px;border-radius:14px;border:1px solid color-mix(in srgb,var(--cc) 32%,transparent);background:color-mix(in srgb,var(--cc) 9%,transparent)}
.callout.tip{--cc:#2dd4bf}.callout.warning{--cc:#f5a524}.callout.important{--cc:#a78bfa}.callout.success{--cc:#22c55e}.callout.note{--cc:#94a3b8}
.calltitle{display:flex;align-items:center;gap:8px;font-size:.82em;font-weight:650;text-transform:uppercase;letter-spacing:.06em;color:var(--cc);margin-bottom:4px}
.callbody{font-size:.97em}
.callbody>*:last-child{margin-bottom:0}
.toc{margin:0 0 1.6em;border:1px solid var(--line);border-radius:14px;background:color-mix(in srgb,var(--ink) 3%,transparent);font-size:14px}
.toc summary{display:flex;align-items:center;gap:8px;cursor:pointer;padding:10px 14px;color:var(--r-aux);font-weight:600;list-style:none;user-select:none}
.toc summary::-webkit-details-marker{display:none}
.toc summary:hover{color:var(--r-head)}
.toc nav{display:grid;gap:1px;padding:0 8px 10px}
.toc a{display:block;padding:4px 8px;border-radius:8px;color:var(--r-aux);text-decoration:none;border-left:2px solid transparent;transition:color .15s ease-out,background .15s ease-out}
.toc a.l3{padding-left:22px;font-size:13px}
.toc a:hover{color:var(--r-head);background:color-mix(in srgb,var(--ink) 5%,transparent)}
.toc a.on{color:var(--accent-light);border-left-color:var(--accent-light);background:var(--accent-soft)}
.hint2{font-size:12px;color:var(--faint);line-height:1.5}
.readbar{display:none;align-items:center;justify-content:space-between;gap:12px;padding:0 0 12px}
.readbar .rtools{display:flex;gap:8px;align-items:center}
.readbar .btn{padding:6px 11px}
.readbar .lbl{color:var(--muted);font-size:13px;font-weight:600;display:flex;gap:8px;align-items:center}
.app.reading .readbar{display:flex;animation:fadein .22s ease-out}
.hero .iconbtn.on{background:var(--grad);border-color:transparent;box-shadow:0 4px 14px rgba(82,117,255,.35)}
.app,.grid,aside{transition:grid-template-columns .22s ease-out}
.topbar,.filters{transition:opacity .18s ease-out,max-height .22s ease-out,margin .22s ease-out;max-height:120px}
.app.reading{grid-template-columns:0 minmax(0,1fr)}
.app.reading aside{padding:0;border-width:0;opacity:0;pointer-events:none;overflow:hidden}
.app.reading .topbar,.app.reading .filters{opacity:0;max-height:0;margin-top:0;margin-bottom:0;overflow:hidden;pointer-events:none}
.app.reading .grid{grid-template-columns:0 minmax(0,1fr);gap:0}
.app.reading .listcol{opacity:0;overflow:hidden;padding:0;pointer-events:none}
.app.reading .detailcol{padding:2px 8px 40px}
.app.reading .card{max-width:calc(var(--read-w,760px) + 56px);margin:0 auto}
.app.reading .mdwrap{max-width:calc(var(--read-w,760px) + 56px);margin:0 auto}
.app.reading .toc{position:relative}
@media (min-width:1180px){
  .app.reading .card:has(.toc){max-width:calc(var(--read-w,760px) + 56px + 250px)}
  .app.reading .mdwrap:has(.toc){display:grid;grid-template-columns:minmax(0,1fr) 220px;column-gap:34px;max-width:none}
  .app.reading .mdwrap .md{grid-column:1;grid-row:1;max-width:var(--read-w,760px)}
  .app.reading .mdwrap .toc{grid-column:2;grid-row:1;position:sticky;top:16px;align-self:start;margin:0;max-height:calc(100vh - 140px);overflow:auto;background:none;border-color:transparent}
  .app.reading .toc summary{pointer-events:none;padding-left:8px}
}
@media (max-width:900px){
  .mdwrap{padding:20px 18px 26px}
  .app.reading,.app.reading .grid{grid-template-columns:1fr}
  .app.reading main{padding:10px 12px 0}
  .app.reading .detailcol{padding:2px 0 40px}
  .readbar .lbl span:not(.ic){display:none}
  .readbar .btn{padding:6px 10px}
}
"""
