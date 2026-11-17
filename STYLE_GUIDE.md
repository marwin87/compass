# Frontend style guide

Everything about building and styling the Compass UI. **Read this before touching `src/compass/page.py`,
`src/compass/i18n.py` or the login page, and add to it whenever a UI decision is made** (a new pattern,
a pitfall, a token). Keep entries short and concrete.

## 1. Structure

The whole app UI is one server-rendered page, no build step and no framework.

| Where | What |
| --- | --- |
| `src/compass/page.py` | `COMMON_CSS` (tokens, base, buttons, chips, forms, toast, login), `APP_CSS` (layout, sidebar, list, cards, panel, dialog, skeleton, responsive), `INDEX_HTML` (markup + one `<script>`), `render_index(lang)` |
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

Dark is the default theme; the light theme is `:root[data-theme=light]`. The choice is stored in
`localStorage` (wrapped in try/catch). Colors come from tokens, never from literals in rules
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
- **Hiding:** use the `hidden` attribute; a global `[hidden]{display:none!important}` exists because
  `display:flex/grid` on a class would otherwise override it.

## 6. Pitfalls (learned the hard way)

- Do not name a local variable `t` in code that calls the translation function; the function is `tr`.
- `.cat` styles the sidebar category buttons and is scoped to `.catlist`; `.badge.cat` is the card badge.
- In a flex column, give containers that use `overflow:hidden` a `flex:none` or they collapse to 0
  height (this hid the sidebar tags once).
- A 204 response has no body: parse JSON defensively (`.catch(() => null)`).
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
   `prototypes/ui-change-screenshot.png`; also check about 390 px wide).
3. Check both languages and both themes. Poll for async results instead of fixed sleeps
   (`file.text()` and fetch mocks are asynchronous under virtual time).
4. Compare against the reference screenshot for layout and color, not just by eye on the code.

Also run `uv run ruff format . && uv run ruff check . && uv run mypy src tests && uv run pytest` and
`docker build -t compass:dev .` before handing over.
