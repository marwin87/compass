/*I18N*/
const LANG = I18N.lang,
  T = I18N.strings;
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
// --- icons (Lucide-style line icons, drawn with DOM calls; no external requests)
const SVGNS = "http://www.w3.org/2000/svg";
const ICONS = {
  compass: [
    ["circle", { cx: 12, cy: 12, r: 10 }],
    ["polygon", { points: "16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76" }],
  ],
  "align-left": [
    ["path", { d: "M21 6H3" }],
    ["path", { d: "M15 12H3" }],
    ["path", { d: "M17 18H3" }],
  ],
  "chat-compass": [
    ["path", { d: "M7.9 20A9 9 0 1 0 4 16.1L2 22Z" }],
    [
      "polygon",
      {
        points: "16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76",
        transform: "translate(12 11.2) scale(.62) translate(-12 -12)",
      },
    ],
  ],
  plus: [
    ["path", { d: "M5 12h14" }],
    ["path", { d: "M12 5v14" }],
  ],
  bold: [
    ["path", { d: "M14 12a4 4 0 0 0 0-8H6v8" }],
    ["path", { d: "M15 20a4 4 0 0 0 0-8H6v8Z" }],
  ],
  italic: [
    ["line", { x1: 19, y1: 4, x2: 10, y2: 4 }],
    ["line", { x1: 14, y1: 20, x2: 5, y2: 20 }],
    ["line", { x1: 15, y1: 4, x2: 9, y2: 20 }],
  ],
  strike: [
    ["path", { d: "M16 4H9a3 3 0 0 0-2.83 4" }],
    ["path", { d: "M14 12a4 4 0 0 1 0 8H6" }],
    ["path", { d: "M4 12h16" }],
  ],
  h2: [
    ["path", { d: "M4 12h8" }],
    ["path", { d: "M4 18V6" }],
    ["path", { d: "M12 18V6" }],
    ["path", { d: "M21 18h-4c0-4 4-3 4-6 0-1.5-2-2.5-4-1" }],
  ],
  h3: [
    ["path", { d: "M4 12h8" }],
    ["path", { d: "M4 18V6" }],
    ["path", { d: "M12 18V6" }],
    ["path", { d: "M17.5 10.5c1.7-1 3.5 0 3.5 1.5a2 2 0 0 1-2 2" }],
    ["path", { d: "M17 17.5c2 1.5 4 .3 4-1.5a2 2 0 0 0-2-2" }],
  ],
  ol: [
    ["path", { d: "M10 6h11" }],
    ["path", { d: "M10 12h11" }],
    ["path", { d: "M10 18h11" }],
    ["path", { d: "M4 6h1v4" }],
    ["path", { d: "M4 10h2" }],
    ["path", { d: "M6 18H4c0-1 2-2 2-3s-1-1.5-2-1" }],
  ],
  quote: [
    [
      "path",
      {
        d: "M3 21c3 0 7-1 7-8V5c0-1.25-.756-2.017-2-2H4c-1.25 0-2 .75-2 1.972V11c0 1.25.75 2 2 2 1 0 1 0 1 1v1c0 1-1 2-2 2s-1 .5-1 1z",
      },
    ],
    [
      "path",
      {
        d: "M15 21c3 0 7-1 7-8V5c0-1.25-.757-2.017-2-2h-4c-1.25 0-2 .75-2 1.972V11c0 1.25.75 2 2 2h.75c0 2.25.25 4-2.75 4v3z",
      },
    ],
  ],
  link: [
    ["path", { d: "M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" }],
    ["path", { d: "M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" }],
  ],
  table: [
    ["path", { d: "M12 3v18" }],
    ["rect", { width: 18, height: 18, x: 3, y: 3, rx: 2 }],
    ["path", { d: "M3 9h18" }],
    ["path", { d: "M3 15h18" }],
  ],
  info: [
    ["circle", { cx: 12, cy: 12, r: 10 }],
    ["path", { d: "M12 16v-4" }],
    ["path", { d: "M12 8h.01" }],
  ],
  bulb: [
    [
      "path",
      { d: "M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1 .2 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5" },
    ],
    ["path", { d: "M9 18h6" }],
    ["path", { d: "M10 22h4" }],
  ],
  "alert-circle": [
    ["circle", { cx: 12, cy: 12, r: 10 }],
    ["path", { d: "M12 8v4" }],
    ["path", { d: "M12 16h.01" }],
  ],
  "check-circle": [
    ["path", { d: "M22 11.08V12a10 10 0 1 1-5.93-9.14" }],
    ["polyline", { points: "22 4 12 14.01 9 11.01" }],
  ],
  keyboard: [
    ["rect", { x: 2, y: 4, width: 20, height: 16, rx: 2 }],
    ["path", { d: "M6 8h.01" }],
    ["path", { d: "M10 8h.01" }],
    ["path", { d: "M14 8h.01" }],
    ["path", { d: "M18 8h.01" }],
    ["path", { d: "M8 12h.01" }],
    ["path", { d: "M12 12h.01" }],
    ["path", { d: "M16 12h.01" }],
    ["path", { d: "M7 16h10" }],
  ],
  list: [
    ["path", { d: "M8 6h13" }],
    ["path", { d: "M8 12h13" }],
    ["path", { d: "M8 18h13" }],
    ["path", { d: "M3 6h.01" }],
    ["path", { d: "M3 12h.01" }],
    ["path", { d: "M3 18h.01" }],
  ],
  "move-h": [
    ["path", { d: "m18 8 4 4-4 4" }],
    ["path", { d: "m6 8-4 4 4 4" }],
    ["path", { d: "M2 12h20" }],
  ],
  alert: [
    ["path", { d: "m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3" }],
    ["path", { d: "M12 9v4" }],
    ["path", { d: "M12 17h.01" }],
  ],
  search: [
    ["circle", { cx: 11, cy: 11, r: 8 }],
    ["path", { d: "m21 21-4.3-4.3" }],
  ],
  zap: [["polygon", { points: "13 2 3 14 12 14 11 22 21 10 12 10 13 2" }]],
  star: [
    [
      "polygon",
      { points: "12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" },
    ],
  ],
  tag: [
    [
      "path",
      {
        d: "M12.586 2.586A2 2 0 0 0 11.172 2H4a2 2 0 0 0-2 2v7.172a2 2 0 0 0 .586 1.414l8.704 8.704a2.426 2.426 0 0 0 3.42 0l6.58-6.58a2.426 2.426 0 0 0 0-3.42z",
      },
    ],
    ["circle", { cx: 7.5, cy: 7.5, r: 0.5, fill: "currentColor" }],
  ],
  cog: [
    [
      "path",
      {
        d: "M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z",
      },
    ],
    ["circle", { cx: 12, cy: 12, r: 3 }],
  ],
  settings: [
    ["path", { d: "M20 7h-9" }],
    ["path", { d: "M14 17H5" }],
    ["circle", { cx: 17, cy: 17, r: 3 }],
    ["circle", { cx: 7, cy: 7, r: 3 }],
  ],
  upload: [
    ["path", { d: "M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" }],
    ["polyline", { points: "17 8 12 3 7 8" }],
    ["line", { x1: 12, y1: 3, x2: 12, y2: 15 }],
  ],
  download: [
    ["path", { d: "M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" }],
    ["polyline", { points: "7 10 12 15 17 10" }],
    ["line", { x1: 12, y1: 15, x2: 12, y2: 3 }],
  ],
  logout: [
    ["path", { d: "M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" }],
    ["polyline", { points: "16 17 21 12 16 7" }],
    ["line", { x1: 21, y1: 12, x2: 9, y2: 12 }],
  ],
  moon: [["path", { d: "M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z" }]],
  sun: [
    ["circle", { cx: 12, cy: 12, r: 4 }],
    ["path", { d: "M12 2v2" }],
    ["path", { d: "M12 20v2" }],
    ["path", { d: "m4.93 4.93 1.41 1.41" }],
    ["path", { d: "m17.66 17.66 1.41 1.41" }],
    ["path", { d: "M2 12h2" }],
    ["path", { d: "M20 12h2" }],
    ["path", { d: "m6.34 17.66-1.41 1.41" }],
    ["path", { d: "m19.07 4.93-1.41 1.41" }],
  ],
  menu: [
    ["path", { d: "M4 6h16" }],
    ["path", { d: "M4 12h16" }],
    ["path", { d: "M4 18h16" }],
  ],
  sort: [
    ["path", { d: "m21 16-4 4-4-4" }],
    ["path", { d: "M17 20V4" }],
    ["path", { d: "m3 8 4-4 4 4" }],
    ["path", { d: "M7 4v16" }],
  ],
  x: [
    ["path", { d: "M18 6 6 18" }],
    ["path", { d: "m6 6 12 12" }],
  ],
  plus: [
    ["path", { d: "M5 12h14" }],
    ["path", { d: "M12 5v14" }],
  ],
  "chevron-right": [["path", { d: "m9 18 6-6-6-6" }]],
  "chevron-left": [["path", { d: "m15 18-6-6 6-6" }]],
  "chevron-down": [["path", { d: "m6 9 6 6 6-6" }]],
  pencil: [
    ["path", { d: "M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z" }],
    ["path", { d: "m15 5 4 4" }],
  ],
  copy: [
    ["rect", { x: 8, y: 8, width: 14, height: 14, rx: 2 }],
    ["path", { d: "M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2" }],
  ],
  trash: [
    ["path", { d: "M3 6h18" }],
    ["path", { d: "M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6" }],
    ["path", { d: "M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" }],
  ],
  calendar: [
    ["rect", { x: 3, y: 4, width: 18, height: 18, rx: 2 }],
    ["path", { d: "M16 2v4" }],
    ["path", { d: "M8 2v4" }],
    ["path", { d: "M3 10h18" }],
  ],
  layers: [
    ["polygon", { points: "12 2 2 7 12 12 22 7 12 2" }],
    ["polyline", { points: "2 17 12 22 22 17" }],
    ["polyline", { points: "2 12 12 17 22 12" }],
  ],
  "filter-x": [
    ["path", { d: "M13.013 3H2l8 9.46V19l4 2v-8.54l.9-1.055" }],
    ["path", { d: "m22 3-5 5" }],
    ["path", { d: "m17 3 5 5" }],
  ],
  message: [["path", { d: "M7.9 20A9 9 0 1 0 4 16.1L2 22Z" }]],
  spark: [
    ["path", { d: "M12 2l1.9 5.6L19.5 9.5l-5.6 1.9L12 17l-1.9-5.6L4.5 9.5l5.6-1.9z", fill: "currentColor" }],
    ["path", { d: "M19 15l.9 2.1 2.1.9-2.1.9L19 21l-.9-2.1-2.1-.9 2.1-.9z", fill: "currentColor" }],
  ],
  swap: [
    ["path", { d: "M8 3 4 7l4 4" }],
    ["path", { d: "M4 7h16" }],
    ["path", { d: "m16 21 4-4-4-4" }],
    ["path", { d: "M20 17H4" }],
  ],
  languages: [
    ["path", { d: "m5 8 6 6" }],
    ["path", { d: "m4 14 6-6 2-3" }],
    ["path", { d: "M2 5h12" }],
    ["path", { d: "M7 2h1" }],
    ["path", { d: "m22 22-5-10-5 10" }],
    ["path", { d: "M14 18h6" }],
  ],
  branch: [
    ["line", { x1: 6, y1: 3, x2: 6, y2: 15 }],
    ["circle", { cx: 18, cy: 6, r: 3 }],
    ["circle", { cx: 6, cy: 18, r: 3 }],
    ["path", { d: "M18 9a9 9 0 0 1-9 9" }],
  ],
  code: [
    ["polyline", { points: "16 18 22 12 16 6" }],
    ["polyline", { points: "8 6 2 12 8 18" }],
  ],
  book: [
    ["path", { d: "M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" }],
    ["path", { d: "M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" }],
  ],
  database: [
    ["ellipse", { cx: 12, cy: 5, rx: 9, ry: 3 }],
    ["path", { d: "M3 5V19A9 3 0 0 0 21 19V5" }],
    ["path", { d: "M3 12A9 3 0 0 0 21 12" }],
  ],
  chart: [
    ["path", { d: "M12 20V10" }],
    ["path", { d: "M18 20V4" }],
    ["path", { d: "M6 20v-4" }],
  ],
  binary: [
    ["rect", { x: 14, y: 14, width: 4, height: 6, rx: 2 }],
    ["rect", { x: 6, y: 4, width: 4, height: 6, rx: 2 }],
    ["path", { d: "M6 20h4" }],
    ["path", { d: "M14 10h4" }],
    ["path", { d: "M6 14h2v6" }],
    ["path", { d: "M14 4h2v6" }],
  ],
  file: [
    ["path", { d: "M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z" }],
    ["path", { d: "M14 2v4a2 2 0 0 0 2 2h4" }],
    ["path", { d: "M10 9H8" }],
    ["path", { d: "M16 13H8" }],
    ["path", { d: "M16 17H8" }],
  ],
};
const WAVE_STOPS = {
  wv1: ["#7a63ff", 0.34, "#4a5be0", 0.06],
  wv2: ["#8f7bff", 0.26, "#5b6cf0", 0.05],
  wv3: ["#6f86ff", 0.22, "#6f5cff", 0.04],
};
function waveDefs(s) {
  // the gradients the hero waves are filled with
  const defs = s.querySelector("defs");
  for (const [id, [c1, a1, c2, a2]] of Object.entries(WAVE_STOPS)) {
    const g = document.createElementNS(SVGNS, "linearGradient");
    g.setAttribute("id", id);
    g.setAttribute("x1", "1");
    g.setAttribute("y1", "0");
    g.setAttribute("x2", "0");
    g.setAttribute("y2", "1");
    for (const [o, c, a] of [
      [0, c1, a1],
      [1, c2, a2],
    ]) {
      const st = document.createElementNS(SVGNS, "stop");
      st.setAttribute("offset", o);
      st.setAttribute("stop-color", c);
      st.setAttribute("stop-opacity", a);
      g.append(st);
    }
    defs.append(g);
  }
  return s;
}
function svg(spec, attrs) {
  const s = document.createElementNS(SVGNS, "svg");
  for (const [k, v] of Object.entries(attrs)) s.setAttribute(k, v);
  for (const [tag, a] of spec) {
    const e = document.createElementNS(SVGNS, tag);
    for (const [k, v] of Object.entries(a)) e.setAttribute(k, v);
    s.append(e);
  }
  return s;
}
const icon = (name, size = 18) =>
  svg(ICONS[name], {
    viewBox: "0 0 24 24",
    width: size,
    height: size,
    fill: "none",
    stroke: "currentColor",
    "stroke-width": 2,
    "stroke-linecap": "round",
    "stroke-linejoin": "round",
    "aria-hidden": "true",
  });
