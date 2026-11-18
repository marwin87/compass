# Frontend style guide

Everything about building and styling the Compass UI. **Read this before touching anything in `src/compass/ui/`, and add to it whenever a UI decision is made** (a new pattern,
a pitfall, a token). Keep entries short and concrete.

## 1. Structure

The whole app UI is one server-rendered page, no build step and no framework.

| Where | What |
| --- | --- |
| `src/compass/ui/core.py` | `CORE_JS`: the helpers both pages share (`tr`, `$`, `h`, icons, `toast`, `api`, `sk`, `SORT_LABELS`, `categoryError`, `saveSettings`) and `inject()`, which fills the I18N and SETTINGS constants and `data-theme` on the server |
| `src/compass/settings.py` | the settings registry (`SPEC`: key, default, validator) stored in the `settings` table; `current()`, `update()` |
| `src/compass/ui/settings_page.py` | the Settings page (`/settings`): Appearance, Data, Shortcuts, AI features, About |
| `src/compass/ui/page.py` | `COMMON_CSS` (tokens, base, buttons, chips, forms, toast, login), `APP_CSS` (layout, sidebar, list, cards, panel, dialog, skeleton, responsive), `INDEX_HTML` (markup + one `<script>`), `render_index(lang)` |
| `src/compass/ui/reader.py` | the note reader: `READER_PURE_JS` (Markdown parser + syntax highlighter, no DOM, tested in Node), `READER_UI_JS` (DOM builder, reading mode, table of contents), `READER_CSS`. Embedded into `INDEX_HTML` at import time |
| `src/compass/ui/editor.py` | the Markdown helper of the note forms: `EDITOR_PURE_JS` (pure text-editing functions, tested in Node), `EDITOR_UI_JS` (toolbar, callout menu, Write/Preview tabs), `EDITOR_CSS`. Embedded into `INDEX_HTML` at import time |
| `src/compass/ai.py` | `status()`: the static check of the AI connection (configured? what is missing? do notes leave the machine?), served by `GET /api/ai/status`. The key (`OPENROUTER_API_KEY`) is read from the environment only, never a setting, never returned |
| `src/compass/ui/chatpanel.py` | the chat with the notes: `CHAT_JS` (`makeChat`, the panel in the detail column) and `CHAT_CSS`. Embedded into `INDEX_HTML` at import time (`/*CHAT_UI*/`) |
| `src/compass/ui/i18n.py` | `STRINGS["pl"]` and `STRINGS["en"]`, `pick_lang` |
| `src/compass/ui/login.py` | the login page (`render_login`); reuses `COMMON_CSS`, the tab icon and the language switch; its logo is the same as in the app (the compass icon drawn inline, name and `tagline`; `.tagline` and `.logo .dot svg` live in `COMMON_CSS` for that reason); the password field has an eye button (`.pwtoggle`, inline SVG, `aria-pressed`, labels `password_show`/`password_hide`) that shows and hides the typed password. The page loads no core script, so its icons are inline SVG (toggle them with `toggleAttribute("hidden")`: the `hidden` property does not exist on SVG elements) |
| `tests/ui/` | the UI tests (mirrors `src/compass/ui/`): `test_i18n.py` (key parity and usage guards), `test_page.py` (the notes page), `test_settings_page.py`, `test_login.py`, `test_reader.py` and `test_editor.py` (the pure JS, run in Node). Backend tests stay in `tests/` (one file per backend area). Helpers: `tests/ui/helpers.py` (`login_cookie`), `tests/ui/conftest.py` (`anon`) |

**Package layout.** `src/compass/` is the backend (`main`, `api`, `auth`, `notes`, `categories`, `tags`, `transfer`,
`settings`, `about`, `db`, `search`, `config`); `src/compass/ui/` is everything the browser receives (pages, CSS,
JavaScript, translations). The backend never builds HTML or CSS; `ui/` may import the backend only for plain data
(`settings` defaults in `core.inject`). New UI modules go into `ui/`.

The script section order in `ui/page.py`: i18n + helpers, text/highlight helpers, icons, toast, state and
server calls, skeleton, rendering, forms and the note panel, category management, import, wiring.
State lives in one `state` object; render functions rebuild their part of the DOM from it.

## 2. Hard rules

- **DOM calls only.** Build elements with `h(tag, props, ...kids)` and set text with `textContent`.
  Never `innerHTML`: note titles, bodies, tags and category names are user data.
- **No external requests.** No web fonts, CDNs or remote images. Icons are inline SVG (section 5), the
  font is a system stack (`Inter, Geist, system-ui, ...`). A test checks the page has no `http(s)://`
  (apart from the SVG namespace). The tab icon is `FAVICON_LINK` in `ui/page.py`: the logo as an inline SVG
  data URI, used by both the notes page and the login page. Change the logo there, not in a file.
