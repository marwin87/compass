// --- the Settings page: each control applies at once, saves, and goes back when the save fails
function segmented(options, value, onPick) {
    const buttons = options.map(([v, ...label]) =>
        h("button", {type: "button", class: "segbtn", "data-v": String(v), onclick: () => onPick(v)}, label),
    );
    const set = (val) =>
        buttons.forEach((b) => {
            const on = b.dataset.v === String(val);
            b.classList.toggle("on", on);
            b.setAttribute("aria-pressed", on ? "true" : "false");
        });
    set(value);
    return {el: h("div", {class: "seg", role: "group"}, buttons), set};
}

// Change one setting: show it, save it, and undo it when the server refuses.
async function change(key, value, show) {
    const before = SETTINGS[key];
    if (value === before) return;
    show(value);
    if (await saveSettings({[key]: value})) toast(tr("settings_saved"), "ok", 1200);
    else show(before);
}

// Appearance
const themeSeg = segmented(
    [
        ["dark", icon("moon", 15), tr("theme_dark")],
        ["light", icon("sun", 15), tr("theme_light")],
    ],
    SETTINGS.theme,
    (v) =>
        change("theme", v, (x) => {
            applyTheme(x);
            themeSeg.set(x);
        }),
);
$("#ctl-theme").append(themeSeg.el);
document.addEventListener("themechange", (/** @type {CustomEvent} */ e) => themeSeg.set(e.detail)); // the T key changed it

const langSeg = segmented(
    [
        ["en", "EN"],
        ["pl", "PL"],
    ],
    LANG,
    (v) => {
        if (v === LANG) return;
        document.cookie = "lang=" + v + "; path=/; max-age=31536000; SameSite=Lax";
        location.reload();
    },
);
$("#ctl-lang").append(langSeg.el);

const sizeVal = h("span", {class: "stepval"});
const showSize = (n) => {
    sizeVal.textContent = n + " px";
    $("#size-minus").disabled = n <= READ_SIZES[0];
    $("#size-plus").disabled = n >= READ_SIZES[1];
};
const stepSize = (d) =>
    change("reader_size", Math.min(READ_SIZES[1], Math.max(READ_SIZES[0], SETTINGS.reader_size + d)), showSize);
$("#ctl-size").append(
    h(
        "button",
        {
            type: "button",
            class: "btn",
            id: "size-minus",
            "aria-label": tr("font_smaller"),
            title: tr("font_smaller"),
            onclick: () => stepSize(-1),
        },
        "A−",
    ),
    sizeVal,
    h(
        "button",
        {
            type: "button",
            class: "btn",
            id: "size-plus",
            "aria-label": tr("font_larger"),
            title: tr("font_larger"),
            onclick: () => stepSize(1),
        },
        "A+",
    ),
);
showSize(SETTINGS.reader_size);

const WIDTH_LABELS = ["width_narrow", "width_medium", "width_wide"];
const widthSeg = segmented(
    WIDTH_LABELS.map((key, i) => [i, tr(key)]),
    SETTINGS.reader_width,
    (v) => change("reader_width", v, (x) => widthSeg.set(x)),
);
$("#ctl-width").append(widthSeg.el);

const sortSel = h(
    "select",
    {class: "sselect", "aria-label": tr("set_sort")},
    Object.entries(SORT_LABELS).map(([value, key]) => h("option", {value}, tr(key))),
);
sortSel.value = SETTINGS.sort;
sortSel.addEventListener("change", () =>
    change("sort", sortSel.value, (x) => {
        sortSel.value = x;
    }),
);
$("#ctl-sort").append(sortSel);
const aiBlock = segmented(
    [
        [true, tr("ai_on")],
        [false, tr("ai_off")],
    ],
    SETTINGS.ai_block_page,
    (v) => change("ai_block_page", v, (x) => aiBlock.set(x)),
);
$("#ctl-ai-block").append(aiBlock.el);
const related = segmented(
    [
        [true, tr("ai_on")],
        [false, tr("ai_off")],
    ],
    SETTINGS.show_related,
    (v) => change("show_related", v, (x) => related.set(x)),
);
$("#ctl-related").append(related.el);
const trashDays = segmented(
    [
        [7, tr("trash_n_days", {n: 7})],
        [30, tr("trash_n_days", {n: 30})],
        [90, tr("trash_n_days", {n: 90})],
        [0, tr("trash_never")],
    ],
    SETTINGS.trash_days,
    (v) => change("trash_days", v, (x) => trashDays.set(x)),
);
$("#ctl-trash-days").append(trashDays.el);