const fillIcons = (root = document) =>
  root
    .querySelectorAll("[data-icon]")
    .forEach((el) => el.replaceChildren(icon(el.dataset.icon, +el.dataset.size || 18)));
function toast(msg, kind = "", ms = 1800) {
  // kind: "", "ok" or "bad"; errors stay longer
  const t = $("#toast");
  t.textContent = msg;
  t.className = "toast show " + kind;
  clearTimeout(t._h);
  t._h = setTimeout(() => t.classList.remove("show"), ms);
}
async function api(path, opts) {
  const r = await fetch(path, opts);
  if (r.status === 401) {
    location.href = "/login";
    throw new Error("not authenticated");
  }
  return r;
}
const json = (method, body) => ({
  method,
  headers: { "content-type": "application/json" },
  body: JSON.stringify(body),
});
const CATEGORY_ERRORS = {
  name_invalid: "category_err_name_invalid",
  name_reserved: "category_err_name_reserved",
  name_taken: "category_err_name_taken",
  default_category: "category_err_default_category",
  not_empty: "category_err_not_empty",
  not_found: "category_err_not_found",
};
function categoryError(detail) {
  const d = detail && typeof detail === "object" ? detail : {};
  const key = CATEGORY_ERRORS[d.code];
  return key ? tr(key, { count: d.count ?? "?" }) : tr("category_err_failed");
}

