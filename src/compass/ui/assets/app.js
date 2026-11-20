/*CORE*/
/*READER_PURE*/
/*EDITOR_PURE*/

// --- text helpers, used only to highlight matches (the server does the searching and ranking)
const fold1 = (c) => (c.length > 1 ? c : c === "ł" || c === "Ł" ? "l" : c.normalize("NFD")[0].toLowerCase());
const fold = (s) => Array.from(s).map(fold1).join("");
const words = (s) => fold(s).match(/[\p{L}\p{N}]+/gu) || [];
const limitFor = (n) => (n < 4 ? 0 : n < 8 ? 1 : 2);
function dist(a, b, k) {
  // optimal string alignment; an adjacent swap is one edit
  if (Math.abs(a.length - b.length) > k) return k + 1;
  let before = null,
    row = Array.from({ length: b.length + 1 }, (_, j) => j);
  for (let i = 1; i <= a.length; i++) {
    const cur = [i];
    for (let j = 1; j <= b.length; j++) {
      let v = Math.min(row[j] + 1, cur[j - 1] + 1, row[j - 1] + (a[i - 1] !== b[j - 1] ? 1 : 0));
      if (before && i > 1 && j > 1 && a[i - 1] === b[j - 2] && a[i - 2] === b[j - 1])
        v = Math.min(v, before[j - 2] + 1);
      cur[j] = v;
    }
    if (Math.min(...cur) > k) return k + 1;
    before = row;
    row = cur;
  }
  return row[b.length];
}
function hlNodes(text, tokens) {
  // marks prefix and typo hits; builds text nodes, never HTML
  const f = fold(text),
    marks = [];
  if (tokens.length)
    for (const m of f.matchAll(/[\p{L}\p{N}]+/gu)) {
      for (const t of tokens) {
        const w = m[0],
          k = limitFor(t.length);
        if (w === t || w.startsWith(t)) {
          marks.push([m.index, m.index + Math.min(t.length, w.length)]);
          break;
        }
        if (k && Math.abs(w.length - t.length) <= k && dist(t, w, k) <= k) {
          marks.push([m.index, m.index + w.length]);
          break;
        }
      }
    }
  const out = [];
  let last = 0;
  for (const [a, b] of marks) {
    if (a < last) continue;
    out.push(text.slice(last, a), h("mark", {}, text.slice(a, b)));
    last = b;
  }
  out.push(text.slice(last));
  return out;
}
function readTags(v) {
  // "SQL, Soft  Skills" -> ["soft skills", "sql"]; limits match the server
  const tags = [
    ...new Set(
      v
        .split(",")
        .map((t) => t.trim().toLowerCase().replace(/\s+/g, " "))
        .filter(Boolean),
    ),
  ].sort((a, b) => a.localeCompare(b, "pl"));
  const error = tags.some((t) => t.length > 30)
    ? tr("tag_long", { n: 30 })
    : tags.length > 10
      ? tr("tag_many", { n: 10 })
      : "";
  return { tags, error };
}
const TOPICS = [
  [/rozmow|interview|soft/, "message"],
  [/\bgit\b/, "branch"],
  [/algorytm|algorithm|big o/, "binary"],
  [/sql|baz|database|data/, "database"],
  [/statyst|mediana|wartosc p/, "chart"],
  [/kod|code|program|api|docker|devops|rest/, "code"],
  [/nauk|learn|biolog|fotosint/, "book"],
  [/pomysl|idea|wskazowk/, "star"],
];
const noteIcon = (note) => {
  const hay = fold(note.title + " " + note.tags.join(" "));
  const hit = TOPICS.find(([re]) => re.test(hay));
  return hit ? hit[1] : "file";
};
const shortDate = (iso) => new Date(iso).toLocaleDateString(LANG, { day: "numeric", month: "short" });
const longDate = (iso) => new Date(iso).toLocaleDateString(LANG, { day: "numeric", month: "short", year: "numeric" });

/*READER_UI*/
/*EDITOR_UI*/
/*CHAT_UI*/
// --- state and server calls
const state = {
  q: "",
  sel: new Set(),
  category: null,
  cur: null,
  mode: "view",
  list: [],
  tags: [],
  categories: [],
  total: 0,
  reading: false,
  sort: "",
};
let seq = 0,
  timer;
const tokens = () => words(state.q);
const SAVE_ERROR = tr("save_error");

