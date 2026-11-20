// ---- the reader: Markdown blocks -> DOM (DOM calls only, never HTML strings)
const CALLOUTS = {
    info: ["callout_info", "info"],
    tip: ["callout_tip", "bulb"],
    warning: ["callout_warning", "alert"],
    important: ["callout_important", "alert-circle"],
    success: ["callout_success", "check-circle"],
    note: ["callout_note", "file"],
};

function mdInlineDom(nodes, tk) {
    return nodes
        .map((n) => {
            if (n.t === "text") return hlNodes(n.v, tk);
            if (n.t === "br") return h("br");
            if (n.t === "code") return h("code", {class: "icode"}, n.v);
            if (n.t === "strong") return h("strong", {}, mdInlineDom(n.c, tk));
            if (n.t === "em") return h("em", {}, mdInlineDom(n.c, tk));
            if (n.t === "del") return h("del", {}, mdInlineDom(n.c, tk));
            if (n.t === "link")
                return h(
                    "a",
                    n.href.startsWith("#") || n.href.startsWith("/")
                        ? {href: n.href}
                        : {href: n.href, target: "_blank", rel: "noopener noreferrer"},
                    mdInlineDom(n.c, tk),
                );
            return null;
        })
        .flat();
}

function copyCode(btn, text) {
    navigator.clipboard.writeText(text).then(
        () => {
            const label = btn.querySelector(".lbl"),
                old = label.textContent;
            label.textContent = tr("code_copied");
            btn.classList.add("done");
            setTimeout(() => {
                label.textContent = old;
                btn.classList.remove("done");
            }, 1500);
        },
        () => toast(tr("copy_failed"), "bad"),
    );
}

function codeBlockDom(b) {
    const lang = hlLang(b.lang) || (b.lang ? "" : hlDetect(b.text));
    const code = h("code", {});
    for (const [cls, text] of mdHighlight(b.text, lang)) code.append(cls ? h("span", {class: cls}, text) : text);
    const copy = h(
        "button",
        {type: "button", class: "copybtn", "aria-label": tr("code_copy"), onclick: () => copyCode(copy, b.text)},
        icon("copy", 14),
        h("span", {class: "lbl"}, tr("copy")),
    );
    return h(
        "div",
        {class: "codeblock"},
        h(
            "div",
            {class: "codehead"},
            h("span", {class: "codelang"}, HL_LABELS[lang] || b.lang || tr("code_plain")),
            copy,
        ),
        h("pre", {tabindex: 0}, code),
    );
}

