"""The single notes page. Note content is only ever inserted via textContent."""

INDEX_HTML = """<!doctype html>
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
  #err, #eerr { color: crimson; }
  [hidden] { display: none !important; }
  #eact, #confirm { display: flex; gap: .5rem; align-items: center; }
  #editform { display: grid; gap: .5rem; }
</style>
</head>
<body>
<header>
  <h1>Compass</h1>
  <form method="post" action="/logout"><button>Wyloguj</button></form>
</header>

<input id="q" type="search" placeholder="Szukaj… np. indeks" autocomplete="off" autofocus>
<ul id="list"></ul>

<section id="view" hidden>
  <div id="read">
    <h2 id="vt"></h2>
    <div id="vb"></div>
    <button type="button" id="edit">Edytuj</button>
  </div>
  <form id="editform" hidden>
    <input id="et" maxlength="200" required>
    <textarea id="eb" rows="8" maxlength="20000"></textarea>
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
    <button>Zapisz</button>
    <span id="err"></span>
  </form>
</details>

<script>
const $ = (s) => document.querySelector(s);
let timer;
let seq = 0;

let current = null;

function show(n) {
  current = n;
  $("#vt").textContent = n.title;
  $("#vb").textContent = n.body;
  $("#editform").hidden = true;
  $("#read").hidden = false;
  $("#view").hidden = false;
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
    ul.append(li);
  }
}

async function load() {
  const mine = ++seq;
  const r = await fetch("/api/notes?q=" + encodeURIComponent($("#q").value));
  if (r.status === 401) { location.href = "/login"; return; }
  const notes = await r.json();
  if (mine === seq) render(notes);
}

$("#q").addEventListener("input", () => {
  clearTimeout(timer);
  timer = setTimeout(load, 100);
});

$("#add").addEventListener("submit", async (e) => {
  e.preventDefault();
  $("#err").textContent = "";
  const r = await fetch("/api/notes", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ title: $("#title").value, body: $("#body").value }),
  });
  if (r.status === 401) { location.href = "/login"; return; }
  if (!r.ok) { $("#err").textContent = "Nie udało się zapisać (tytuł 1–200 znaków)."; return; }
  const note = await r.json();
  $("#add").reset();
  $("#q").value = "";
  await load();
  show(note);
});

$("#edit").addEventListener("click", () => {
  $("#et").value = current.title;
  $("#eb").value = current.body;
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
    body: JSON.stringify({ title: $("#et").value, body: $("#eb").value }),
  });
  if (r.status === 401) { location.href = "/login"; return; }
  if (!r.ok) {
    $("#eerr").textContent = "Nie udało się zapisać (tytuł 1–200 znaków).";
    askConfirm(false);
    return;
  }
  const note = await r.json();
  await load();
  show(note);
});

load();
</script>
</body>
</html>
"""
