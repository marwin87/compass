"""The single notes page. Note content is only ever inserted via textContent."""

INDEX_HTML = r"""<!doctype html>
<html lang="pl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Compass</title>
<style>
  :root { color-scheme: light dark; font-family: system-ui, sans-serif; }
  body { max-width: 52rem; margin: 0 auto; padding: 1rem; }
  header { display: flex; justify-content: space-between; align-items: center; }
  h1 { margin: 0; font-size: 1.4rem; }
  input, textarea, button { font: inherit; padding: .5rem; box-sizing: border-box; }
  #q { width: 100%; font-size: 1.1rem; margin: 1rem 0; }
  ul { list-style: none; padding: 0; margin: 0 0 1rem; }
  li button { width: 100%; text-align: left; margin-bottom: .25rem; cursor: pointer; }
  li small { display: block; opacity: .7; white-space: nowrap; overflow: hidden;
             text-overflow: ellipsis; }
  #view { border: 1px solid; border-radius: .5rem; padding: 1rem; margin-bottom: 1rem; }
  #vb { white-space: pre-wrap; }
  details { margin-bottom: 1rem; }
  form.add { display: grid; gap: .5rem; margin-top: .5rem; }
  #err, #eerr, #derr { color: crimson; }
  #status { color: green; min-height: 1.2em; }
  [hidden] { display: none !important; }
  #eact, #confirm, #ract, #dconfirm { display: flex; gap: .5rem; align-items: center; }
  #editform { display: grid; gap: .5rem; }
  .chips { display: flex; flex-wrap: wrap; gap: .25rem; margin: .25rem 0 .5rem; }
  .chip { padding: .1rem .5rem; border-radius: 1rem; cursor: pointer; font-size: .85rem; }
  .chip.on { font-weight: bold; outline: 2px solid; }
  li .chips { margin: 0 0 .5rem; }
</style>
</head>
<body>
<header>
  <h1>Compass</h1>
  <form method="post" action="/logout"><button>Wyloguj</button></form>
</header>

<input id="q" type="search" placeholder="Szukaj… np. indeks" autocomplete="off" autofocus>
<div id="tagbar" class="chips"></div>
<div id="status" role="status"></div>
<ul id="list"></ul>

<section id="view" hidden>
  <div id="read">
    <h2 id="vt"></h2>
    <div id="vb"></div>
    <div id="vtags" class="chips"></div>
    <div id="ract">
      <button type="button" id="edit">Edytuj</button>
      <button type="button" id="del">Usuń</button>
    </div>
    <div id="dconfirm" hidden>
      <span>Na pewno usunąć? Tego nie da się cofnąć.</span>
      <button type="button" id="dyes">Tak, usuń</button>
      <button type="button" id="dno">Wróć</button>
    </div>
    <span id="derr"></span>
  </div>
  <form id="editform" hidden>
    <input id="et" maxlength="200" required>
    <textarea id="eb" rows="8" maxlength="20000"></textarea>
    <input id="etags" placeholder="Tagi (po przecinku)" autocomplete="off">
    <div id="esugg" class="chips"></div>
    <div id="eact">
      <button type="submit">Zapisz</button>
      <button type="button" id="ecancel">Anuluj</button>
    </div>
    <div id="confirm" hidden>
      <span>Na pewno nadpisać? Poprzednia wersja przepadnie.</span>
      <button type="button" id="eyes">Tak, nadpisz</button>
      <button type="button" id="eno">Wróć</button>
    </div>
    <span id="eerr"></span>
  </form>
</section>

<details id="addbox">
  <summary>Dodaj notatkę</summary>
  <form class="add" id="add">
    <input id="title" placeholder="Tytuł" maxlength="200" required>
    <textarea id="body" rows="6" placeholder="Treść" maxlength="20000"></textarea>
    <input id="tags" placeholder="Tagi (po przecinku)" autocomplete="off">
    <div id="sugg" class="chips"></div>
    <button>Zapisz</button>
    <span id="err"></span>
  </form>
</details>

<script>
const $ = (s) => document.querySelector(s);
let timer;
let seq = 0;

let current = null;
let allTags = [];
const selected = new Set();

const norm = (s) => s.toLowerCase().split(/\s+/).filter(Boolean).join(" ");
const parseTags = (v) => v.split(",").map((t) => t.trim()).filter(Boolean);

function chip(label, on, handler) {
  const b = document.createElement("button");
  b.type = "button";
  b.className = "chip" + (on ? " on" : "");
  b.textContent = label;
  b.addEventListener("click", handler);
  return b;
}

function toggle(name) {
  if (selected.has(name)) selected.delete(name); else selected.add(name);
  renderTagbar();
  load();
}

function renderTagbar() {
  $("#tagbar").replaceChildren(
    ...allTags.map((t) => chip("#" + t.name + " (" + t.count + ")", selected.has(t.name), () => toggle(t.name))),
  );
}

function appendTag(input, name) {
  const have = parseTags(input.value);
  if (have.some((t) => norm(t) === name)) return;
  input.value = have.concat(name).join(", ");
  input.focus();
}

function renderSuggestions() {
  for (const [input, box] of [["#tags", "#sugg"], ["#etags", "#esugg"]]) {
    $(box).replaceChildren(
      ...allTags.slice(0, 30).map((t) => chip(t.name, false, () => appendTag($(input), t.name))),
    );
  }
}

async function loadTags() {
  const r = await fetch("/api/tags");
  if (r.status === 401) { location.href = "/login"; return; }
  allTags = await r.json();
  const names = new Set(allTags.map((t) => t.name));
  for (const t of [...selected]) if (!names.has(t)) selected.delete(t);
  renderTagbar();
  renderSuggestions();
}

function tagChips(tags) {
  return tags.map((t) => chip("#" + t, selected.has(t), () => toggle(t)));
}

function show(n) {
  current = n;
  $("#vt").textContent = n.title;
  $("#vb").textContent = n.body;
  $("#vtags").replaceChildren(...tagChips(n.tags));
  $("#editform").hidden = true;
  $("#read").hidden = false;
  $("#view").hidden = false;
  askDelete(false);
  $("#derr").textContent = "";
}

function askDelete(on) {
  $("#dconfirm").hidden = !on;
  $("#ract").hidden = on;
}

function askConfirm(on) {
  $("#confirm").hidden = !on;
  $("#eact").hidden = on;
}

function render(notes) {
  const ul = $("#list");
  ul.replaceChildren();
  if (!notes.length) {
    const li = document.createElement("li");
    li.textContent = "Brak wyników";
    ul.append(li);
    return;
  }
  for (const n of notes) {
    const li = document.createElement("li");
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = n.title;
    const small = document.createElement("small");
    small.textContent = n.body.slice(0, 120);
    b.append(small);
    b.addEventListener("click", () => show(n));
    li.append(b);
    if (n.tags.length) {
      const row = document.createElement("div");
      row.className = "chips";
      row.append(...tagChips(n.tags));
      li.append(row);
    }
    ul.append(li);
  }
}

async function load() {
  const mine = ++seq;
  const params = new URLSearchParams({ q: $("#q").value });
  for (const t of selected) params.append("tag", t);
  const r = await fetch("/api/notes?" + params);
  if (r.status === 401) { location.href = "/login"; return; }
  const notes = await r.json();
  if (mine === seq) render(notes);
}

$("#q").addEventListener("input", () => {
  $("#status").textContent = "";
  clearTimeout(timer);
  timer = setTimeout(load, 100);
});

$("#add").addEventListener("submit", async (e) => {
  e.preventDefault();
  $("#err").textContent = "";
  const r = await fetch("/api/notes", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ title: $("#title").value, body: $("#body").value, tags: parseTags($("#tags").value) }),
  });
  if (r.status === 401) { location.href = "/login"; return; }
  if (!r.ok) { $("#err").textContent = "Nie udało się zapisać (tytuł 1–200 znaków)."; return; }
  const note = await r.json();
  $("#status").textContent = "";
  $("#add").reset();
  $("#q").value = "";
  selected.clear();
  await loadTags();
  await load();
  show(note);
});

$("#edit").addEventListener("click", () => {
  $("#et").value = current.title;
  $("#eb").value = current.body;
  $("#etags").value = current.tags.join(", ");
  $("#eerr").textContent = "";
  askConfirm(false);
  $("#read").hidden = true;
  $("#editform").hidden = false;
  $("#et").focus();
});

$("#ecancel").addEventListener("click", () => show(current));
$("#eno").addEventListener("click", () => askConfirm(false));

$("#editform").addEventListener("submit", (e) => {
  e.preventDefault();
  $("#eerr").textContent = "";
  askConfirm(true);
});

$("#eyes").addEventListener("click", async () => {
  const r = await fetch("/api/notes/" + current.id, {
    method: "PUT",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ title: $("#et").value, body: $("#eb").value, tags: parseTags($("#etags").value) }),
  });
  if (r.status === 401) { location.href = "/login"; return; }
  if (!r.ok) {
    $("#eerr").textContent = "Nie udało się zapisać (tytuł 1–200 znaków).";
    askConfirm(false);
    return;
  }
  const note = await r.json();
  await loadTags();
  await load();
  show(note);
});

$("#del").addEventListener("click", () => askDelete(true));
$("#dno").addEventListener("click", () => askDelete(false));

$("#dyes").addEventListener("click", async () => {
  const r = await fetch("/api/notes/" + current.id, { method: "DELETE" });
  if (r.status === 401) { location.href = "/login"; return; }
  if (r.status !== 204 && r.status !== 404) {
    $("#derr").textContent = "Nie udało się usunąć.";
    askDelete(false);
    return;
  }
  current = null;
  $("#view").hidden = true;
  await loadTags();
  await load();
  $("#status").textContent = "Notatka usunięta";
});

loadTags();
load();
</script>
</body>
</html>
"""