// AI: the switch, the connection and where it points; the key itself lives in the server environment only
const aiOn = segmented(
    [
        [true, tr("ai_on")],
        [false, tr("ai_off")],
    ],
    SETTINGS.ai_enabled,
    (v) => change("ai_enabled", v, (x) => aiOn.set(x)).then(loadAiStatus),
);
$("#ctl-ai-on").append(aiOn.el);
// Each connection keeps its own model: the model field shows and saves the one of the chosen connection
// One model per role (chat, embeddings, vision; another role = one more entry here, in SPEC and in the HTML row)
const MODEL_ROLES = [
    ["ai_model_", "#ctl-ai-model", "ai_model_ph"],
    ["ai_embed_model_", "#ctl-ai-embed", "ai_embed_ph"],
    ["ai_vision_model_", "#ctl-ai-vision", "ai_vision_ph"],
];
const aiText = (keyOf, ph) => {
    const input = h("input", {
        class: "sinput",
        maxlength: "200",
        autocomplete: "off",
        placeholder: ph,
        "aria-label": ph,
    });
    input.value = SETTINGS[keyOf()];
    input.addEventListener("change", () => {
        const key = keyOf();
        change(key, input.value.trim(), (x) => {
            if (keyOf() === key) input.value = x;
        }).then(loadAiStatus);
    });
    return input;
};
const aiAddr = aiText(() => "ai_address", "localhost:11434/v1");
const modelInputs = MODEL_ROLES.map(([prefix, slot, ph]) => {
    const input = aiText(() => prefix + SETTINGS.ai_connection, tr(ph));
    $(slot).append(input);
    return [prefix, input];
});
const showAiConn = (conn) => {
    $("#row-ai-addr").hidden = conn !== "local";
    for (const [prefix, input] of modelInputs) input.value = SETTINGS[prefix + conn];
};
const aiConn = segmented(
    [
        ["openrouter", "OpenRouter"],
        ["local", tr("ai_local")],
    ],
    SETTINGS.ai_connection,
    (v) =>
        change("ai_connection", v, (x) => {
            aiConn.set(x);
            showAiConn(x);
        }).then(loadAiStatus),
);
$("#ctl-ai-conn").append(aiConn.el);
$("#ctl-ai-addr").append(aiAddr);
showAiConn(SETTINGS.ai_connection);
// The chat's index (embeddings): changed notes are added when a question is asked; this builds everything at once on request, because it costs model calls. Maintenance, not an AI job the user waits in front of: it does not block the page (no aiBusy)
const indexBtn = h("button", {type: "button", class: "btn", onclick: () => buildIndex()}, tr("index_build"));
const clearBtn = h("button", {type: "button", class: "btn", onclick: () => askClear(true)}, tr("index_clear"));
const clearAsk = h(
    "span",
    {hidden: true, style: "display:inline-flex;gap:8px;align-items:center;flex-wrap:wrap"},
    h("span", {class: "sdesc"}, tr("index_clear_ask")),
    h("button", {type: "button", class: "btn danger", onclick: () => clearIndex()}, tr("yes_delete")),
    h("button", {type: "button", class: "btn", onclick: () => askClear(false)}, tr("back")),
);
const askClear = (on) => {
    indexBtn.hidden = clearBtn.hidden = on;
    clearAsk.hidden = !on;
};
$("#ctl-ai-index").append(indexBtn, clearBtn, clearAsk);

async function clearIndex() {
    askClear(false);
    try {
        const r = await api("/api/ai/index", {method: "DELETE"});
        if (r.status !== 204) throw new Error("clear");
        toast(tr("index_cleared"), "ok");
    } catch (e) {
        if (e.message !== "not authenticated") toast(tr("index_clear_failed"), "bad", 5000);
    }
    loadIndexStatus();
}

async function loadIndexStatus() {
    try {
        const r = await api("/api/ai/index");
        if (r.ok) $("#ai-index-status").textContent = tr("index_status", await r.json());
    } catch (e) {
        /* only a hint */
    }
}

async function buildIndex() {
    indexBtn.disabled = clearBtn.disabled = true;
    let finished = false;
    try {
        const resp = await api("/api/ai/index", {method: "POST"});
        if (!resp.ok) {
            toast(tr("index_failed"), "bad", 5000);
            return;
        }
        const reader = resp.body.getReader(),
            decoder = new TextDecoder();
        let buffer = "";
        for (; ;) {
            const {value, done} = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, {stream: true});
            let nl;
            while ((nl = buffer.indexOf("\n")) >= 0) {
                const line = buffer.slice(0, nl);
                buffer = buffer.slice(nl + 1);
                if (!line) continue;
                const e = JSON.parse(line);
                if (e.type === "progress") indexBtn.textContent = tr("index_building", {done: e.done, total: e.total});
                else if (e.type === "error") {
                    toast(tr("index_failed"), "bad", 5000);
                    return;
                } else if (e.type === "done") finished = true;
            }
        }
        if (finished) toast(tr("index_done"), "ok");
        else toast(tr("index_failed"), "bad", 5000);
    } catch (e) {
        if (e.message !== "not authenticated") toast(tr("index_failed"), "bad", 5000);
    } finally {
        indexBtn.disabled = clearBtn.disabled = false;
        indexBtn.textContent = tr("index_build");
        loadIndexStatus();
    }
}

const MISSING_LABELS = {key: tr("ai_missing_key"), address: tr("ai_missing_address"), model: tr("ai_missing_model")};

async function loadAiStatus() {
    let d;
    try {
        const r = await api("/api/ai/status");
        if (!r.ok) throw new Error("ai");
        d = await r.json();
    } catch (e) {
        if (e.message !== "not authenticated") $("#ai-status").textContent = tr("ai_status_failed");
        return;
    }
    setAiReady(d.enabled && d.configured); // the logo badge follows the switch at once
    $("#row-ai-index").hidden = !(d.enabled && d.configured && d.embeddings);
    if (!$("#row-ai-index").hidden) loadIndexStatus();
    const where = tr(d.leaves_machine ? "ai_leaves" : "ai_stays");
    const state = d.configured
        ? tr(d.enabled ? "ai_ready" : "ai_idle")
        : tr("ai_missing", {items: d.missing.map((m) => MISSING_LABELS[m]).join(", ")});
    $("#ai-status").replaceChildren(
        h("span", {class: "aistate " + (d.configured ? "ok" : "bad")}, state),
        h("br"),
        where,
    );
}

