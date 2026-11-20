// ---- the editor around a note's textarea: toolbar (Write) and a rendered preview (Preview)
function applyEdit(ta, e) {
  // keeps the undo history where the browser allows it
  ta.focus();
  ta.setSelectionRange(e.from, e.to);
  let done = false;
  try {
    done = document.execCommand("insertText", false, e.insert);
  } catch (x) {
    /* falls back below */
  }
  if (!done) ta.setRangeText(e.insert, e.from, e.to, "end");
  ta.setSelectionRange(e.selFrom, e.selTo);
  ta.dispatchEvent(new Event("input", { bubbles: true }));
}
function markdownEditor(ta) {
  const text = () => tr("editor_ph_text");
  const labels = () => ({ col1: tr("editor_col1"), col2: tr("editor_col2"), cell: tr("editor_cell") });
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
  const toolbar = h("div", { class: "edtools", role: "toolbar", "aria-label": tr("label_body") });
  for (const [ic, key, short, fn] of TOOLS) {
    toolbar.append(
      h(
        "button",
        {
          type: "button",
          class: "edbtn",
          "data-tool": ic,
          "aria-label": tr(key),
          title: tr(key) + (short ? " (" + mod + short + ")" : ""),
          onmousedown: (e) => e.preventDefault(),
          onclick: () => run(fn),
        },
        icon(ic, 16),
      ),
    ); // mousedown must not take the selection away from the textarea
  }
  // callouts: one button, a small menu of the six kinds
  const menu = h("div", { class: "edmenu", role: "menu", hidden: true });
  const closeMenu = () => {
    menu.hidden = true;
    document.removeEventListener("mousedown", outside);
  };
  const outside = (e) => {
    if (!menu.contains(e.target) && !calloutBtn.contains(e.target)) closeMenu();
  };
  for (const [kind, [label, ic]] of Object.entries(CALLOUTS)) {
    menu.append(
      h(
        "button",
        {
          type: "button",
          role: "menuitem",
          class: "edmenuitem " + kind,
          onmousedown: (e) => e.preventDefault(),
          onclick: () => {
            closeMenu();
            run((t, a, b) => edCallout(t, a, b, kind, text()));
          },
        },
        icon(ic, 15),
        tr(label),
      ),
    );
  }
  const calloutBtn = h(
    "button",
    {
      type: "button",
      class: "edbtn",
      "data-tool": "callout",
      "aria-label": tr("editor_callout"),
      title: tr("editor_callout"),
      "aria-haspopup": "menu",
      onmousedown: (e) => e.preventDefault(),
      onclick: () => {
        if (menu.hidden) {
          menu.hidden = false;
          document.addEventListener("mousedown", outside);
        } else closeMenu();
      },
    },
    icon("info", 16),
  );
  toolbar.append(h("span", { class: "edpop" }, calloutBtn, menu)); // the menu opens right under its button
  menu.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      e.stopPropagation();
      closeMenu();
      ta.focus();
    }
  });

  // Write / Preview
  const preview = h("div", { class: "edpreview", hidden: true });
  const tabs = h("div", { class: "edtabs", role: "tablist" });
  const tabWrite = h(
    "button",
    { type: "button", role: "tab", class: "edtab on", "aria-selected": "true" },
    tr("editor_write"),
  );
  const tabPreview = h(
    "button",
    { type: "button", role: "tab", class: "edtab", "aria-selected": "false" },
    tr("editor_preview"),
  );
  function show(previewOn) {
    if (previewOn) {
      const value = ta.value;
      preview.style.minHeight = ta.offsetHeight + "px";
      preview.replaceChildren(
        value.trim()
          ? h("article", { class: "md" }, mdBlocksDom(mdParse(value), { tk: [], heads: [] }))
          : h("div", { class: "muted" }, tr("editor_empty_preview")),
      );
    } else closeMenu();
    ta.hidden = previewOn;
    preview.hidden = !previewOn;
    toolbar.hidden = previewOn;
    tabWrite.classList.toggle("on", !previewOn);
    tabPreview.classList.toggle("on", previewOn);
    tabWrite.setAttribute("aria-selected", String(!previewOn));
    tabPreview.setAttribute("aria-selected", String(previewOn));
    if (!previewOn) ta.focus();
  }
  tabWrite.addEventListener("click", () => show(false));
  tabPreview.addEventListener("click", () => show(true));
  tabs.append(tabWrite, tabPreview);

  ta.addEventListener("keydown", (e) => {
    // Ctrl/Cmd+B and +I
    if (!(e.metaKey || e.ctrlKey) || e.shiftKey || e.altKey) return;
    const tool = { b: TOOLS[0][3], i: TOOLS[1][3] }[e.key.toLowerCase()];
    if (tool) {
      e.preventDefault();
      run(tool);
    }
  });
  return { el: h("div", { class: "edwrap" }, h("div", { class: "edbar" }, tabs, toolbar), ta, preview), show };
}