// Everything AI is marked the same way: gradient frame (.aiframe), the spark icon and the AI tag
// Which way a translation goes by default: a note with Polish letters or mostly Polish little words is PL, otherwise EN; the user can swap it.
const noteLang = (text) => {
  const w = text.toLowerCase().match(/\p{L}+/gu) || [];
  const pl =
    (text.match(/[ąćęłńóśźż]/gi) || []).length +
    w.filter((x) => /^(i|w|z|na|nie|się|jest|do|że|to|jak|po|dla|przy|oraz)$/.test(x)).length;
  const en = w.filter((x) => /^(the|and|is|of|to|in|for|with|are|it|that|you|this)$/.test(x)).length;
  return pl >= en ? "pl" : "en";
};
const translateLabel = (to) => tr(to === "en" ? "translate_pl_en" : "translate_en_pl");
// AI components: every one carries `data-ai` and starts `hidden`; it shows only while AI is enabled AND configured (AI_READY).
const setAiReady = (on) =>
  document.querySelectorAll("[data-ai]").forEach((el) => {
    el.hidden = !on;
  });
// The rule for every AI job: while it runs, with the setting `ai_block_page` on, the page is blurred and inactive
// except the window where the AI works. Call aiBusy(() => thatElement) when the job starts and aiBusy(null) when it
// ends (done, failed or cancelled). A veil with a hole cut out at the window does it, so it needs no z-index games.
let aiGet = null,
  aiVeil = null;
