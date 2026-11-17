# Frontend style guide

Everything about building and styling the Compass UI. **Read this before touching `src/compass/page.py`,
`src/compass/i18n.py` or the login page, and add to it whenever a UI decision is made** (a new pattern,
a pitfall, a token). Keep entries short and concrete.

## 1. Structure

The whole app UI is one server-rendered page, no build step and no framework.

| Where | What |
| --- | --- |
| `src/compass/core.py` | `CORE_JS`: the helpers both pages share (`tr`, `$`, `h`, icons, `toast`, `api`, `sk`, `SORT_LABELS`, `categoryError`, `saveSettings`) and `inject()`, which fills the I18N and SETTINGS constants and `data-theme` on the server |
| `src/compass/settings.py` | the settings registry (`SPEC`: key, default, validator) stored in the `settings` table; `current()`, `update()` |
| `src/compass/settings_page.py` | the Settings page (`/settings`): Appearance, Data, Shortcuts, About |
| `src/compass/page.py` | `COMMON_CSS` (tokens, base, buttons, chips, forms, toast, login), `APP_CSS` (layout, sidebar, list, cards, panel, dialog, skeleton, responsive), `INDEX_HTML` (markup + one `<script>`), `render_index(lang)` |
| `src/compass/reader.py` | the note reader: `READER_PURE_JS` (Markdown parser + syntax highlighter, no DOM, tested in Node), `READER_UI_JS` (DOM builder, reading mode, table of contents), `READER_CSS`. Embedded into `INDEX_HTML` at import time |
| `src/compass/editor.py` | the Markdown helper of the note forms: `EDITOR_PURE_JS` (pure text-editing functions, tested in Node), `EDITOR_UI_JS` (toolbar, callout menu, Write/Preview tabs), `EDITOR_CSS`. Embedded into `INDEX_HTML` at import time |
| `src/compass/i18n.py` | `STRINGS["pl"]` and `STRINGS["en"]`, `pick_lang` |
| `src/compass/auth.py` | login page; reuses `COMMON_CSS` only |
| `tests/test_i18n.py` | page smoke tests and i18n guards |

The script section order in `page.py`: i18n + helpers, text/highlight helpers, icons, toast, state and
server calls, skeleton, rendering, forms and the note panel, category management, import, wiring.
State lives in one `state` object; render functions rebuild their part of the DOM from it.

## 2. Hard rules

- **DOM calls only.** Build elements with `h(tag, props, ...kids)` and set text with `textContent`.
  Never `innerHTML`: note titles, bodies, tags and category names are user data.
- **No external requests.** No web fonts, CDNs or remote images. Icons are inline SVG (section 5), the
  font is a system stack (`Inter, Geist, system-ui, ...`). A test checks the page has no `http(s)://`
  (apart from the SVG namespace). The tab icon is `FAVICON_LINK` in `page.py`: the logo as an inline SVG
  data URI, used by both the notes page and the login page. Change the logo there, not in a file.
- **Exactly one `</script>`** in the rendered page (the embedded I18N JSON must not end it early).
- **Every UI string is translated** (section 3). Never hard-code Polish or English text in the markup or JS.
- **Business logic stays on the server.** The page only renders and calls `/api/*`; search ranking,
  validation and category rules live in Python. The highlighting in JS is cosmetic.
- **No dead controls.** Do not add buttons for functions that do not exist (favorite, sync status,
  tag management). Notes are plain text; do not render Markdown unless that becomes a feature.
- **Same-origin, cookie session.** A 401 from `api()` redirects to `/login`.

## 3. Translations

- Strings are keys in `i18n.py`, present in **both** languages. Markup uses `[[key]]` (filled on the
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
- **Testing:** `tests/test_reader.py` runs the pure parser/highlighter in Node (skipped without Node). The DOM
  side is checked with the headless-Chromium method from section 7. Under virtual time `requestAnimationFrame`
  and smooth scrolling do not progress between sleeps: use instant scrolling and screenshots for those.

## 9. Settings page and the settings registry

- **Where things live:** `/settings` is a separate page with sections (left nav, a chip row on phones):
  Appearance, Categories, Tags, Backup, Keyboard shortcuts, Danger zone, About (one section per thing, named like its nav entry). **The danger zone is always the second-to-last
  section, right above About** (new sections go before it); destructive "clear everything" actions live only there. Theme and language are changed only there (one place, no duplicates); the notes page has just a
  Settings button in the sidebar footer; import and export are in Settings -> Backup, the category and tag managers in their own sections, clear-all in
  the danger zone
  (the notes page's "Zarzadzaj" links go to `/settings#categories` and `/settings#tags`). Quick add of a category stays in the note forms.
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
- **Pages share code through `core.py`:** never copy a helper into a second page. New shared helpers go to
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
  They are unit-tested in Node (`tests/test_editor.py`), including that the reader's parser understands what they
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