loadAiStatus();

// Keyboard shortcuts
$("#shortcutlist").append(...shortcutRows());

// About
const humanSize = (n) =>
    n < 1024 ? n + " B" : n < 1048576 ? (n / 1024).toFixed(1) + " KB" : (n / 1048576).toFixed(1) + " MB";

async function loadAbout() {
    const card = $("#aboutcard");
    card.replaceChildren(...[0, 1, 2].map(() => h("div", {class: "sk-row"}, sk("30%", 14), sk("20%", 14))));
    let d;
    try {
        const r = await api("/api/about");
        if (!r.ok) throw new Error("about");
        d = await r.json();
    } catch (e) {
        if (e.message === "not authenticated") return;
        card.replaceChildren(
            h(
                "div",
                {class: "aboutfail"},
                h("span", {}, tr("about_failed")),
                h("button", {type: "button", class: "btn", onclick: loadAbout}, tr("retry")),
            ),
        );
        return;
    }
    const row = (key, value) => h("div", {}, h("dt", {}, tr(key)), h("dd", {}, String(value)));
    card.replaceChildren(
        h(
            "dl",
            {class: "dl"},
            row("about_version", d.version),
            row("about_notes", d.notes),
            row("about_categories", d.categories),
            row("about_tags", d.tags),
            row("about_db_size", humanSize(d.db_size_bytes)),
            row("about_db_path", d.db_path),
        ),
    );
}

loadAbout();

// Data: the category manager (inline), export, import (confirmed in a popup), clearing everything
let categories = [];
const catLabel = (c) => (c.default ? tr("category_default") : c.name);
const manage = {editing: null, deleting: null};
const setCatMsg = (text) => {
    $("#catmsg").textContent = text;
};

async function loadCategories() {
    try {
        const r = await api("/api/categories");
        if (!r.ok) throw new Error("categories");
        categories = await r.json();
    } catch (e) {
        if (e.message !== "not authenticated") setCatMsg(tr("category_err_failed"));
        return;
    }
    renderManage();
}

const refreshData = () =>
    Promise.all([loadCategories(), loadAbout(), typeof loadTags === "function" ? loadTags() : null]); // counts change after every data operation
async function categoryCall(path, method, body) {
    const r = await api(path, body === undefined ? {method} : json(method, body));
    const data = (await r.json().catch(() => null)) || {}; // 204 has no body
    return {r, detail: data.detail};
}

const plainText = (s) =>
    s
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .replace(/ł/g, "l")
        .toLowerCase();
const rowBtn = (name, label, onclick, kind = "") =>
    h("button", {type: "button", class: "rowbtn " + kind, "aria-label": label, title: label, onclick}, icon(name, 15));

function renderManage() {
    const q = plainText($("#catsearch").value.trim());
    const list = categories.filter((c) => !q || plainText(catLabel(c)).includes(q));
    if (!list.length) {
        $("#catrows").replaceChildren(
            h("li", {class: "catrow wide"}, h("span", {class: "muted"}, tr("categories_none_match"))),
        );
        return;
    }
    $("#catrows").replaceChildren(
        ...list.map((c) => {
            const li = h("li", {class: "catrow"});
            if (c.default) {
                li.className = "catrow wide";
                li.append(
                    h("span", {class: "name"}, catLabel(c)),
                    h("span", {class: "n"}, c.count),
                    h("span", {class: "muted small"}, tr("manage_default_note")),
                );
            } else if (manage.editing === c.id) {
                li.className = "catrow wide";
                const input = h("input", {value: c.name, maxlength: 60, "aria-label": tr("manage_rename")});
                const save = async () => {
                    const {r, detail} = await categoryCall("/api/categories/" + c.id, "PUT", {name: input.value});
                    if (r.ok) {
                        manage.editing = null;
                        setCatMsg("");
                        await refreshData();
                    } else if (r.status === 404) {
                        manage.editing = null;
                        await refreshData();
                    } else setCatMsg(categoryError(detail));
                };
                input.addEventListener("keydown", (e) => {
                    if (e.key === "Enter") {
                        e.preventDefault();
                        save();
                    }
                });
                li.append(
                    input,
                    h("button", {type: "button", class: "btn primary", onclick: save}, tr("save")),
                    h(
                        "button",
                        {
                            type: "button",
                            class: "btn",
                            onclick: () => {
                                manage.editing = null;
                                setCatMsg("");
                                renderManage();
                            },
                        },
                        tr("cancel"),
                    ),
                );
                setTimeout(() => input.focus());
            } else if (manage.deleting === c.id) {
                li.className = "catrow wide";
                const remove = async () => {
                    const {r, detail} = await categoryCall("/api/categories/" + c.id, "DELETE");
                    manage.deleting = null;
                    if (r.status === 204 || r.status === 404) {
                        setCatMsg("");
                        await refreshData();
                    } // already gone is fine
                    else {
                        setCatMsg(categoryError(detail));
                        renderManage();
                    }
                };
                li.append(
                    h("span", {class: "name"}, tr("manage_confirm_delete", {name: c.name})),
                    h("button", {type: "button", class: "btn danger", onclick: remove}, tr("yes_delete")),
                    h(
                        "button",
                        {
                            type: "button",
                            class: "btn",
                            onclick: () => {
                                manage.deleting = null;
                                renderManage();
                            },
                        },
                        tr("back"),
                    ),
                );
            } else {
                li.append(
                    h("span", {class: "name", title: c.name}, c.name),
                    h("span", {class: "n"}, c.count),
                    rowBtn("pencil", tr("manage_rename"), () => {
                        manage.editing = c.id;
                        manage.deleting = null;
                        setCatMsg("");
                        renderManage();
                    }),
                    rowBtn(
                        "trash",
                        tr("delete"),
                        () => {
                            manage.deleting = c.id;
                            manage.editing = null;
                            setCatMsg("");
                            renderManage();
                        },
                        "danger",
                    ),
                );
            }
            return li;
        }),
    );
}