const defaultId = () => (state.categories.find((c) => c.default) || { id: 1 }).id;
const catLabel = (c) => (c.default ? tr("category_default") : c.name);
const catName = (id) => {
  const c = state.categories.find((x) => x.id === id);
  return c ? catLabel(c) : "";
};
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
const setView = (v) => {
  $("#app").dataset.view = v;
};
function showLoadError() {
  $("#count").textContent = "";
  $("#results").replaceChildren(
    h(
      "div",
      { class: "empty" },
      h("div", {}, tr("load_failed")),
      h("button", { type: "button", class: "btn", style: "margin-top:12px", onclick: () => load() }, tr("retry")),
    ),
  );
  if (state.mode === "view")
    $("#detail").replaceChildren(h("div", { class: "card" }, h("div", { class: "empty" }, tr("load_failed"))));
}
// --- skeleton loading: one block (`sk`) and a few variants built from it; shown only while we really wait
const SK_CARDS = [
  { t: 58, a: 92, b: 64, tags: [54, 70, 46] },
  { t: 72, a: 84, b: 52, tags: [62, 48] },
  { t: 46, a: 96, b: 70, tags: [44, 66, 58] },
  { t: 64, a: 78, b: 40, tags: [58, 52, 72] },
  { t: 52, a: 90, b: 58, tags: [66, 46] },
  { t: 68, a: 82, b: 48, tags: [50, 60, 44] },
];
function skeletonCard(i) {
  const v = SK_CARDS[i % SK_CARDS.length];
  return h(
    "div",
    { class: "skcard", "aria-hidden": "true" },
    sk("40px", 40, "round"),
    h(
      "div",
      { class: "skbody" },
      h("div", { class: "sktop" }, sk(v.t + "%", 15), sk("36px", 10)),
      sk(v.a + "%", 11),
      sk(v.b + "%", 11),
      h(
        "div",
        { class: "sktags" },
        v.tags.map((w) => sk(w + "px", 20, "pill")),
      ),
    ),
  );
}
function skeletonPanel() {
  return h(
    "div",
    { class: "card skdetail", "aria-hidden": "true" },
    h(
      "div",
      { class: "skhero" },
      h("div", { class: "sktop" }, sk("170px", 28, "pill"), sk("120px", 36, "pill")),
      h("div", { style: "margin-top:18px" }, sk("64%", 30)),
      h("div", { class: "sktags" }, sk("58px", 26, "pill"), sk("92px", 26, "pill"), sk("70px", 26, "pill")),
    ),
    h(
      "div",
      { class: "sheet" },
      h("div", { class: "sklines" }, sk("96%"), sk("88%"), sk("92%"), sk("60%"), sk("100%", 96)),
    ),
  );
}
let skTimer = 0,
  skShown = false,
  loaded = false;
function showSkeleton(withPanel) {
  skShown = true;
  $("#results").setAttribute("aria-busy", "true");
  $("#results").replaceChildren(...[0, 1, 2, 3, 4, 5].map(skeletonCard));
  if (withPanel && state.mode === "view") $("#detail").replaceChildren(skeletonPanel());
}
function loadingStarted() {
  // first load: at once; later loads: only if the answer is slow (no flicker)
  clearTimeout(skTimer);
  if (!loaded) showSkeleton(true);
  else skTimer = setTimeout(() => showSkeleton(false), 350);
}
function loadingDone() {
  // true when a skeleton was on screen, so the real cards should fade in
  clearTimeout(skTimer);
  $("#results").removeAttribute("aria-busy");
  const was = skShown;
  skShown = false;
  return was;
}
async function load(keepDetail = false) {
  const mine = ++seq,
    had = state.cur;
  const params = new URLSearchParams({ q: state.q });
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
    if (mine === seq && e.message !== "not authenticated") {
      loadingDone();
      loaded = false;
      showLoadError();
    }
    return;
  }
  if (mine !== seq) return;
  const reveal = loadingDone();
  loaded = true;
  state.total = state.categories.reduce((sum, c) => sum + c.count, 0);
  state.list = list;
  if (state.mode === "view" && !list.some((n) => n.id === state.cur)) state.cur = list.length ? list[0].id : null;
  renderList();
  if (reveal) {
    $("#results").classList.add("reveal");
    setTimeout(() => $("#results").classList.remove("reveal"), 400);
  }
  if (!keepDetail || had !== state.cur || reveal) renderDetail();
}
function toggleCategory(id) {
  state.category = state.category === id ? null : id;
  renderCategories();
  load();
}
function toggleTag(t) {
  state.sel.has(t) ? state.sel.delete(t) : state.sel.add(t);
  renderTagbar();
  load();
}
function openNew() {
  state.mode = "new";
  state.cur = null;
  setView("detail");
  renderList();
  renderDetail();
}
function select(id) {
  state.cur = id;
  state.mode = "view";
  setView("detail");
  renderList();
  renderDetail();
}
function resetFilters(all) {
  state.sel.clear();
  state.category = null;
  if (all) {
    state.q = "";
    $("#q").value = "";
  }
  state.mode = "view";
  renderTagbar();
  renderCategories();
  load();
}

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
  const entry = (label, count, on, handler) =>
    h(
      "button",
      { type: "button", class: "cat" + (on ? " on" : ""), onclick: handler },
      h("span", {}, label),
      h("span", { class: "n" }, count),
    );
  $("#catbar").replaceChildren(
    entry(tr("category_all"), total, state.category === null, () => {
      state.category = null;
      renderCategories();
      load();
    }),
    ...state.categories.map((c) => entry(catLabel(c), c.count, state.category === c.id, () => toggleCategory(c.id))),
  );
  fitList("cat", CAT_PREVIEW + 1, catsOpen); // +1: the "All" entry
}
const TAG_PREVIEW = 9;
let tagsOpen = false;
// Collapsed: the first `preview` items; open: everything. The height change is animated (tags and categories alike).
function fitList(name, preview, open) {
  const bar = $("#" + name + "bar"),
    more = $("#" + name + "more"),
    kids = bar.children,
    many = kids.length > preview;
  more.hidden = !many;
  more.classList.toggle("open", open);
  $("#" + name + "moretext").textContent = open ? tr("tags_less") : tr("tags_more");
  if (!many) {
    bar.style.maxHeight = "";
    return;
  }
  const last = kids[preview - 1];
  bar.style.maxHeight = (open ? bar.scrollHeight : last.offsetTop + last.offsetHeight) + "px";
}
const fitTags = () => fitList("tag", TAG_PREVIEW, tagsOpen);
function renderTagbar() {
  renderFilters();
  $("#tagbar").replaceChildren(
    ...state.tags.map((t) =>
      h(
        "button",
        { type: "button", class: "chip" + (state.sel.has(t.name) ? " on" : ""), onclick: () => toggleTag(t.name) },
        "#" + t.name,
        h("span", { class: "n" }, t.count),
      ),
    ),
  );
  fitTags();
}
function categoryBadge(id) {
  // the default category is not shown on cards (less noise)
  const c = state.categories.find((x) => x.id === id);
  return c && !c.default ? h("span", { class: "badge cat" }, c.name) : null;
}
// A card shows the start of the text without Markdown markers; the note itself is never changed.
const snippet = (body) =>
  body
    .replace(/^\s*>\s*\[!\w+\]\s*/gm, "")
    .replace(/```\w*/g, " ")
    .replace(/^\s*#{1,6}\s+/gm, "")
    .replace(/\*\*|__|~~|`/g, "")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 160);