- **Exactly one `</script>`** in the rendered page (the embedded I18N JSON must not end it early).
- **Every UI string is translated** (section 3). Never hard-code Polish or English text in the markup or JS.
- **Business logic stays on the server.** The page only renders and calls `/api/*`; search ranking,
  validation and category rules live in Python. The highlighting in JS is cosmetic.
- **No dead controls.** Do not add buttons for functions that do not exist (favorite, sync status,
  tag management). Notes are plain text; do not render Markdown unless that becomes a feature.
- **Same-origin, cookie session.** A 401 from `api()` redirects to `/login`.

## 3. Translations

- Strings are keys in `ui/i18n.py`, present in **both** languages. Markup uses `[[key]]` (filled on the
  server, HTML-escaped); JS uses `tr("key", {var})` or `T.key`. Placeholders look like `{count}` and
  must match between languages.
- Tests enforce: identical key sets, every key used by the page exists, every key is used somewhere,
  matching placeholders, no Polish text in the English page and vice versa.
- Keys read through a lookup table must appear as a quoted key in the script (the usage test looks for
  `"key"`). Existing tables: `IMPORT_ERRORS`, `FIELD_NAMES`, `CATEGORY_ERRORS`.
- Server error codes become messages through those tables (`import_err_*`, `field_*`,
  `category_err_*`). A new server error code needs a key in both languages; tests check this.
- Plurals use `Intl.PluralRules` with the `count` forms (pl: one/few/many/other).
- Language: cookie `lang`, else `Accept-Language`, default Polish. The PL/EN buttons set the cookie and reload.

## 4. Design tokens and look

Dark is the default theme; the light theme is `:root[data-theme=light]`. The choice is stored on the server
(setting `theme`) and put on `<html data-theme>` by the server, so there is no flash. Colors come from tokens, never from literals in rules
(exceptions: the note hero gradient and the wave art).

| Token | Use |
| --- | --- |
| `--bg` `--side` `--panel` `--raise` | page, sidebar, card surface, raised surface |
| `--line` `--line-strong` | subtle border, active border |
| `--accent` `--accent-light` `--accent-soft` `--grad` | primary blue/violet, soft fill, the one gradient |
| `--ink` `--muted` `--faint` | primary, secondary, helper text |
| `--ok` `--danger` `--danger-soft` | success, danger |
| `--shadow` `--glow` `--ease` | elevation, active glow, transition (`.18s ease-out`) |
| `--sk-a` `--sk-b` | skeleton base and shimmer highlight |

- **Radii:** 12 px buttons and inputs, 16 px cards and the search bar, 20 px panels and dialogs,
  999 px pills.
- **Type:** card title 15.5 px semibold, snippet 13.5 px, metadata 12 px, note title 29 px bold,
  note body 15.5 px with line-height 1.7. Section headings are 11 px uppercase with letter-spacing.
- **Gradient** only for emphasis: the primary button, active tag/filter, the note hero. Not on large
  surfaces. Avoid extra borders; prefer a surface tint (see `.chip.mini`).
- **Motion:** 150-220 ms, `ease-out`, subtle. Everything respects `prefers-reduced-motion` (one global rule).
- **Layout:** sidebar 250 px, list up to 455 px, detail takes the rest; list and detail scroll on their
  own, the page does not. At 900 px and below the sidebar is a slide-in menu and list/detail are
  separate views (`#app[data-view]`).

## 5. Components and patterns

- **Icons:** the `ICONS` map in the script, Lucide-style paths (24x24, stroke 2, round caps). Use
  `icon("name", size)` in JS or `<span class="ic" data-icon="name" data-size="16">` in markup. Add a new
  icon by adding its path data there; do not pull in a library.
- **Buttons:** `.btn` (+ `.primary` gradient, `.danger`, `.icon`), `.pill` for filters, `.chip` for tags
  (`.on` when active, `.mini` on cards). Icon-only buttons need `aria-label` and `title`.
- **Toast:** `toast(msg, kind, ms)`, kind `""`, `"ok"` or `"bad"`. Use it for results of actions (saved,
  deleted, import and export results, copy). Errors stay longer. Questions that need an answer
  (confirmations) are inline, not toasts.