const aiBlocked = () => aiGet !== null;
function aiBusy(get) {
  aiGet = SETTINGS.ai_block_page ? get : null;
  if (!aiGet) {
    if (aiVeil) aiVeil.hidden = true;
    return;
  }
  if (!aiVeil) {
    aiVeil = h("div", { class: "aiveil", "aria-hidden": "true" });
    document.body.append(aiVeil);
  }
  aiTick();
}
function aiTick() {
  const win = aiGet && aiGet();
  if (!win || !win.isConnected || !win.getClientRects().length) {
    aiGet = null;
    aiVeil.hidden = true;
    return;
  } // the window is gone: never leave the page locked
  const r = win.getBoundingClientRect(),
    p = (v) => Math.round(v) + "px";
  aiVeil.hidden = false;
  aiVeil.style.clipPath =
    "polygon(evenodd, 0 0, 100% 0, 100% 100%, 0 100%, 0 0, " +
    [
      [r.left, r.top],
      [r.left, r.bottom],
      [r.right, r.bottom],
      [r.right, r.top],
      [r.left, r.top],
    ]
      .map(([x, y]) => p(x) + " " + p(y))
      .join(", ") +
    ")";
  requestAnimationFrame(() => {
    if (aiGet) aiTick();
  }); // follows the window while it grows, moves or scrolls
}
const aiTag = () => h("span", { class: "aitag" }, icon("spark", 10), "AI");
const SUMMARY_ERRORS = {
  not_enabled: "ai_err_not_enabled",
  not_configured: "ai_err_not_configured",
  timeout: "ai_err_timeout",
  failed: "ai_err_failed_summary",
};
const AI_ERRORS = {
  not_enabled: "ai_err_not_enabled",
  not_configured: "ai_err_not_configured",
  timeout: "ai_err_timeout",
  failed: "ai_err_failed",
};