async function addCategory() {
    const input = $("#catnew");
    const {r, detail} = await categoryCall("/api/categories", "POST", {name: input.value});
    if (r.status === 201) {
        input.value = "";
        setCatMsg("");
        await refreshData();
        input.focus();
    } else setCatMsg(categoryError(detail)); // here an existing name is an error (the note forms just select it)
}

// Import: the server validates the whole file and answers with a code we translate
const IMPORT_ERRORS = {
    not_json: "import_err_not_json",
    not_an_export: "import_err_not_an_export",
    invalid_file: "import_err_invalid_file",
    count_mismatch: "import_err_count_mismatch",
    invalid_note: "import_err_invalid_note",
    invalid_conversation: "import_err_invalid_conversation",
    file_too_large: "import_err_file_too_large",
};
const FIELD_NAMES = {
    title: "field_title",
    body: "field_body",
    tags: "field_tags",
    created_at: "field_created_at",
    category: "field_category",
    note: "field_note",
    summary: "field_summary",
    role: "field_role",
    text: "field_text",
    messages: "field_messages",
    sources: "field_sources",
    conversation: "field_conversation",
    message: "field_message",
};

function importError(detail) {
    const d = detail && typeof detail === "object" ? detail : {};
    const key = IMPORT_ERRORS[d.code];
    if (!key) return tr("import_err_failed");
    const field = FIELD_NAMES[d.field] ? tr(FIELD_NAMES[d.field]) : "";
    return tr(key, {
        expected: d.expected ?? "?",
        actual: d.actual ?? "?",
        index: d.index ?? "?",
        field,
        mb: d.limit_mb ?? "?",
    });
}

async function importFile(file) {
    const show = (text, ok) => toast(text, ok ? "ok" : "bad", ok ? 3500 : 6000);
    let r;
    try {
        r = await api("/api/import", {
            method: "POST",
            headers: {"content-type": "application/json"},
            body: await file.text(),
        });
    } catch (e) {
        if (e.message !== "not authenticated") show(tr("import_err_failed"), false);
        return;
    }
    const body = await r.json().catch(() => ({}));
    if (!r.ok) {
        show(importError(body.detail), false);
        return;
    }
    show(tr("import_done", {n: body.imported}), true);
    await refreshData();
}

// Import from Word (AI): the model writes the notes part by part. Proposals appear as each part is ready,
// so they can be reviewed and saved while the rest is still coming; a failed part says why and can be run again.
const WORD_ERRORS = {
    not_docx: "word_err_not_docx",
    not_text: "word_err_not_text",
    unsupported: "word_err_unsupported",
    not_image: "word_err_not_image",
    not_pdf: "word_err_not_pdf",
    too_many_images: "word_err_too_many_images",
    encrypted: "word_err_encrypted",
    no_vision: "word_err_no_vision",
    empty: "word_err_empty",
    too_large: "word_err_too_large",
    file_too_large: "import_err_file_too_large",
    not_enabled: "ai_err_not_enabled",
    not_configured: "ai_err_not_configured",
    timeout: "ai_err_timeout",
};
const PART_ERRORS = {timeout: "ai_err_timeout"};
const wordError = (d) => tr(WORD_ERRORS[d && d.code] || "word_err_failed", {mb: (d && d.limit_mb) ?? "?"});
const partWhy = (e) => tr(PART_ERRORS[e.code] || "word_err_part") + (e.detail ? " (" + e.detail + ")" : "");
let rv = null; // the review that is open (one at a time)
function closeReview() {
    aiBusy(null);
    if (rv) rv.abort.abort(); // stops the stream; the server makes no further model calls
    rv = null;
    $("#wordreview").hidden = true;
    $("#wordreview").replaceChildren();
}