function renderList() {
  const tk = tokens(),
    n = state.list.length;
  $("#results").classList.toggle("searching", !!state.q); // one line of text per card, two while searching so the match shows
  $("#count").textContent =
    n === 50
      ? tr("top50")
      : n +
        " " +
        T.count[new Intl.PluralRules(LANG).select(n)] +
        (state.category !== null ? " • " + catName(state.category) : "") +
        (state.sel.size ? " • " + [...state.sel].map((t) => "#" + t).join(" ") : "");
  const none = !n && !state.q && !state.sel.size && state.category === null && state.total === 0;
  $("#results").replaceChildren(
    ...(n
      ? state.list.map((note) =>
          h(
            "button",
            {
              type: "button",
              class: "res" + (note.id === state.cur && state.mode === "view" ? " on" : ""),
              onclick: () => select(note.id),
            },
            h("div", { class: "ico" }, icon(noteIcon(note), 20)),
            h(
              "div",
              {},
              h(
                "div",
                { class: "top" },
                h("span", { class: "t" }, hlNodes(note.title, tk)),
                h("span", { class: "date" }, shortDate(note.created_at)),
              ),
              h("div", { class: "s" }, hlNodes(snippet(note.body), tk)),
              h(
                "div",
                { class: "meta" },
                categoryBadge(note.category_id),
                note.tags.map((t) =>
                  h(
                    "span",
                    {
                      class: "chip mini" + (state.sel.has(t) ? " on" : ""),
                      onclick: (e) => {
                        e.stopPropagation();
                        toggleTag(t);
                      },
                    },
                    "#" + t,
                  ),
                ),
              ),
            ),
            h("span", { class: "chev" }, icon("chevron-right", 16)),
          ),
        )
      : [h("div", { class: "empty" }, tr(none ? "empty_none" : "no_results"))]),
  );
}
let chat = null; // the chat panel, made on first use and kept: opening a source note must not lose the conversation
function openChat() {
  if (!AI_READY) return;
  chat = chat || makeChat({ openNote: openSource, close: closeChat });
  exitReading();
  state.mode = "chat";
  setView("detail");
  renderList();
  renderDetail();
  chat.show();
}
function closeChat() {
  state.mode = "view";
  setView("list");
  renderList();
  renderDetail();
} // the panel is kept: "Ask" brings the conversation back
async function openSource(id, title) {
  // a note named in an answer: found through its title, so it is in the (limited) list
  state.q = title;
  $("#q").value = title;
  state.sel.clear();
  state.category = null;
  state.mode = "view";
  state.cur = id;
  setView("detail");
  renderTagbar();
  renderCategories();
  await load();
}
function renderDetail() {
  const d = $("#detail");
  if (state.mode === "chat") {
    d.replaceChildren(h("div", { class: "card chatcard" }, chat.el));
    return;
  }
  if (state.mode === "new") {
    exitReading();
    d.replaceChildren(
      h(
        "div",
        { class: "card" },
        newPanel({
          onCancel: () => {
            state.mode = "view";
            setView("list");
            load();
          },
          onCreated: async (n) => {
            state.q = "";
            $("#q").value = "";
            state.sel.clear();
            state.category = null;
            state.mode = "view";
            state.cur = n.id;
            await loadCategories();
            await loadTags();
            await load();
            toast(tr("toast_created"));
          },
        }),
      ),
    );
    return;
  }
  const n = state.list.find((x) => x.id === state.cur);
  if (!n) exitReading();
  if (!n) {
    d.replaceChildren(h("div", { class: "card" }, h("div", { class: "empty" }, tr("pick_or_add"))));
    return;
  }
  d.replaceChildren(
    h(
      "div",
      { class: "card" },
      notePanel(n, {
        onChange: async () => {
          await loadCategories();
          await loadTags();
          await load(true);
          toast(tr("toast_saved"));
        },
        onDeleted: async () => {
          state.cur = null;
          setView("list");
          await loadCategories();
          await loadTags();
          await load();
          toast(tr("toast_deleted"));
        },
      }),
    ),
  );
}