// --- placeholders: one shimmering block, used to build skeleton loading states
const sk = (w, ht = 12, cls = "") => h("span", { class: "sk " + cls, style: "width:" + w + ";height:" + ht + "px" });
// Sort orders of the note list ("" = relevance while searching, newest first otherwise) and their labels
const SORT_LABELS = {
  "": "sort_default",
  title_asc: "sort_title_asc",
  title_desc: "sort_title_desc",
  date_desc: "sort_date_desc",
  date_asc: "sort_date_asc",
};
// --- settings: the values were embedded by the server (SETTINGS); changes are saved at once
// --- theme: the T key flips dark/light on both pages (saved like the Settings control; "themechange" lets the Settings control follow)
const applyTheme = (t) => {
  document.documentElement.dataset.theme = t;
  document.dispatchEvent(new CustomEvent("themechange", { detail: t }));
};
async function toggleTheme() {
  const before = SETTINGS.theme,
    next = before === "light" ? "dark" : "light";
  applyTheme(next);
  if (!(await saveSettings({ theme: next }))) applyTheme(before);
}
document.addEventListener("keydown", (e) => {
  if ((e.key !== "t" && e.key !== "T") || e.ctrlKey || e.metaKey || e.altKey || e.repeat) return;
  if (
    /INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName) ||
    document.activeElement.isContentEditable ||
    document.querySelector("dialog[open]") ||
    aiBlocked()
  )
    return;
  e.preventDefault();
  toggleTheme();
});
// --- keyboard shortcuts: one list for the Settings section and the "?" window (also opened by the sidebar icon on the notes page)
const MAC = /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);
const SHORTCUTS = [
  [["/"], "sc_search"],
  [[MAC ? "⌘" : "Ctrl", "K"], "sc_search_any"],
  [["N"], "sc_new"],
  [["↑", "↓"], "sc_move"],
  [["T"], "sc_theme"],
  [["?"], "sc_help"],
  [["Esc"], "sc_clear"],
  [["Esc"], "sc_reading_exit"],
];
const shortcutRows = () => [
  ...SHORTCUTS.map(([keys, label]) =>
    h(
      "div",
      { class: "krow" },
      h("span", {}, tr(label)),
      h(
        "span",
        { class: "keys" },
        keys.map((k) => h("kbd", {}, k)),
      ),
    ),
  ),
  h("div", { class: "krow" }, h("span", {}, tr("sc_reading_open")), h("span", { class: "keys" }, icon("book", 16))),
];
let kdlg = null;
function showShortcuts() {
  if (document.querySelector("dialog[open]")) return;
  if (!kdlg) {
    const close = () => kdlg.close();
    kdlg = h(
      "dialog",
      { class: "kdlg", "aria-label": tr("settings_nav_shortcuts") },
      h(
        "div",
        { class: "dlg-head" },
        h("h3", {}, tr("settings_nav_shortcuts")),
        h(
          "button",
          { type: "button", class: "btn icon", "aria-label": tr("ai_close"), title: tr("ai_close"), onclick: close },
          icon("x", 14),
        ),
      ),
      h("div", {}, shortcutRows()),
      h(
        "div",
        { class: "kfoot" },
        location.pathname === "/settings"
          ? h("span")
          : h("a", { class: "linkbtn", href: "/settings#shortcuts" }, tr("sc_all_settings")),
        h("button", { type: "button", class: "btn", onclick: close }, tr("ai_close")),
      ),
    );
    kdlg.addEventListener("click", (e) => {
      if (e.target === kdlg) close();
    }); // a click on the backdrop
    document.body.append(kdlg);
  }
  kdlg.showModal();
}
document.addEventListener("keydown", (e) => {
  if (e.key !== "?" || e.ctrlKey || e.metaKey || e.altKey) return;
  const a = document.activeElement,
    emptySearch = a.id === "q" && !a.value; // the search box has focus on load: a "?" as its first character opens the window
  if ((/INPUT|TEXTAREA|SELECT/.test(a.tagName) && !emptySearch) || a.isContentEditable || aiBlocked()) return;
  e.preventDefault();
  showShortcuts();
});
const READ_WIDTHS = [680, 760, 880],
  READ_SIZES = [15, 22]; // reading mode: text column widths (px) and text size range
async function saveSettings(patch) {
  // true when saved; on failure a toast says so and the caller reverts
  try {
    const r = await api("/api/settings", json("PUT", patch));
    if (!r.ok) throw new Error("save");
    Object.assign(SETTINGS, await r.json());
    return true;
  } catch (e) {
    if (e.message !== "not authenticated") toast(tr("settings_save_error"), "bad");
    return false;
  }
}