function newReview(file) {
    const r = {
        file,
        abort: new AbortController(),
        rows: [],
        failed: new Map(),
        omitted: [],
        unmatched: new Set(),
        unchecked: [],
        total: 0,
        todo: 0,
        done: 0,
        written: 0,
        produced: 0,
        labels: [],
        running: false,
        first: true,
    };
    r.status = h("div", {class: "wstatus"});
    r.check = h("div", {class: "wcheck"});
    r.fail = h("div", {class: "wfail"});
    r.hint = h("p", {class: "wordhint muted"}, tr("word_review_hint"));
    r.all = h("button", {type: "button", class: "btn", onclick: () => toggleAll(r)});
    r.tools = h("div", {class: "wtools"}, r.hint, r.all);
    r.list = h("ul", {class: "wlist"});
    r.close = h("button", {type: "button", class: "btn", onclick: closeReview});
    r.save = h("button", {type: "button", class: "btn primary", onclick: () => saveSelected(r)});
    $("#wordreview").replaceChildren(
        h("div", {class: "aihd"}, icon("spark", 16), h("span", {class: "grow"}, tr("word_review_h")), aiTag()),
        r.status,
        r.check,
        r.fail,
        r.tools,
        r.list,
        h("div", {class: "wbar"}, r.close, r.save),
        h(
            "datalist",
            {id: "wordcats"},
            categories.filter((c) => !c.default).map((c) => h("option", {value: c.name})),
        ),
    );
    $("#wordreview").hidden = false;
    return r;
}

function renderReview(r) {
    const summary = tr("word_summary", {n: r.produced});
    r.status.replaceChildren(
        r.running
            ? h(
                "span",
                {class: "aithink inline"},
                icon("spark", 14),
                !r.total || (!r.produced && r.written < r.todo)
                    ? tr("word_thinking")
                    : tr("word_progress", {done: r.done, todo: r.todo}) +
                    " " +
                    summary +
                    (r.written >= r.todo && r.done < r.todo ? " " + tr("word_checking") : ""),
            )
            : h("span", {class: "aistate ok"}, summary),
    );
    const check = [];
    if (r.omitted.length)
        check.push(
            h("div", {}, tr("word_check_missing")),
            h(
                "ul",
                {},
                r.omitted.map((m) => h("li", {}, m)),
            ),
        );
    if (r.unmatched.size) check.push(h("div", {}, tr("word_check_tokens", {items: [...r.unmatched].join(", ")})));
    if (r.unchecked.length)
        check.push(h("div", {}, tr("word_unchecked", {parts: r.unchecked.map((i) => i + 1).join(", ")})));
    if (!check.length && !r.running && !r.failed.size && r.produced)
        check.push(h("div", {class: "aistate ok"}, tr("word_check_ok")));
    r.check.replaceChildren(...check);
    r.fail.replaceChildren(
        ...[...r.failed].map(([i, e]) =>
            h(
                "div",
                {class: "wfailrow"},
                h(
                    "span",
                    {class: "aistate bad"},
                    tr("word_part_failed", {n: i + 1, total: r.total, label: r.labels[i] || "", why: partWhy(e)}),
                ),
                h(
                    "button",
                    {
                        type: "button",
                        class: "btn",
                        title: tr("word_retry_title"),
                        disabled: r.running,
                        onclick: () => runWord(r, [i]),
                    },
                    tr("word_retry"),
                ),
            ),
        ),
    );
    r.rows.forEach((x) => x.li.classList.toggle("sel", x.on.checked));
    const n = r.rows.filter((x) => x.on.checked).length;
    const free = r.rows.filter((x) => !x.dup); // "select all" leaves the notes that already exist alone
    r.all.textContent = tr(free.length && free.every((x) => x.on.checked) ? "word_unselect_all" : "word_select_all");
    r.all.disabled = !free.length && !n;
    r.save.textContent = tr("word_save", {n});
    r.save.disabled = !n;
    r.tools.hidden = !r.rows.length;
    r.close.textContent = tr(r.running ? "cancel" : "word_close");
}

// Nothing is selected for the user: every proposal has to be looked at and ticked. This is the shortcut for the rest.
function toggleAll(r) {
    const free = r.rows.filter((x) => !x.dup);
    const on = !(free.length && free.every((x) => x.on.checked));
    (on ? free : r.rows).forEach((x) => {
        x.on.checked = on;
    }); // unselecting clears everything, also a duplicate ticked by hand
    renderReview(r);
}

const splitTags = (text) =>
    text
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean);

// Which of the suggested names do not exist yet (the user's guard against a pile of near-duplicates)
function newNames(category, tagText) {
    const known = (names, v) => names.some((x) => plainText(x) === plainText(v));
    const c = category.trim();
    const newCat =
        c &&
        !known(
            categories.filter((x) => !x.default).map((x) => x.name),
            c,
        )
            ? tr("word_new_category", {name: c})
            : "";
    const fresh = splitTags(tagText).filter(
        (t) =>
            !known(
                tagList.map((x) => x.name),
                t,
            ),
    );
    return [newCat, fresh.length ? tr("word_new_tags", {items: fresh.join(", ")}) : ""].filter(Boolean).join(" · ");
}