// --- forms and the note panel (edit and delete each need a second, explicit confirmation)
function suggestions(input) {
  return h(
    "div",
    { class: "chips" },
    state.tags.slice(0, 24).map((t) =>
      h(
        "button",
        {
          type: "button",
          class: "chip ghost",
          onclick: () => {
            const have = readTags(input.value).tags;
            if (!have.includes(t.name)) input.value = have.concat(t.name).join(", ");
            input.focus();
          },
        },
        t.name,
      ),
    ),
  );
}
// A <select> of the categories plus a quick way to add one without leaving the form.
function categoryField(selectedId) {
  const select = h("select", { "aria-label": tr("label_category") });
  const fill = (id) => {
    select.replaceChildren(...state.categories.map((c) => h("option", { value: String(c.id) }, catLabel(c))));
    select.value = String(id);
  };
  fill(selectedId);
  const err = h("div", { class: "err" });
  const name = h("input", { placeholder: tr("category_new_ph"), maxlength: 60, autocomplete: "off" });
  const quick = h("div", { class: "qrow", hidden: true });
  const close = () => {
    quick.hidden = true;
    name.value = "";
    err.textContent = "";
  };
  async function add() {
    err.textContent = "";
    const r = await api("/api/categories", json("POST", { name: name.value }));
    const body = (await r.json().catch(() => null)) || {};
    if (r.status === 201) {
      await loadCategories();
      fill(body.id);
    } else if (r.status === 409 && body.detail && body.detail.code === "name_taken")
      fill(body.detail.id); // already exists: just use it
    else {
      err.textContent = categoryError(body.detail);
      return;
    }
    close();
    select.focus();
  }
  name.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      e.stopPropagation();
      add();
    } else if (e.key === "Escape") {
      e.stopPropagation();
      close();
      select.focus();
    }
  });
  quick.append(
    name,
    h("button", { type: "button", class: "btn primary", onclick: add }, tr("category_add")),
    h(
      "button",
      {
        type: "button",
        class: "btn",
        onclick: () => {
          close();
          select.focus();
        },
      },
      tr("cancel"),
    ),
  );
  const row = h(
    "div",
    { class: "qrow" },
    select,
    h(
      "button",
      {
        type: "button",
        class: "btn",
        onclick: () => {
          quick.hidden = false;
          name.focus();
        },
      },
      tr("category_new"),
    ),
  );
  select.style.flex = "1";
  return { el: h("div", { class: "catfield" }, row, quick, err), value: () => Number(select.value) };
}
function noteForm(init, message) {
  const title = h("input", { value: init.title, maxlength: 200, placeholder: tr("label_title") });
  const body = h("textarea", { value: init.body, placeholder: tr("label_body"), maxlength: 20000 });
  const mdHint = h("div", { class: "hint2" }, tr("md_hint"));
  const editor = markdownEditor(body); // the toolbar and the preview tab around the same textarea
  const tags = h("input", { value: init.tags.join(", "), placeholder: tr("label_tags"), autocomplete: "off" });
  const category = categoryField(init.category_id);
  const err = h("div", { class: "err" }, message);
  const el = h(
    "div",
    { class: "form" },
    h("label", {}, tr("label_title")),
    title,
    h("label", {}, tr("label_body")),
    editor.el,
    mdHint,
    h("label", {}, tr("label_tags")),
    tags,
    suggestions(tags),
    h("label", {}, tr("label_category")),
    category.el,
    err,
  );
  return {
    el,
    err,
    focus: () => title.focus(),
    values() {
      const t = readTags(tags.value),
        ti = title.value.trim();
      err.textContent = !ti ? tr("empty_title") : t.error;
      return err.textContent ? null : { title: ti, body: body.value, tags: t.tags, category_id: category.value() };
    },
  };
}
async function copyNote(note) {
  try {
    await navigator.clipboard.writeText(note.title + "\n\n" + note.body);
    toast(tr("copied"));
  } catch (e) {
    toast(tr("copy_failed"));
  }
}
function notePanel(note, cb) {
  const root = h("div", { class: "panel" });
  let mode = "read",
    draft = null,
    msg = "";
  let preview = null,
    sum = null,
    tjob = 0,
    sjob = 0,
    swapped = false; // preview: the translation, shown in place of the note: {state: "loading"|"done"|"error", text, msg}; swapped: the user turned its direction around; sum: the summary, shown above the note: {state, text, msg, collapsed}; the counters drop a late answer
  const dropAi = () => {
    tjob++;
    sjob++;
    preview = null;
    sum = null;
    swapped = false;
  };
  const back = () => {
    dropAi();
    mode = "read";
    draft = null;
    msg = "";
    draw();
    loadSummary();
  }; // the kept summary comes back (stale if the note changed)
  async function save() {
    const r = await api("/api/notes/" + note.id, json("PUT", draft));
    if (!r.ok) {
      msg = SAVE_ERROR;
      mode = "edit";
      draw();
      return;
    }
    Object.assign(note, await r.json());
    back();
    cb.onChange();
  }
  async function remove() {
    const r = await api("/api/notes/" + note.id, { method: "DELETE" });
    if (r.status !== 204 && r.status !== 404) {
      msg = tr("delete_failed");
      mode = "read";
      draw();
      return;
    }
    cb.onDeleted(); // a 404 means it is already gone, which is the state the user wanted
  }
  const target = () => ((noteLang(note.body) === "pl") !== swapped ? "en" : "pl"); // the language to translate into
  // Translation: a preview in place of the note. Leaves the note untouched, saves nothing.
  async function translate() {
    const mine = ++tjob,
      to = target();
    preview = {
      state: "loading",
      minH: Math.max(160, (root.querySelector(".sheet") || { offsetHeight: 0 }).offsetHeight - 50),
    };
    draw();
    aiBusy(() => root.querySelector(".aipad"));
    let next;
    try {
      const r = await api("/api/notes/" + note.id + "/translate?to=" + to, { method: "POST" });
      if (r.ok) {
        const d = await r.json();
        next = { state: "done", text: d.text, lang: d.lang };
      } else {
        const d = (await r.json().catch(() => ({}))).detail;
        next = { state: "error", msg: tr(AI_ERRORS[d && d.code] || "ai_err_failed") };
      }
    } catch (e) {
      if (e.message === "not authenticated") return;
      next = { state: "error", msg: tr("ai_err_failed") };
    }
    if (mine !== tjob || !preview) return;
    aiBusy(null);
    preview = { ...next, minH: preview.minH };
    draw();
  }
  const closeTranslation = () => {
    tjob++;
    preview = null;
    swapped = false;
    draw();
  };
  const openTranslation = () => {
    swapped = false;
    translate();
  };
  const swap = () => {
    swapped = !swapped;
    translate();
  };
  async function copyAiText(text) {
    try {
      await navigator.clipboard.writeText(text);
      toast(tr("copied"));
    } catch (e) {
      toast(tr("copy_failed"));
    }
  }
  function translationBlock(tk) {
    const head = h(
      "div",
      { class: "aihd" },
      icon("spark", 16),
      h("span", {}, translateLabel(target())),
      preview.state === "loading"
        ? null
        : h(
            "button",
            {
              type: "button",
              class: "btn icon",
              "aria-label": tr("translate_swap"),
              title: tr("translate_swap"),
              onclick: swap,
            },
            icon("swap", 16),
          ),
      h("span", { class: "grow" }),
      preview.state === "done"
        ? h(
            "button",
            { type: "button", class: "btn", onclick: () => copyAiText(preview.text) },
            icon("copy", 16),
            tr("copy_translation"),
          )
        : null,
      preview.state === "error"
        ? h("button", { type: "button", class: "btn primary", onclick: translate }, tr("retry"))
        : null,
      h("button", { type: "button", class: "btn", onclick: closeTranslation }, tr("back")),
    );
    const body =
      preview.state === "loading"
        ? h("div", { class: "aithink", role: "status" }, icon("spark", 30), h("span", {}, tr("translating")))
        : preview.state === "error"
          ? h("div", { class: "err aierr" }, preview.msg)
          : h("div", { class: "aibody" }, readerBody({ body: preview.text }, tk, preview.lang)); // the same layout as the note: contents, width, font
    return h(
      "div",
      { class: "aiframe aipad", style: preview.state === "done" ? "" : "min-height:" + preview.minH + "px" },
      head,
      body,
    ); // loading and errors keep the height of the note, so the page does not jump
  }
  // Summary: a block above the note (the note stays below it). Saves nothing.
  async function summarize() {
    const mine = ++sjob;
    sum = { state: "loading", collapsed: false };
    draw();
    aiBusy(() => root.querySelector(".aisum"));
    let next;
    try {
      const r = await api("/api/notes/" + note.id + "/summarize", { method: "POST" });
      if (r.ok) {
        const d = await r.json();
        next = d.text
          ? { state: "done", text: d.text, created_at: d.created_at, stale: false }
          : { state: "error", msg: tr("summary_empty") };
      } else {
        const d = (await r.json().catch(() => ({}))).detail;
        next = { state: "error", msg: tr(SUMMARY_ERRORS[d && d.code] || "ai_err_failed_summary") };
      }
    } catch (e) {
      if (e.message === "not authenticated") return;
      next = { state: "error", msg: tr("ai_err_failed_summary") };
    }
    if (mine !== sjob || !sum) return;
    aiBusy(null);
    sum = { ...next, collapsed: false };
    draw();
  }
  // The summary is kept on the server (one per note): it is there when the note is opened again, and goes stale when the note is edited.
  async function loadSummary() {
    if (!AI_READY) return;
    const mine = sjob;
    try {
      const r = await api("/api/notes/" + note.id + "/summary");
      if (!r.ok) return;
      const d = await r.json();
      if (d && mine === sjob && !sum && mode === "read") {
        sum = { state: "done", text: d.text, created_at: d.created_at, stale: d.stale, collapsed: false };
        draw();
      } // open by default
    } catch (e) {
      /* a convenience: without it the note simply shows no summary */
    }
  }
  const toggleSummary = () => {
    sum.collapsed = !sum.collapsed;
    draw();
  };
  async function removeSummary() {
    // the close button deletes a kept summary (collapsing is the chevron); an unsaved one is just dropped
    const kept = !!sum && sum.state === "done";
    sjob++;
    sum = null;
    draw();
    if (!kept) return;
    try {
      const r = await api("/api/notes/" + note.id + "/summary", { method: "DELETE" });
      if (r.status !== 204) throw new Error("delete");
    } catch (e) {
      if (e.message !== "not authenticated") toast(tr("summary_delete_failed"), "bad", 4000);
    }
  }
  function summaryBlock(tk) {
    const head = h(
      "div",
      { class: "aihd" },
      icon("spark", 16),
      h(
        "span",
        { title: sum.created_at ? tr("summary_from", { date: longDate(sum.created_at) }) : "" },
        tr("summary_h"),
      ),
      sum.stale ? h("span", { class: "stale", title: tr("summary_stale_hint") }, tr("summary_stale")) : null,
      h("span", { class: "grow" }),
      sum.state === "done"
        ? h(
            "button",
            {
              type: "button",
              class: "btn",
              "aria-label": tr("copy_summary"),
              title: tr("copy_summary"),
              onclick: () => copyAiText(sum.text),
            },
            icon("copy", 14),
            tr("copy"),
          )
        : null,
      sum.state === "loading"
        ? null
        : h(
            "button",
            { type: "button", class: "btn", onclick: summarize },
            icon("swap", 14),
            tr(sum.state === "error" ? "retry" : "ai_refresh"),
          ),
      sum.state === "done"
        ? h(
            "button",
            {
              type: "button",
              class: "btn icon chev",
              "aria-label": tr(sum.collapsed ? "ai_expand" : "ai_collapse"),
              title: tr(sum.collapsed ? "ai_expand" : "ai_collapse"),
              "aria-expanded": sum.collapsed ? "false" : "true",
              onclick: toggleSummary,
            },
            icon("chevron-down", 14),
          )
        : null,
      h(
        "button",
        {
          type: "button",
          class: "btn icon",
          "aria-label": tr(sum.state === "done" ? "summary_delete" : "ai_close"),
          title: tr(sum.state === "done" ? "summary_delete" : "ai_close"),
          onclick: removeSummary,
        },
        icon("x", 14),
      ),
    );
    const body =
      sum.state === "loading"
        ? h("div", { class: "aithink", role: "status" }, icon("spark", 18), h("span", {}, tr("summarizing")))
        : sum.state === "error"
          ? h("div", { class: "err aierr" }, sum.msg)
          : h(
              "article",
              { class: "md aisumbody" },
              mdBlocksDom(mdParse(sum.text), { tk, heads: [], lang: noteLang(note.body) }),
            );
    return h(
      "div",
      { class: "sumwrap" },
      h("div", { class: "aiframe aisum" + (sum.collapsed ? " collapsed" : "") }, head, body),
    );
  }
  // The AI actions live in one strip at the top of the sheet; its single AI tag marks everything below it (the blocks it opens carry the frame and the spark, not a second tag)
  function aiStrip() {
    if (!AI_READY) return null;
    const act = (on, ic, label, title, onclick) =>
      h(
        "button",
        {
          type: "button",
          class: "btn aibtn" + (on ? " act" : ""),
          "aria-pressed": on ? "true" : "false",
          title: title + " (AI)",
          onclick,
        },
        icon(ic, 15),
        label,
      );
    return h(
      "div",
      { class: "aistrip" },
      act(
        !!sum && !sum.collapsed,
        "align-left",
        tr("summarize_btn"),
        tr("summarize"),
        sum ? (sum.state === "done" ? toggleSummary : removeSummary) : summarize,
      ),
      act(
        !!preview,
        "languages",
        translateLabel(target()),
        translateLabel(target()),
        preview ? closeTranslation : openTranslation,
      ),
      h("span", { class: "grow" }),
      aiTag(),
    );
  }
  function draw() {
    root.dataset.mode = mode;
    if (mode === "read") {
      const tk = tokens();
      const edit = () => {
        exitReading();
        dropAi();
        draft = { title: note.title, body: note.body, tags: [...note.tags], category_id: note.category_id };
        msg = "";
        mode = "edit";
        draw();
      };
      const catBadge = h("span", { class: "badge cat" }, catName(note.category_id));
      root.replaceChildren(
        h(
          "div",
          { class: "hero" },
          waveDefs(
            svg(
              [
                ["defs", {}],
                ["path", { d: "M0 250 C 110 215, 210 140, 290 78 S 380 8, 400 0 V250 Z", fill: "url(#wv1)" }],
                ["path", { d: "M110 250 C 210 228, 300 170, 352 112 S 392 60, 400 52 V250 Z", fill: "url(#wv2)" }],
                ["path", { d: "M230 250 C 300 238, 360 205, 400 165 V250 Z", fill: "url(#wv3)" }],
              ],
              { class: "wave", viewBox: "0 0 400 250", preserveAspectRatio: "xMaxYMid slice", "aria-hidden": "true" },
            ),
          ),
          h(
            "div",
            { class: "bar" },
            h(
              "div",
              { class: "left" },
              h(
                "button",
                { type: "button", class: "iconbtn back", "aria-label": tr("back"), onclick: () => setView("list") },
                icon("chevron-left", 18),
              ),
              h("span", { class: "datebadge" }, icon("calendar", 15), tr("created") + ": " + longDate(note.created_at)),
              catBadge,
            ),
            h(
              "div",
              { class: "tools" },
              h(
                "button",
                {
                  type: "button",
                  class: "iconbtn readtoggle",
                  "aria-label": tr("reading_mode"),
                  "aria-pressed": "false",
                  title: tr("reading_mode"),
                  onclick: toggleReading,
                },
                icon("book", 17),
              ),
              h(
                "button",
                {
                  type: "button",
                  class: "iconbtn",
                  "aria-label": tr("copy"),
                  title: tr("copy"),
                  onclick: () => copyNote(note),
                },
                icon("copy", 17),
              ),
              h(
                "button",
                { type: "button", class: "iconbtn", "aria-label": tr("edit"), title: tr("edit"), onclick: edit },
                icon("pencil", 17),
              ),
              h(
                "button",
                {
                  type: "button",
                  class: "iconbtn del",
                  "aria-label": tr("delete"),
                  title: tr("delete"),
                  onclick: () => {
                    dropAi();
                    msg = "";
                    mode = "del";
                    draw();
                  },
                },
                icon("trash", 17),
              ),
            ),
          ),
          h("h2", {}, hlNodes(note.title, tk)),
          h(
            "div",
            { class: "chips" },
            note.tags.map((t) =>
              h(
                "button",
                { type: "button", class: "chip" + (state.sel.has(t) ? " on" : ""), onclick: () => toggleTag(t) },
                "#" + t,
              ),
            ),
          ),
        ),
        h(
          "div",
          { class: "sheet" },
          aiStrip(),
          preview ? translationBlock(tk) : [sum && AI_READY ? summaryBlock(tk) : null, readerBody(note, tk)],
          h("div", { class: "err" }, msg),
        ),
      );
      setTimeout(() => {
        watchToc(root);
        syncReadButton();
      }, 0); // after the panel is in the page
    } else if (mode === "del") {
      root.replaceChildren(
        h("h2", {}, note.title),
        h(
          "div",
          { class: "confirm" },
          h("span", {}, tr("confirm_delete")),
          h("button", { class: "btn danger", onclick: remove }, tr("yes_delete")),
          h("button", { class: "btn", onclick: back }, tr("back")),
        ),
      );
    } else if (mode === "edit") {
      const f = noteForm(draft, msg);
      root.replaceChildren(
        f.el,
        h(
          "div",
          { class: "row" },
          h(
            "button",
            {
              class: "btn primary",
              onclick: () => {
                const v = f.values();
                if (v) {
                  draft = v;
                  msg = "";
                  mode = "confirm";
                  draw();
                }
              },
            },
            tr("save"),
          ),
          h("button", { class: "btn", onclick: back }, tr("cancel")),
        ),
      );
      f.focus();
    } else {
      root.replaceChildren(
        h("h2", {}, draft.title),
        h(
          "div",
          { class: "confirm warn" },
          h("span", {}, tr("confirm_save")),
          h("button", { class: "btn primary", onclick: save }, tr("yes_overwrite")),
          h(
            "button",
            {
              class: "btn",
              onclick: () => {
                mode = "edit";
                draw();
              },
            },
            tr("back"),
          ),
        ),
      );
    }
  }
  draw();
  loadSummary(); // a kept summary is shown at once
  return root;
}
function newPanel(cb) {
  const f = noteForm({ title: "", body: "", tags: [], category_id: state.category ?? defaultId() }, "");
  const root = h(
    "div",
    { class: "panel pad" },
    h("h2", {}, tr("new_note_h")),
    f.el,
    h(
      "div",
      { class: "row" },
      h(
        "button",
        {
          class: "btn primary",
          onclick: async () => {
            const v = f.values();
            if (!v) return;
            const r = await api("/api/notes", json("POST", v));
            if (!r.ok) {
              f.err.textContent = SAVE_ERROR;
              return;
            }
            cb.onCreated(await r.json());
          },
        },
        tr("save"),
      ),
      h("button", { class: "btn", onclick: cb.onCancel }, tr("cancel")),
    ),
  );
  setTimeout(() => f.focus());
  return root;
}