- **Destructive actions** (delete, overwrite, import-replace) always ask for a second, explicit confirmation.
  Delete and overwrite confirm inline in the note panel; the import (it replaces all data) uses a modal
  popup (`#importdialog`: warning icon, title, text, file name, Cancel focused first, red "Replace
  everything"). Esc, Cancel and a click on the backdrop do nothing. Any `dialog[open]` blocks the global shortcuts.
- **Skeleton:** build placeholders from `sk(width, height, cls)`; variants are `skeletonCard` and
  `skeletonPanel`. Shown at once on the first load, and on later loads only if the answer takes more
  than 350 ms, so fast interactions never flicker. Real content fades in (`.reveal`). Placeholders are
  `aria-hidden`, the list gets `aria-busy`. Do not add spinners.
- **Errors:** a failed list load shows the message with a retry button; never leave a blank screen.
- **Note card (`.res`):** icon chosen by topic (`TOPICS`), title, date, one line of text (two while
  searching), category as plain accent text, tags in one row. Active card: `--line-strong` border and `--glow`.
- **Note panel:** `.card` with one continuous gradient in read mode (`:has(.panel[data-mode=read])`),
  hero with date, category, tags and the Copy / Edit / Delete icon buttons at the top right, text on the
  rounded `.sheet`. Edit, new and confirm modes use the plain panel.
- **Dialog:** native `<dialog>` with `showModal()` (Esc closes it, focus is trapped by the browser).
- **Keyboard:** `/` and Ctrl/Cmd+K focus search, `N` new note, Esc clears filters, Up/Down move through
  the notes from the search box or from anywhere outside a form. Shortcuts never fire inside inputs,
  textareas or selects, and never while the dialog is open.
- **Sorting:** the `#sort` select above the list (`SORT_LABELS`): default (newest first, or by relevance while
  searching), title A-Z / Z-A, oldest / newest first. A chosen order overrides relevance, is sent as `sort=` to
  `/api/notes` (server sorts before cutting to 50; titles ignore case and accents), is stored as the setting
  `sort` and is highlighted while active. New sort options need the API `Literal`, `SORTS` in
  `notes.py`, an `i18n` key and a test in `tests/test_sort.py`.
- **Hiding:** use the `hidden` attribute; a global `[hidden]{display:none!important}` exists because
  `display:flex/grid` on a class would otherwise override it.

## 6. Pitfalls (learned the hard way)

- Do not name a local variable `t` in code that calls the translation function; the function is `tr`.
- `.cat` styles the sidebar category buttons and is scoped to `.catlist`; `.badge.cat` is the card badge.
- In a flex column, give containers that use `overflow:hidden` a `flex:none` or they collapse to 0
  height (this hid the sidebar tags once).
- A 204 response has no body: parse JSON defensively (`.catch(() => null)`).
- Scroll-spy navigation (Settings): a section near the end of the page cannot be scrolled to the top, so a
  highlight computed only from the scroll position picks the wrong link after a click. A clicked link sets the
  highlight at once and keeps it (`navLock`) until the user scrolls by hand (wheel, touch, key, mouse down).
- Cards are re-created on every render, so state that must survive (focus, scroll) has to be restored
  explicitly (`scrollIntoView({block:"nearest"})` after keyboard selection).
- File inputs: clear `value` after reading so the same file can be chosen twice. Import replaces all data
  and therefore asks for confirmation first.

## 7. Verifying UI changes

`pytest` only checks markup and translations. For behavior and looks, run the page in headless Chromium
with a stubbed `window.fetch`:

1. Render `render_index(lang)` into a temp HTML file, inject a mock `fetch` before the main script and a
   test script after it that writes results into `<pre id="result">`.
2. Dump it with `chrome-headless-shell --no-sandbox --disable-gpu --virtual-time-budget=... --dump-dom`.
   Use `--screenshot` with `--window-size` for visuals (1333 px wide matches the reference design in
   `docs/prototypes/ui-change-screenshot.png`; also check about 390 px wide).
3. Check both languages and both themes. Poll for async results instead of fixed sleeps
   (`file.text()` and fetch mocks are asynchronous under virtual time).
4. Compare against the reference screenshot for layout and color, not just by eye on the code.

Also run `uv run ruff format . && uv run ruff check . && uv run mypy src tests && uv run pytest` and
`docker build -t compass:dev .` before handing over.

## 8. Note reader (Markdown) and reading mode

- **Notes are plain text in the database and stay so.** They are only *displayed* through the Markdown
  renderer; nothing is migrated or rewritten, and import/export/search see the original text. Edit mode
  shows the raw text with a one-line Markdown hint.
- **Backward compatibility:** a single line break is kept (`<br>`), blank lines separate paragraphs, so an
  old plain note looks the way it always did. `-`/`1.` lines become lists, `#` + space a heading, `---` a rule.
- **Safe by construction:** the parser (`mdParse`) produces an AST and `mdBlocksDom` builds DOM nodes. Raw HTML
  in a note is shown as text; links are limited to `http(s)`, `mailto:`, `/` and `#` (anything else, e.g.
  `javascript:`, is plain text); external links get `rel="noopener noreferrer"`; images are not loaded
  (that would be an external request).
- **Supported:** H1-H6, paragraphs, bold, italic, strikethrough, inline code, fenced code (with language),
  ordered/unordered/nested lists, blockquotes, links and bare URLs, GFM tables (alignment, `\|`), rules,
  callouts `> [!NOTE|INFO|TIP|WARNING|IMPORTANT|SUCCESS]` (`CAUTION` = warning). Callout labels are translated
  (`callout_*`).
- **Code blocks:** own tiny highlighter (`mdHighlight`: js/ts, python, sql, json, bash, yaml, css, html), language
  from the fence or guessed (`hlDetect`), label in the corner, Copy button with an in-place confirmation,
  horizontal scroll. Never highlight code over 30 000 characters. Add a language by adding to `HL_LANGS`.
- **Tables** live in `.tablewrap` (own horizontal scroll, never wider than the panel). **Contents** (`.toc`) is built
  from H2/H3 and shown only with 3 or more of them: collapsed above the text normally, open and sticky on the
  right in reading mode on wide screens; the current section is highlighted while scrolling (one rAF per burst).
- **Typography** is in `.md` (em-based so the reading font size scales it); colors use `--r-*` tokens, which also
  have a light variant. Do not add reading progress, word counts or reading-time estimates (decided against).
- **Reading mode** (`#app.reading`): hides sidebar, list, search and filters, centres the text at 680/760/880 px,
  keeps Copy/Edit/Delete and shows `#readbar` (smaller/larger text, width, exit). Esc leaves it; shortcuts and
  arrow navigation are off while it is active; editing leaves it. Size and width are the settings
  `reader_size` and `reader_width` (several clicks are saved as one request). `.card` uses `overflow:clip` (not `hidden`) so the sticky contents works.
- **List snippets** strip Markdown markers (`snippet()`); the note itself is never changed.
- **Testing:** `tests/ui/test_reader.py` runs the pure parser/highlighter in Node (skipped without Node). The DOM
  side is checked with the headless-Chromium method from section 7. Under virtual time `requestAnimationFrame`
  and smooth scrolling do not progress between sleeps: use instant scrolling and screenshots for those.

## 9. Settings page and the settings registry

- **Where things live:** `/settings` is a separate page with sections (left nav, a chip row on phones):
  Appearance, Categories, Tags, Load Data (AI), Keyboard shortcuts, AI features, Backup, Danger zone, About (one section per thing, named like its nav entry). **The danger zone is always the second-to-last
  section, right above About** (new sections go before it); destructive "clear everything" actions live only there. Theme and language are changed only there (one place, no duplicates); the notes page has just a
  Settings button in the sidebar footer; import and export are in Settings -> Backup, the category and tag managers in their own sections, clear-all in
  the danger zone
  (the notes page's "Zarzadzaj" links go to `/settings#categories` and `/settings#tags`). Quick add of a category stays in the note forms.
- **AI section:** on/off, connection (OpenRouter or Local), address (Local only), models (one per role and connection: the chat model `ai_model_openrouter` / `ai_model_local` and the embedding model `ai_embed_model_openrouter` / `ai_embed_model_local`; each field shows and saves the chosen connection's own; a new role is one entry in `MODEL_ROLES` in the Settings script, one key in `settings.SPEC` and one row, e.g. a vision model later); a status line from `GET /api/ai/status` says what is missing and whether notes leave the machine. Text settings save on `change` (trimmed) through the same `change()` helper. A secret is never a setting: it is read from the environment and never reaches `GET /api/settings`, the page or the export.
- **The basic rule for every AI component: it exists only while AI is enabled AND configured (`AI_READY`).** The server computes it from the same `ai.status` as `GET /api/ai/status` (switch on, and a key or address and model present) and injects `const AI_READY` next to `SETTINGS` (`core.inject`). Static markup (the logo badge, a panel, a button) carries the `data-ai` attribute and starts `hidden`; `setAiReady(AI_READY)` shows it after `fillIcons()`, and the Settings page calls `setAiReady(...)` again whenever the AI status changes, so a switch takes effect without a reload. Controls built in JS are created only `AI_READY ? ... : null` (never check `SETTINGS.ai_enabled` alone: that ignores a missing key or model). The Settings AI section itself is the exception: it is where AI gets configured, so it is always visible. New AI components must follow this and are covered by `test_ai_components_show_only_when_ai_is_enabled_and_configured`.
- **Blocking rule for AI work (setting `ai_block_page`, Settings -> Appearance, an `data-ai` row, off by default):** with it on, while an AI job runs the whole page is blurred and inactive except the one window where the AI works (the translation preview, the load-data review card). **Every AI job that takes noticeable time follows it**: call `aiBusy(() => theWindowElement)` (shared, `core.py`) when the job starts and `aiBusy(null)` when it ends, however it ends (done, failed, cancelled; use `finally`). Pass a function, not an element: the window may be re-created while the job runs. The veil (`.aiveil`, `backdrop-filter: blur`, `z-index: 50`, below toasts at 60) is one fixed layer with a hole cut out at the window's rectangle (`clip-path: polygon(evenodd, ...)`, refitted every frame while busy), so it needs no z-index tricks and works through any stacking context; the clip also lets clicks through inside the hole and stops them everywhere else. It heals itself: if the window is gone or hidden, the veil drops, so a lost job never leaves the page locked. Keyboard shortcuts check `aiBlocked()` (Tab can still reach blurred controls: `inert` cannot be put on the ancestors of the window). The user's own AI window stays fully usable, including its Cancel. Checked in headless Chromium (blur, hole, click blocking, release); do the same after changing it.
- **Logo badge:** the `AI` tag (`.logo .aitag`, `data-ai`) sits after "Compass" in the side panel and on the Settings page, following the rule above.
- **AI marker (variant A, violet to pink):** everything that is AI-related carries the same three marks: a gradient frame, the `spark` icon and the `AI` tag. **The tag is shown once per surface, not on every block**: a block opened from the note's AI strip (summary, translation) has the frame and the spark, and the strip's single tag (on the right) marks all of it. Tokens `--ai1`, `--ai2`, `--ai-soft` (same in both themes). Classes in `COMMON_CSS`: `.aiframe` (gradient border on a panel or `.scard`), `.aihd` (tinted header row with the icon, a title and the tag), `.aitag` (filled gradient pill; in JS `aiTag()`, in markup `<span class="aitag"><span class="ic" data-icon="spark" data-size="10"></span>AI</span>`), `.aibtn` (a pill button with a gradient border for an AI action, used in the note's AI strip, `.act` while its block is open). "AI" is the same in PL and EN, so it is not a translation key. A new AI control, panel or section must use these; do not invent another colour.
- **Note panel AI strip:** the AI actions (Summarize, Translate) are not toolbar icons: they are pill buttons (`.aibtn`, icon + label) in a strip (`.aistrip`) at the top of the sheet, shown only with `AI_READY`; the hero toolbar keeps only Reading mode, Copy, Edit and Delete. The strip's `AI` tag is on its right and is the only AI tag in the sheet. Each button toggles its own block (`.act` while open). New AI actions for a note go into this strip; with four or five of them, replace the buttons by one `AI` menu (the layout study is `docs/prototypes/ai-note-actions.html`, not tracked).
- **Translate (note panel):** the strip's Translate button; its label names the direction, `Translate PL→EN` or `EN→PL` (`translateLabel(target())`; `noteLang` in `core.py` guesses the note's language for the default direction). The client always sends the direction, `POST /api/notes/{id}/translate?to=en|pl`, and the model is not asked to detect anything. The translation **replaces the note** (it is a different text): the `.aiframe.aipad` block shows an `.aihd` header (spark, direction, swap button hidden while loading, Copy or Retry, Back) and the translated note in the reader layout; the strip button is a toggle. Loading is `.aithink`: a pulsing `spark` icon and the text (static under `prefers-reduced-motion`); an error is `.aierr` from `AI_ERRORS`. Edit and Delete drop it. It returns `{lang: to, text}` and saves nothing; a late answer is dropped (`tjob` counter). The preview passes `lang` in the reader context so callout titles (Warning, Tip...) come out in the language of the translation: `I18N.callouts` holds those labels (and `toc_title`) for both languages (`ctx.lang` empty = the interface language).
- **Load Data (Settings -> its own section under Tags, `#load`):** loading new data into Compass, as opposed to Backup, which restores an export. The section and its nav link are `data-ai hidden` (shown only while `AI_READY`; the scroll-spy skips hidden sections) and carry the AI marks. One button takes every file type (today `.docx`, `.txt`, `.md`; PDF, spreadsheets and images are to follow). The description and the `accept` of the file input name exactly the supported formats, so no control promises more than works (the server still decides by extension and answers `unsupported`); a new format is a parser in `src/compass/` (blocks like `docx.Block`) plus one line in `importer._blocks`, an error-message key if it has its own error code, and the formats in both descriptions. `#wordreview` is **not** `data-ai`: `setAiReady` would unhide it, and its visibility belongs to the review code. The file goes as the raw body to `POST /api/import/file?name=<file name>` (the extension picks the parser; an unknown one is `unsupported`), which saves nothing and answers with a **stream of JSON lines** (`importer.run`): `start` (part count, labels), then, mixed across parts (parts run side by side, each event has its part `index`): `note` the moment the model has finished writing one note (the model's answer is streamed from the provider and its JSON array is read item by item), `written` (`unmatched` = numbers/links in no note), `check` (`omitted` = what the model found missing, `unchecked`) or `error` (`code`, `detail` = the reason, e.g. `HTTP 401: ...`), then `done`. `?parts=0,2` runs only those parts again. The client (`runWord`) reads the stream and adds each proposal to the `#wordreview` card (`.aiframe`) **the moment its `note` arrives**, in file order whatever the arrival order (`addNote`); a part that is run again first drops its unsaved proposals (`dropRows`), so the user can review and save while the rest is still coming: `.aihd` header, `.wstatus` (progress), `.wcheck` (the check: model's list, numbers/links, unchecked parts, or "nothing missing" when finished), `.wfail` (one row per failed part with its reason and a Retry button), then one `.wnote` accordion per proposal (checkbox, title input and a chevron; inside: category field with a datalist of the existing categories, a comma-separated tags field, a `.wnew` line naming which of the suggested category/tags do not exist yet, and a large text area; only the first one open; all editable), a "Select all / Unselect all" toggle above the list, **a warning for a note whose title already exists** (the server flags it with `exists`, comparing titles ignoring case, accents and spaces; the row gets the `.wchip` "Already exists" and an explanation, and "Select all" skips it, while "Unselect all" clears everything; it is a warning, not a ban: the user may tick it by hand), Cancel/Close and "Save selected (n)". **Nothing is ticked by default**: the user goes through every proposal and ticks it (`.wnote.sel` = ticked, the only highlighted state; open and closed look the same); proposals that arrive later are unticked too. Saved proposals leave the list; the card closes when nothing is left and nothing failed. Cancel (or Close) aborts the request; the server stops making model calls. The model suggests the category and tags from the existing ones first (`importer.Vocab`; the code maps its answer onto existing names, case and accents ignored, and drops bad tags), and the user is the guard against near-duplicates: new names are announced in `.wnew`. Saving goes to `POST /api/notes/bulk` (all or none; the category is sent by name and created when missing). Errors before any model call (AI off, bad file, too large) are toasts through `WORD_ERRORS`. The existing JSON import (`#importdialog`, replaces everything) is a separate flow and stays untouched.
- **Summarize (note panel):** the strip's Summarize button. The summary **is added above the note** (it is an addition, the note stays readable below it): a `.aiframe.aisum` block with an `.aihd` header (spark, `Summary`, Copy, Refresh or Retry, a collapse chevron, a close button; no AI tag of its own) and the text rendered with the reader's Markdown (`mdBlocksDom`, headings shown as small section labels). Collapsing keeps the header only. `POST /api/notes/{id}/summarize` returns `{text}` and saves nothing: Markdown in the language of the note with a short summary and a key-points list (the heading words come from the model, in the note's language). **The summary is kept** (table `note_summaries`, one per note, `src/compass/summaries.py`; not searched, deleted with the note, part of the export and import as an optional `summary` field of the note): `summarize` saves the result (a new one replaces the old), `GET /api/notes/{id}/summary` returns it or `null`, `DELETE` removes it. `loadSummary()` runs when a note panel opens (and on Back from editing) and shows a kept summary **open by default** (only with `AI_READY`; with AI off the data stays and the block is hidden). It remembers a digest of the title and text it was written from, so after an edit it is shown with the `.stale` chip "Outdated" (still readable; Refresh writes a new one). The close button **deletes** a kept summary (label "Delete summary"; an unsaved loading or failed block is just dropped); collapsing is the chevron, and the strip's Summarize button is the same collapse/expand toggle, never a delete. The header wraps on narrow panels. Its state (`sum`, counter `sjob`) is separate from the translation's (`preview`, `tjob`): while the translation is shown the summary is hidden, and it comes back on Back; Edit, Delete and leaving the note drop the on-screen state of both (`dropAi`; the kept summary stays on the server). The translation is not kept. Errors use `SUMMARY_ERRORS` (`ai_err_failed_summary`: "Could not summarize"). Both blocks are the window of `aiBusy` (`.aisum`, `.aipad`).
- **Chat with the notes (`#chatbtn` inside the search bar, right of the shortcut hint, `data-ai hidden`; `ui/chatpanel.py`):** asking and searching are the same intent, so the entry sits in the search bar: an `.aibtn.askbtn` (gradient frame, soft violet glow and a small `AI` badge on its top right corner, which stays visible when only the icon is shown) with the `chat-compass` icon (the Compass needle inside a round speech bubble: chat + our logo; the AI frame and badge come from the button) and the label "Ask" / "Zapytaj" (icon only on phones, the label stays as `aria-label`). The panel's title is just "Chat". Do not call it "chat with notes" / "rozmowa z notatkami" (decided: too clumsy). The entry is global, not note-scoped, so it is not in the note's AI strip. It switches the detail column to `state.mode = "chat"` (`openChat()`); `renderDetail()` puts the one cached panel (`chat`, made by `makeChat` on first use) into a `.card.chatcard`, so a later `load()` or a trip to a source note never loses the conversation. The panel: an `.aihd` header (spark, title, a **custom dropdown** (`dropdown()` in `chatpanel.py`: a native `<select>` popup cannot have rounded corners; button + `role=listbox` menu with 16 px radius, 10 px rounded options, arrow keys, Enter, Esc, click outside) of saved conversations whose first option is "New chat", New chat (an icon button, so the header stays on one row), Rename (a pencil: the dropdown turns into a text field, Enter saves through `PATCH /api/chats/{id}`, Esc or leaving cancels; the first question names a conversation until then), Delete with an inline confirmation row, the single AI tag, and a close X like the summary's, which leaves the chat but keeps the panel and its conversation), `.chatlog` (scrolls; `role="log"`), the question box (a 3-line rounded `.chatbox` with the Send/Stop button inside it, growing with the text up to 220 px; Enter sends, Shift+Enter a new line) and a one-line privacy hint. A conversation is created on the **first question**, so no empty ones are saved. `POST /api/chats/{id}/ask` answers with a **stream of JSON lines** (`chat.answer`): `indexing` (changed notes being embedded, at most 20 per question), `excerpts`, `delta` (a piece of the answer, rendered as Markdown with the reader's `mdParse` and `mdBlocksDom`, at most once per frame), then `done` with the final `text` and the cited `sources`, or `error` (`code`). **Citations:** the model cites excerpts as `[n]`; the server renumbers them after the **notes** (one source per note, in order of first mention; an invented number is removed), so `[2]` in the text is chip 2 under the message (`.chatsrc`, `.srcchip`). A chip opens the note (`openSource`: it puts the title in the search box so the note is in the limited list); a note deleted later stays as a struck-through chip (`deleted`). A question and its answer are saved **together, once the answer is complete**: an error shows `.aierr` with Retry and saves nothing, Stop (the Send button while an answer runs) aborts, drops both bubbles and puts the question back into the box. The panel is the `aiBusy` window (`el`). Errors come from `CHAT_ERRORS`. Settings -> AI has the embedding model field and, only when AI is ready and one is set, the "Chat index" row (`#row-ai-index`: how many notes are indexed and a Build index button streaming `POST /api/ai/index`, and a Clear index button, `DELETE /api/ai/index`, which asks inline first (derived data, but rebuilding costs model calls); both buttons are disabled while an index is being built; this is maintenance, not an AI job the user waits in front of, so it **never uses `aiBusy`** and the page stays usable); without an embedding model the chat still works with keyword search only. **Backup:** saved conversations are part of the export and import as an optional top-level `conversations` field (absent when there are none, so older files are unchanged): each has `title`, `created_at` and `messages` (`role`, `text`, `created_at`, `sources` of `{note, title}`, where `note` is the cited note's `id` in the same file, or null when it was deleted). Import replaces the conversations one to one and points the sources at the notes' new ids; a malformed one refuses the whole file (`invalid_conversation`). The vector index is derived data and is not exported: after an import it is empty, and the next question or Build index fills it. Checked in headless Chromium in both languages and themes and at 390 px.
- **Server-side settings, not `localStorage`:** preferences are rows in the `settings` table, read through
  `settings.current()` and written with `PUT /api/settings` (a partial update, validated as a whole, 422
  `invalid_setting` with the key). The server embeds them as `const SETTINGS` and puts the theme on `<html>`,
  so pages need no extra request. The language is the exception: it stays the `lang` cookie (the login page and
  the first render need it before any setting is available).
- **Adding a setting:** 1) a key in `settings.SPEC` with a default and a validator, 2) a control on the Settings
  page (and use of `SETTINGS.<key>` where it matters), 3) an i18n label and description in both languages,
  4) a test in `tests/test_settings.py`. A test fails when a registry key has no control on the page. Secrets
  (API keys and the like) must never be returned by `GET /api/settings`: make them write-only when the first one
  is added, and prefer environment variables in Docker.
- **Controls:** every control applies at once, saves through `saveSettings(patch)` (it toasts on failure) and goes
  back to its previous value when the save fails (`change()` on the Settings page). No Save button.
- **Pages share code through `ui/core.py`:** never copy a helper into a second page. New shared helpers go to
  `CORE_JS`; page-specific code stays in its module. Both pages are embedded at import time so the i18n tests see
  all of their strings.
- **Data section rules:** import and clear-all always ask in a popup (safe button focused first); results and
  errors are toasts; after any data operation the category list and the About counts are reloaded.

## 10. The Markdown editor of the note forms

- **The note stays a plain textarea.** The toolbar only edits its text; saving sends exactly `textarea.value`.
  No library and no WYSIWYG: a rich editor would keep its own document model and could silently rewrite
  Markdown it does not know (our callouts), and it would break the no-external-request, DOM-only rules.
- **Pure functions, one replacement each:** every button is `ed*(text, selStart, selEnd, ...)` returning
  `{from, to, insert, selFrom, selTo}` (replace `text[from:to]`, then select `[selFrom, selTo)` of the new text).
  They are unit-tested in Node (`tests/ui/test_editor.py`), including that the reader's parser understands what they
  insert. Add a button = a pure function + a test + an icon + an i18n label.
- **Toggling, not just inserting:** bold/italic/strike/code unwrap when already wrapped, headings/lists/quotes
  remove their marker when every selected line has it, switching bullets and numbers replaces the marker, and
  italic never unwraps the `*` of a `**bold**`.
- **Applying edits:** `applyEdit` uses `document.execCommand("insertText")` so Ctrl+Z keeps working (it is
  deprecated but universal), with `setRangeText` as the fallback. Toolbar buttons prevent `mousedown` so the
  textarea keeps its focus and selection.
- **Preview** (the Write/Preview tabs) uses the reader's own `mdParse` and `mdBlocksDom`, so it always looks like
  the saved note; raw HTML is shown as text there too.
- **Shortcuts:** Ctrl/Cmd+B and Ctrl/Cmd+I inside the textarea only. Escape closes the callout menu before it
  reaches the global handler (which would otherwise clear the filters and leave the form).
- **Do not write a literal URL scheme in page code** (the link helper builds it from two parts): a test checks
  that the page contains no external URL.

## 11. Tag management (Settings -> Tags)

- **Same pattern as the category manager:** inline rows, a row turns into an edit field or a confirmation, errors in
  a `role="alert"` line, results as toasts, and after every change the list and the About counts reload.
- **Rename onto an existing name is a merge, and it asks first** (`tags_merge_ask` shows both counts); the
  confirmation is decided on the client from the loaded list, and the server reports `merged` anyway. Deleting a tag
  also asks, with the number of notes. Neither is blocked (unlike categories): a note may have no tags.
- **Server rules** live in `tags.py`: one transaction, names cleaned like every tag (lowercase, spaces collapsed,
  1-30 characters, no commas), `INSERT OR IGNORE` so a note never gets a tag twice, and **every touched note is
  re-indexed** because tags are part of the search index. Tag names go into the URL with `encodeURIComponent`
  (a name may contain `/`, `#`, `?`, `%`, accents), and the route is `{name:path}`.
- **Long lists:** search (case and accent insensitive, a leading `#` is ignored), sort (most used / alphabetical)
  and "show more" in steps of 25. Bulk selection is not built.
- **Management lists** (categories, tags; `.mgrlist`): a search box above, rows kept compact (one line, icon-only
  `rowBtn` actions with `aria-label`/`title`, two columns when there is room), the list scrolls inside its card
  (`max-height`) so a long list never makes the page long, and rows that need room (rename field, confirmation,
  the fixed default category) get the `wide` class and span both columns. At most 300 rows are drawn; the hint
  line (`list_capped`) says so and the search narrows the rest. Do not add a "show more" button to these lists.

## 12. End-to-end tests (`tests/e2e/`, local only)

- **Run:** `uv run pytest -m e2e` (`--headed --slowmo 300` to watch). The `e2e` marker is added to everything under
  `tests/e2e/` and the default `addopts` deselect it, so a plain `pytest` and CI never need a browser.
- **Server and state:** the `server` fixture runs `uvicorn` on a free port with a temporary database and an explicit
  test password; the autouse `clean` fixture empties the data (`DELETE /api/data`) and restores the default settings
  before every test; every test gets a fresh browser context (own cookies). Use the `app` fixture for a logged-in
  page, `page` for an anonymous one, `api` for preparing or checking data over HTTP.
- **Rules (from `CLAUDE.md`):** locate by role, label, placeholder or text (`get_by_role`, `get_by_label`,
  `get_by_placeholder`, `get_by_text`); `get_by_test_id` only when those are ambiguous; never `wait_for_timeout`
  (use web-first `expect(...)` and `wait_for_url`/`wait_for`); each test is independent, builds its own data with
  `unique(...)` titles and does not rely on another test.
- **Texts come from the app:** `tests/e2e/pages.py` exposes `T = STRINGS["pl"]` (the browser runs with the Polish
  locale), so a renamed string breaks the test at its source instead of silently. Put repeated steps in `pages.py`;
  keep assertions in the tests.
- **Browser context:** reduced motion (no transitions to wait for), a 1280x800 viewport, clipboard permissions.
  Mobile tests build their own context with a phone viewport.
- **Failures** leave a screenshot and a trace in `test-results/` (git-ignored).
- **Not here:** pixel comparison, other browsers, a CI job.