// A proposal joins the list the moment the model has written it, in the order of the file (parts arrive mixed)
function addNote(r, part, n) {
    const on = h("input", {type: "checkbox", "aria-label": tr("word_field_include")});
    const title = h("input", {type: "text", maxlength: "200", "aria-label": tr("word_field_title")});
    const body = h("textarea", {"aria-label": tr("word_field_body"), maxlength: "20000"});
    title.value = n.title;
    body.value = n.body;
    const cat = h("input", {type: "text", maxlength: "40", autocomplete: "off", placeholder: tr("category_default")});
    cat.setAttribute("list", "wordcats"); // `list` is read-only as a property
    cat.value = n.category || "";
    const tags = h("input", {type: "text", autocomplete: "off"});
    tags.value = n.tags.join(", ");
    const hint = h("p", {class: "wnew muted"});
    const sync = () => {
        hint.textContent = newNames(cat.value, tags.value);
    };
    cat.addEventListener("input", sync);
    tags.addEventListener("input", sync);
    sync();
    const meta = h(
        "div",
        {class: "wmeta"},
        h("label", {class: "wlabel"}, tr("label_category"), cat),
        h("label", {class: "wlabel"}, tr("label_tags"), tags),
    );
    const bodyBox = h(
        "div",
        {class: "wbody"},
        n.exists ? h("p", {class: "wdup"}, tr("word_exists_hint")) : null,
        meta,
        hint,
        body,
    );
    const toggle = rowBtn("chevron-down", tr("word_toggle"), () => open(bodyBox.hidden));
    const li = h(
        "li",
        {class: "wnote" + (n.exists ? " dup" : "")},
        h("div", {class: "whead"}, on, title, n.exists ? h("span", {class: "wchip"}, tr("word_exists")) : null, toggle),
        bodyBox,
    );
    const open = (yes) => {
        bodyBox.hidden = !yes;
        li.classList.toggle("open", yes);
        toggle.setAttribute("aria-expanded", yes ? "true" : "false");
    };
    open(r.first); // the first proposal is open so the user sees what one holds
    r.first = false;
    on.addEventListener("change", () => renderReview(r));
    const row = {part, on, title, body, cat, tags, li, dup: !!n.exists};
    const after = r.rows.find((x) => x.part > part);
    if (after) {
        r.list.insertBefore(li, after.li);
        r.rows.splice(r.rows.indexOf(after), 0, row);
    } else {
        r.list.append(li);
        r.rows.push(row);
    }
    r.produced++;
}

// A part that is run again replaces its unsaved proposals
function dropRows(r, part) {
    const gone = r.rows.filter((x) => x.part === part);
    gone.forEach((x) => x.li.remove());
    r.rows = r.rows.filter((x) => x.part !== part);
    r.produced -= gone.length;
    r.unchecked = r.unchecked.filter((i) => i !== part);
}

// One event of the stream (see importer.run); true when it was the last one
function wordEvent(r, e) {
    if (e.type === "start") {
        r.total = e.total;
        r.labels = e.labels;
        r.todo = e.parts.length;
    } else if (e.type === "note") addNote(r, e.index, e.note);
    else if (e.type === "written") {
        r.written++;
        e.unmatched.forEach((t) => r.unmatched.add(t));
        if (!e.count) r.done++;
    } else if (e.type === "check") {
        r.done++;
        r.omitted.push(...e.omitted);
        if (e.unchecked) r.unchecked.push(e.index);
    } else if (e.type === "error") {
        r.done++;
        r.written++;
        r.failed.set(e.index, e);
    }
    renderReview(r);
    return e.type === "done";
}

async function runWord(r, only) {
    if (only)
        only.forEach((i) => {
            r.failed.delete(i);
            dropRows(r, i);
        });
    r.running = true;
    r.done = 0;
    r.written = 0;
    r.todo = only ? only.length : 0;
    renderReview(r);
    aiBusy(() => $("#wordreview"));
    let finished = false;
    try {
        const resp = await api(
            "/api/import/file?name=" + encodeURIComponent(r.file.name) + (only ? "&parts=" + only.join(",") : ""),
            {method: "POST", body: await r.file.arrayBuffer(), signal: r.abort.signal},
        );
        if (!resp.ok) {
            const body = await resp.json().catch(() => ({}));
            toast(wordError(body.detail), "bad", 6000);
            if (rv === r && !r.rows.length && !r.failed.size) closeReview();
            else if (rv === r) {
                r.running = false;
                renderReview(r);
            }
            return;
        }
        const reader = resp.body.getReader(),
            decoder = new TextDecoder();
        let buffer = "";
        for (; ;) {
            const {value, done} = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, {stream: true});
            let nl;
            while ((nl = buffer.indexOf("\n")) >= 0) {
                const line = buffer.slice(0, nl);
                buffer = buffer.slice(nl + 1);
                if (line && wordEvent(r, JSON.parse(line))) finished = true;
            }
        }
    } catch (e) {
        if (e.name === "AbortError" || e.message === "not authenticated") return;
    } finally {
        aiBusy(null); // the job is over, however it ended
    }
    if (rv !== r) return;
    r.running = false;
    if (!finished) toast(tr("word_err_cut"), "bad", 6000);
    renderReview(r);
    if (finished && !r.produced && !r.failed.size) {
        closeReview();
        toast(tr("word_err_empty"), "bad", 6000);
    }
}

async function saveSelected(r) {
    const chosen = r.rows.filter((x) => x.on.checked);
    r.save.disabled = true;
    try {
        const res = await api(
            "/api/notes/bulk",
            json("POST", {
                notes: chosen.map((x) => ({
                    title: x.title.value.trim(),
                    body: x.body.value,
                    tags: splitTags(x.tags.value),
                    category: x.cat.value.trim() || null,
                })),
            }),
        );
        if (!res.ok) {
            toast(tr("word_err_save"), "bad", 6000);
            renderReview(r);
            return;
        }
        toast(tr("word_saved", {n: (await res.json()).created}), "ok", 3500);
        chosen.forEach((x) => x.li.remove()); // saved ones leave the list; the rest keeps coming and stays editable
        r.rows = r.rows.filter((x) => !chosen.includes(x));
        await refreshData();
        if (rv === r && !r.running && !r.rows.length && !r.failed.size) closeReview();
        else renderReview(r);
    } catch (e) {
        if (e.message !== "not authenticated") {
            toast(tr("word_err_save"), "bad", 6000);
            renderReview(r);
        }
    }
}