// --- wiring
$("#q").addEventListener("input", () => {
  state.q = $("#q").value;
  clearTimeout(timer);
  timer = setTimeout(() => {
    state.mode = "view";
    load();
  }, 100);
});
$("#new").addEventListener("click", openNew);
$("#chatbtn").addEventListener("click", () => {
  openMenu(false);
  openChat();
});
$("#f-all").addEventListener("click", () => {
  state.sel.clear();
  state.category = null;
  state.mode = "view";
  renderTagbar();
  renderCategories();
  load();
});
$("#f-clear").addEventListener("click", () => resetFilters(true));
// Sorting: "" is the default (newest first, or by relevance while searching); a chosen order always wins
state.sort = SETTINGS.sort;
$("#sort").replaceChildren(...Object.entries(SORT_LABELS).map(([value, key]) => h("option", { value }, tr(key))));
const syncSort = () => {
  $("#sort").value = state.sort;
  $("#sortbox").classList.toggle("on", state.sort !== "");
};
syncSort();
$("#sort").addEventListener("change", async () => {
  const prev = state.sort;
  state.sort = $("#sort").value;
  syncSort();
  load();
  if (!(await saveSettings({ sort: state.sort }))) {
    state.sort = prev;
    syncSort();
    load();
  }
});
applyReader(false);
$("#r-smaller").addEventListener("click", () => {
  READER.size = Math.max(READ_SIZES[0], READER.size - 1);
  applyReader();
});
$("#r-larger").addEventListener("click", () => {
  READER.size = Math.min(READ_SIZES[1], READER.size + 1);
  applyReader();
});
$("#r-width").addEventListener("click", () => {
  READER.width = (READER.width + 1) % READ_WIDTHS.length;
  applyReader();
});
$("#r-exit").addEventListener("click", exitReading);
$("#catmore").addEventListener("click", () => {
  catsOpen = !catsOpen;
  fitList("cat", CAT_PREVIEW + 1, catsOpen);
});
$("#tagmore").addEventListener("click", () => {
  tagsOpen = !tagsOpen;
  fitTags();
});
const openMenu = (on) => {
  $("#app").classList.toggle("menu", on);
  $("#scrim").hidden = !on;
};
$("#menu").addEventListener("click", () => openMenu(true));
$("#kbbtn").addEventListener("click", () => {
  openMenu(false);
  showShortcuts();
});
$("#scrim").addEventListener("click", () => openMenu(false));
$("#shortcut").textContent = /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent) ? "⌘ K" : "Ctrl K";
document.addEventListener("keydown", (e) => {
  if (document.querySelector("dialog[open]") || aiBlocked()) return; // a dialog handles its own keys (Esc closes it natively); the page is blocked while AI works
  if (state.reading) {
    if (e.key === "Escape") {
      e.preventDefault();
      exitReading();
    }
    return;
  } // reading mode: Esc leaves it, the rest scrolls
  const typing = /INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName),
    q = $("#q");
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
    e.preventDefault();
    q.focus();
    q.select();
  } else if (e.key === "/" && !typing) {
    e.preventDefault();
    q.focus();
  } else if ((e.key === "n" || e.key === "N") && !typing) {
    e.preventDefault();
    openNew();
  } else if (e.key === "Escape") {
    openMenu(false);
    resetFilters(true);
    q.focus();
  } else if (
    (e.key === "ArrowDown" || e.key === "ArrowUp") &&
    state.list.length &&
    !e.altKey &&
    !e.ctrlKey &&
    !e.metaKey &&
    (document.activeElement === q || (!typing && state.mode === "view"))
  ) {
    // from the search box, or anywhere outside a form
    const i = state.list.findIndex((x) => x.id === state.cur);
    const next = state.list[Math.max(0, Math.min(state.list.length - 1, i + (e.key === "ArrowDown" ? 1 : -1)))];
    e.preventDefault();
    select(next.id);
    const on = document.querySelector(".res.on");
    if (on) on.scrollIntoView({ block: "nearest" }); // keep the chosen card in view (the list scrolls, not the page)
  }
});
fillIcons();
setAiReady(AI_READY);
loadTags();
loadCategories().then(() => load()); // categories first: the note's category badge and the total need them