function mdBlocksDom(blocks, ctx) {
    return blocks.map((b) => {
        const inl = (c) => mdInlineDom(c, ctx.tk);
        if (b.t === "p") return h("p", {}, inl(b.c));
        if (b.t === "h") {
            const id =
                "sec-" +
                ctx.heads.length +
                "-" +
                (fold(mdPlain(b.c))
                    .replace(/[^a-z0-9]+/g, "-")
                    .replace(/^-|-$/g, "")
                    .slice(0, 40) || "x");
            ctx.heads.push({id, level: b.level, text: mdPlain(b.c)});
            return h("h" + b.level, {id}, inl(b.c));
        }
        if (b.t === "code") return codeBlockDom(b);
        if (b.t === "hr") return h("hr");
        if (b.t === "quote") return h("blockquote", {}, mdBlocksDom(b.c, ctx));
        if (b.t === "callout") {
            const [label, ic] = CALLOUTS[b.kind];
            return h(
                "div",
                {class: "callout " + b.kind, role: "note"},
                h(
                    "div",
                    {class: "calltitle"},
                    icon(ic, 16),
                    h("span", {}, ctx.lang && I18N.callouts[ctx.lang] ? I18N.callouts[ctx.lang][label] : tr(label)),
                ),
                h("div", {class: "callbody"}, mdBlocksDom(b.c, ctx)),
            );
        }
        if (b.t === "ul" || b.t === "ol") {
            const list = h(b.t, b.t === "ol" && b.start !== 1 ? {start: b.start} : {});
            for (const it of b.items) list.append(h("li", {}, mdBlocksDom(it.c, ctx)));
            return list;
        }
        if (b.t === "table") {
            const cell = (tag, c, k) => h(tag, b.align[k] ? {style: "text-align:" + b.align[k]} : {}, inl(c));
            return h(
                "div",
                {class: "tablewrap"},
                h(
                    "table",
                    {},
                    h(
                        "thead",
                        {},
                        h(
                            "tr",
                            {},
                            b.head.map((c, k) => cell("th", c, k)),
                        ),
                    ),
                    h(
                        "tbody",
                        {},
                        b.rows.map((r) =>
                            h(
                                "tr",
                                {},
                                r.map((c, k) => cell("td", c, k)),
                            ),
                        ),
                    ),
                ),
            );
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
    clearTimeout(readerSave); // several clicks on A+ become one request
    readerSave = setTimeout(() => saveSettings({reader_size: READER.size, reader_width: READER.width}), 400);
}

let tocWatch = null;

function watchToc(root) {
    // highlight the section being read; cheap, one rAF per scroll burst
    if (tocWatch) tocWatch();
    tocWatch = null;
    const links = [...root.querySelectorAll(".toc a")],
        scroller = $("#detail");
    if (!links.length) return;
    const heads = links.map((a) => root.querySelector("#" + a.dataset.id));
    let queued = false;
    const update = () => {
        queued = false;
        const top = scroller.getBoundingClientRect().top + 96;
        let cur = 0;
        heads.forEach((el, i) => {
            if (el && el.getBoundingClientRect().top <= top) cur = i;
        });
        links.forEach((a, i) => a.classList.toggle("on", i === cur));
    };
    const onScroll = () => {
        if (!queued) {
            queued = true;
            requestAnimationFrame(update);
        }
    };
    scroller.addEventListener("scroll", onScroll, {passive: true});
    tocWatch = () => scroller.removeEventListener("scroll", onScroll);
    update();
}

function readerBody(note, tk, lang) {
    // the rendered note: optional contents + the article; lang names callouts in a translation
    const ctx = {tk, heads: [], lang};
    const article = h("article", {class: "md"}, mdBlocksDom(mdParse(note.body), ctx));
    const tocHeads = ctx.heads.filter((x) => x.level === 2 || x.level === 3);
    const wrap = h("div", {class: "mdwrap"});
    if (tocHeads.length >= 3) {
        // short notes get no contents
        const tocTitle = lang && I18N.callouts[lang] ? I18N.callouts[lang].toc_title : tr("toc_title"); // a translation names it in its own language
        const nav = h(
            "nav",
            {"aria-label": tocTitle},
            tocHeads.map((x) =>
                h(
                    "a",
                    {
                        href: "#" + x.id,
                        "data-id": x.id,
                        class: "l" + x.level,
                        onclick: (e) => {
                            e.preventDefault();
                            document.getElementById(x.id).scrollIntoView({
                                behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth",
                                block: "start",
                            });
                        },
                    },
                    x.text,
                ),
            ),
        );
        wrap.append(h("details", {class: "toc"}, h("summary", {}, icon("list", 15), tocTitle), nav));
    }
    wrap.append(article);
    return wrap;
}

function syncReadButton() {
    // the book icon in the note header is a toggle: lit while reading
    document.querySelectorAll(".readtoggle").forEach((/** @type {HTMLElement} */ b) => {
        b.classList.toggle("on", state.reading);
        b.setAttribute("aria-pressed", state.reading ? "true" : "false");
        b.title = tr(state.reading ? "reading_exit" : "reading_mode");
    });
}

const toggleReading = () => (state.reading ? exitReading() : enterReading());

function enterReading() {
    state.reading = true;
    setView("detail");
    openMenu(false);
    $("#app").classList.add("reading");
    syncReadButton();
    document.querySelectorAll(".toc").forEach((/** @type {HTMLDetailsElement} */ d) => {
        d.open = true;
    });
    $("#detail").scrollTo({top: 0});
}

function exitReading() {
    if (!state.reading) return;
    state.reading = false;
    $("#app").classList.remove("reading");
    syncReadButton();
    document.querySelectorAll(".toc").forEach((/** @type {HTMLDetailsElement} */ d) => {
        d.open = false;
    });
}