$("#wordbtn").addEventListener("click", () => $("#wordfile").click());
$("#wordfile").addEventListener("change", (e) => {
    const file = e.target.files[0];
    e.target.value = "";
    if (!file) return;
    closeReview();
    rv = newReview(file);
    runWord(rv, null);
});

let pending = null;
$("#import").addEventListener("click", () => $("#importfile").click());
$("#importfile").addEventListener("change", (e) => {
    const file = e.target.files[0];
    e.target.value = ""; // so choosing the same file again fires another change
    if (!file) return;
    pending = file; // importing replaces everything, so ask first, in a popup
    $("#importfilename").textContent = file.name;
    $("#importdialog").showModal();
    $("#importno").focus(); // the safe choice has the focus
});
$("#importyes").addEventListener("click", async () => {
    const file = pending;
    pending = null;
    $("#importdialog").close();
    if (file) await importFile(file);
});
$("#importno").addEventListener("click", () => $("#importdialog").close());
$("#importdialog").addEventListener("close", () => {
    pending = null;
}); // Esc, Cancel or the backdrop: nothing happens
$("#importdialog").addEventListener("click", (e) => {
    if (e.target === e.currentTarget) e.currentTarget.close();
}); // click on the backdrop
$("#exportlink").addEventListener("click", () => toast(tr("export_started"), "ok"));
$("#catadd").addEventListener("click", addCategory);
$("#catsearch").addEventListener("input", renderManage);
$("#catnew").addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
        e.preventDefault();
        addCategory();
    }
});

// Clear everything: a second, explicit confirmation, then the server removes all notes, tags and categories
$("#clearbtn").addEventListener("click", () => {
    $("#cleardialog").showModal();
    $("#clearno").focus();
});
$("#clearno").addEventListener("click", () => $("#cleardialog").close());
$("#cleardialog").addEventListener("click", (e) => {
    if (e.target === e.currentTarget) e.currentTarget.close();
});
$("#clearyes").addEventListener("click", async () => {
    $("#cleardialog").close();
    try {
        const r = await api("/api/data", {method: "DELETE"});
        if (r.status !== 204) throw new Error("clear");
        toast(tr("data_cleared"), "ok", 3500);
        await refreshData();
    } catch (e) {
        if (e.message !== "not authenticated") toast(tr("data_clear_failed"), "bad", 6000);
    }
});
loadCategories();

// Tags: list, search, sort; rename (an existing name merges), delete; each asks first where it changes many notes
let tagList = [];
const TAG_CAP = 300; // rows drawn at most (the search narrows the rest)
const tagUi = {editing: null, deleting: null, merging: null};
const setTagMsg = (text) => {
    $("#tagmsg").textContent = text;
};
const cleanTag = (s) => s.trim().replace(/^#+/, "").toLowerCase().split(/\s+/).filter(Boolean).join(" "); // like the server: lowercase, spaces collapsed ("#api" works too)
const TAG_ERRORS = {name_invalid: "tags_err_name_invalid", not_found: "tags_err_not_found"};
const tagErrorText = (detail) => tr(TAG_ERRORS[detail && detail.code] || "tags_err_failed");
const tagUrl = (name) => "/api/tags/" + encodeURIComponent(name);

async function tagCall(name, method, body) {
    const r = await api(tagUrl(name), body === undefined ? {method} : json(method, body));
    const data = (await r.json().catch(() => null)) || {};
    return {r, data};
}

async function loadTags() {
    try {
        const r = await api("/api/tags");
        if (!r.ok) throw new Error("tags");
        tagList = await r.json();
    } catch (e) {
        if (e.message !== "not authenticated") setTagMsg(tr("tags_err_failed"));
        return;
    }
    renderTags();
}

const refreshTags = () => Promise.all([loadTags(), loadAbout()]); // the About counts change too
function tagRows() {
    const q = plainText($("#tagsearch").value.trim().replace(/^#+/, ""));
    const list = tagList.filter((t) => !q || plainText(t.name).includes(q));
    if ($("#tagsort").value === "name") list.sort((a, b) => a.name.localeCompare(b.name, LANG));
    return list;
}

function renderTags() {
    const all = tagRows(),
        shown = all.slice(0, TAG_CAP),
        box = $("#tagrows");
    if (!all.length) {
        box.replaceChildren(
            h(
                "li",
                {class: "catrow wide"},
                h("span", {class: "muted"}, tr(tagList.length ? "tags_none_match" : "tags_none")),
            ),
        );
    } else box.replaceChildren(...shown.map(tagRow));
    $("#taghint").textContent =
        all.length > shown.length ? tr("list_capped", {shown: shown.length, total: all.length}) : "";
}

function tagRow(t) {
    const li = h("li", {class: "catrow"});
    const reset = () => {
        tagUi.editing = tagUi.deleting = tagUi.merging = null;
        setTagMsg("");
        renderTags();
    };
    const done = async (message) => {
        reset();
        toast(message, "ok", 3500);
        await refreshTags();
    };
    const fail = async (r, data) => {
        if (r.status === 404) {
            reset();
            await refreshTags();
        }
        setTagMsg(tagErrorText(data.detail));
    };
    if (tagUi.merging && tagUi.merging.from === t.name) {
        // the new name exists: ask before merging
        li.className = "catrow wide";
        const m = tagUi.merging,
            target = tagList.find((x) => x.name === m.to);
        const merge = async () => {
            const {r, data} = await tagCall(t.name, "PUT", {name: m.to});
            if (r.ok) await done(tr("tags_merged", {from: t.name, to: data.name, count: data.count}));
            else await fail(r, data);
        };
        li.append(
            h(
                "span",
                {class: "tagname"},
                tr("tags_merge_ask", {from: t.name, to: m.to, count: t.count, toCount: target ? target.count : 0}),
            ),
            h("button", {type: "button", class: "btn primary", onclick: merge}, tr("tags_merge_yes")),
            h(
                "button",
                {
                    type: "button",
                    class: "btn",
                    onclick: () => {
                        tagUi.merging = null;
                        tagUi.editing = t.name;
                        renderTags();
                    },
                },
                tr("back"),
            ),
        );
    } else if (tagUi.editing === t.name) {
        li.className = "catrow wide";
        const input = h("input", {value: t.name, maxlength: 60, "aria-label": tr("manage_rename")});
        const save = async () => {
            const to = cleanTag(input.value);
            if (!to || to.includes(",") || to.length > 30) {
                setTagMsg(tr("tags_err_name_invalid"));
                return;
            }
            if (to === t.name) {
                reset();
                return;
            }
            if (tagList.some((x) => x.name === to)) {
                setTagMsg("");
                tagUi.merging = {from: t.name, to};
                renderTags();
                return;
            }
            const {r, data} = await tagCall(t.name, "PUT", {name: to});
            if (r.ok) await done(tr("tags_renamed", {name: data.name}));
            else await fail(r, data);
        };
        input.addEventListener("keydown", (e) => {
            if (e.key === "Enter") {
                e.preventDefault();
                save();
            } else if (e.key === "Escape") {
                e.stopPropagation();
                reset();
            }
        });
        li.append(
            input,
            h("button", {type: "button", class: "btn primary", onclick: save}, tr("save")),
            h("button", {type: "button", class: "btn", onclick: reset}, tr("cancel")),
        );
        setTimeout(() => {
            input.focus();
            input.select();
        });
    } else if (tagUi.deleting === t.name) {
        li.className = "catrow wide";
        const remove = async () => {
            const {r, data} = await tagCall(t.name, "DELETE");
            if (r.ok) await done(tr("tags_deleted", {name: t.name, count: data.notes}));
            else await fail(r, data);
        };
        li.append(
            h("span", {class: "tagname"}, tr("tags_delete_ask", {name: t.name, count: t.count})),
            h("button", {type: "button", class: "btn danger", onclick: remove}, tr("yes_delete")),
            h("button", {type: "button", class: "btn", onclick: reset}, tr("back")),
        );
    } else {
        li.append(
            h("span", {class: "tagname", title: "#" + t.name}, "#" + t.name),
            h("span", {class: "n"}, t.count),
            rowBtn("pencil", tr("manage_rename"), () => {
                tagUi.editing = t.name;
                tagUi.deleting = tagUi.merging = null;
                setTagMsg("");
                renderTags();
            }),
            rowBtn(
                "trash",
                tr("delete"),
                () => {
                    tagUi.deleting = t.name;
                    tagUi.editing = tagUi.merging = null;
                    setTagMsg("");
                    renderTags();
                },
                "danger",
            ),
        );
    }
    return li;
}

$("#tagsearch").addEventListener("input", renderTags);
$("#tagsort").addEventListener("change", renderTags);
loadTags();

// Navigation: the link of the section being read is highlighted. A section near the end of the page cannot be
// scrolled to the top, so a clicked link keeps the highlight until the user scrolls by hand.
const NAV = [...document.querySelectorAll("#snav a")],
    SECS = NAV.map((/** @type {HTMLElement} */ a) => document.getElementById(a.dataset.sec));
let navQueued = false,
    navLock = null;
const showNav = (cur) => NAV.forEach((a, i) => a.classList.toggle("on", i === cur));

function updateNav() {
    navQueued = false;
    if (navLock !== null) return;
    let cur = 0;
    SECS.forEach((s, i) => {
        if (!s.hidden && s.getBoundingClientRect().top <= 140) cur = i;
    }); // a hidden section has no position
    if (window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 4) cur = SECS.length - 1;
    showNav(cur);
}

NAV.forEach((a, i) =>
    a.addEventListener("click", () => {
        navLock = i;
        showNav(i);
    }),
);
const unlockNav = () => {
    if (navLock !== null) {
        navLock = null;
        updateNav();
    }
};
["wheel", "touchmove", "keydown", "mousedown"].forEach((ev) =>
    addEventListener(
        ev,
        (/** @type {any} */ e) => {
            if (!(e.target.closest && e.target.closest("#snav"))) unlockNav();
        },
        {passive: true},
    ),
);
addEventListener(
    "scroll",
    () => {
        if (!navQueued) {
            navQueued = true;
            requestAnimationFrame(updateNav);
        }
    },
    {passive: true},
);
updateNav();
fillIcons();
setAiReady(AI_READY);
