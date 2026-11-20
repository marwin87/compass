// A dropdown with rounded corners (a native <select> popup cannot be styled): button + listbox, keyboard and outside-click aware.
function dropdown(label, onpick) {
    let items = [],
        value = "",
        hot = 0;
    const text = h("span", {}),
        menu = h("ul", {class: "ddmenu", role: "listbox", "aria-label": label, hidden: true});
    const btn = h(
        "button",
        {type: "button", class: "ddbtn", "aria-haspopup": "listbox", "aria-expanded": "false", "aria-label": label},
        text,
        icon("chevron-down", 14),
    );
    const el = h("div", {class: "dd"}, btn, menu);
    const isOpen = () => !menu.hidden;

    function paint() {
        menu.replaceChildren(
            ...items.map((o, i) =>
                h(
                    "li",
                    {
                        class: "ddopt" + (i === hot ? " hot" : ""),
                        role: "option",
                        "aria-selected": o.value === value ? "true" : "false",
                        title: o.label,
                        onmousedown: (e) => e.preventDefault(),
                        onclick: () => pick(i),
                        onmousemove: () => {
                            if (hot !== i) {
                                hot = i;
                                paint();
                            }
                        },
                    },
                    o.label,
                ),
            ),
        );
        const cur = items.find((o) => o.value === value);
        text.textContent = cur ? cur.label : "";
    }

    function open(on) {
        menu.hidden = !on;
        el.classList.toggle("open", on);
        btn.setAttribute("aria-expanded", on ? "true" : "false");
        if (on) {
            hot = Math.max(
                0,
                items.findIndex((o) => o.value === value),
            );
            paint();
            const h0 = menu.children[hot];
            if (h0) h0.scrollIntoView({block: "nearest"});
        }
    }

    function pick(i) {
        open(false);
        btn.focus();
        if (items[i] && items[i].value !== value) onpick(items[i].value);
    }

    btn.addEventListener("click", () => open(!isOpen()));
    btn.addEventListener("keydown", (e) => {
        if (e.key === "Escape" && isOpen()) {
            e.preventDefault();
            e.stopPropagation();
            open(false);
        } else if (e.key === "ArrowDown" || e.key === "ArrowUp") {
            e.preventDefault();
            if (!isOpen()) open(true);
            else {
                hot = Math.max(0, Math.min(items.length - 1, hot + (e.key === "ArrowDown" ? 1 : -1)));
                paint();
                menu.children[hot].scrollIntoView({block: "nearest"});
            }
        } else if ((e.key === "Enter" || e.key === " ") && isOpen()) {
            e.preventDefault();
            pick(hot);
        }
    });
    document.addEventListener("mousedown", (e) => {
        if (isOpen() && !el.contains(e.target)) open(false);
    });
    btn.addEventListener("blur", () =>
        setTimeout(() => {
            if (isOpen() && !el.contains(document.activeElement)) open(false);
        }, 0),
    );
    return {
        el,
        set(list, v) {
            items = list;
            value = v;
            paint();
        },
        value: () => value,
    };
}

// --- the chat with the notes. cb.openNote(id, title) shows a source note, cb.close() leaves the chat; the page keeps this panel alive
const CHAT_ERRORS = {
    not_enabled: "ai_err_not_enabled",
    not_configured: "ai_err_not_configured",
    timeout: "ai_err_timeout",
    failed: "ai_err_failed_chat",
};

function makeChat(cb) {
    let convs = [],
        cur = {id: null, messages: []},
        run = null; // run: the question being answered, {ctrl}
    const select = dropdown(tr("chat_list_label"), (v) => openConv(v));
    const del = h(
        "button",
        {
            type: "button",
            class: "btn icon",
            "aria-label": tr("chat_delete"),
            title: tr("chat_delete"),
            onclick: () => askDelete(true),
        },
        icon("trash", 14),
    );
    const nameIn = h("input", {
        class: "chatname",
        maxlength: "200",
        autocomplete: "off",
        "aria-label": tr("chat_rename"),
        placeholder: tr("chat_rename"),
        hidden: true,
    });
    const rename = h(
        "button",
        {
            type: "button",
            class: "btn icon",
            "aria-label": tr("chat_rename"),
            title: tr("chat_rename"),
            onclick: () => editName(true),
        },
        icon("pencil", 14),
    );
    const ask = h(
        "div",
        {class: "chatask", hidden: true},
        h("span", {}, tr("chat_delete_ask")),
        h("button", {type: "button", class: "btn danger", onclick: removeConv}, tr("yes_delete")),
        h("button", {type: "button", class: "btn", onclick: () => askDelete(false)}, tr("back")),
    );
    const manageBtn = h(
        "button",
        {
            type: "button",
            class: "btn icon",
            "aria-label": tr("chat_manage"),
            title: tr("chat_manage"),
            onclick: () => manage(mgr.hidden),
        },
        icon("list", 14),
    );
    const head = h(
        "div",
        {class: "aihd"},
        icon("spark", 16),
        h("span", {}, tr("chat_h")),
        select.el,
        nameIn,
        h(
            "button",
            {
                type: "button",
                class: "btn icon",
                "aria-label": tr("chat_new"),
                title: tr("chat_new"),
                onclick: () => openConv(""),
            },
            icon("plus", 14),
        ),
        rename,
        del,
        manageBtn,
        h("span", {class: "grow"}),
        aiTag(),
        h(
            "button",
            {type: "button", class: "btn icon", "aria-label": tr("ai_close"), title: tr("ai_close"), onclick: cb.close},
            icon("x", 14),
        ),
    );
    const log = h("div", {class: "chatlog", role: "log", "aria-live": "polite"});
    // --- management: pick many conversations and delete them at once (older than OLD_DAYS are one click)
    const OLD_DAYS = 30;
    let picked = new Set();
    const mAll = h("input", {
        type: "checkbox",
        onchange: () => {
            picked = new Set(mAll.checked ? convs.map((c) => c.id) : []);
            mdraw();
        },
    });
    const mCount = h("span", {class: "muted"});
    const mOld = h(
        "button",
        {
            type: "button",
            class: "btn",
            onclick: () => {
                picked = new Set(convs.filter(isOld).map((c) => c.id));
                mdraw();
            },
        },
        tr("chat_select_old"),
    );
    const mDel = h(
        "button",
        {
            type: "button",
            class: "btn danger",
            onclick: () => {
                mAsk.hidden = false;
                mAskText.textContent = tr("chat_delete_many_ask", {count: picked.size});
            },
        },
        tr("chat_delete_selected"),
    );
    const mAskText = h("span", {});
    const mAsk = h(
        "div",
        {class: "chatask", hidden: true},
        mAskText,
        h("button", {type: "button", class: "btn danger", onclick: removeMany}, tr("yes_delete")),
        h(
            "button",
            {
                type: "button",
                class: "btn",
                onclick: () => {
                    mAsk.hidden = true;
                },
            },
            tr("back"),
        ),
    );
    const mList = h("div", {class: "mlist"});
    const mgr = h(
        "div",
        {class: "chatmgr", hidden: true},
        h(
            "div",
            {class: "mbar"},
            h("label", {}, mAll, tr("chat_select_all")),
            mCount,
            h("span", {class: "grow"}),
            mOld,
            mDel,
        ),
        mAsk,
        mList,
    );
    const isOld = (c) => Date.now() - new Date(c.updated_at).getTime() > OLD_DAYS * 864e5;

    function mdraw() {
        mList.replaceChildren(
            ...(convs.length
                ? convs.map((c) =>
                    h(
                        "label",
                        {class: "mrow" + (picked.has(c.id) ? " on" : "") + (isOld(c) ? " old" : "")},
                        h("input", {
                            type: "checkbox",
                            checked: picked.has(c.id),
                            onchange: (e) => {
                                e.target.checked ? picked.add(c.id) : picked.delete(c.id);
                                mdraw();
                            },
                        }),
                        h("span", {class: "tt", title: c.title}, c.title || tr("chat_untitled")),
                        h("span", {class: "mm"}, tr("chat_msgs", {count: c.count}) + " · " + longDate(c.updated_at)),
                    ),
                )
                : [h("div", {class: "chatempty"}, tr("chat_none"))]),
        );
        mCount.textContent = picked.size
            ? tr("chat_selected", {count: picked.size})
            : tr("chat_total", {count: convs.length});
        mDel.disabled = !picked.size;
        mAll.checked = !!convs.length && picked.size === convs.length;
        mAll.indeterminate = picked.size > 0 && picked.size < convs.length;
        mAsk.hidden = true;
    }

    async function manage(on) {
        if (on && run) return; // an answer is being written
        askDelete(false);
        editName(false);
        if (on) {
            picked = new Set();
            await loadList();
            mdraw();
        }
        mgr.hidden = !on;
        log.hidden = form.hidden = note.hidden = on;
        manageBtn.classList.toggle("act", on);
        if (!on) input.focus();
    }

    async function removeMany() {
        const ids = [...picked];
        mAsk.hidden = true;
        try {
            const r = await api("/api/chats/delete", json("POST", {ids}));
            if (!r.ok) throw new Error("delete");
            toast(tr("chat_deleted_many", {count: (await r.json()).deleted}), "ok");
        } catch (e) {
            if (e.message !== "not authenticated") toast(tr("chat_delete_failed"), "bad", 4000);
            return;
        }
        if (ids.includes(cur.id)) {
            cur = {id: null, messages: []};
            draw();
        }
        picked = new Set();
        await loadList();
        mdraw();
    }

    const input = h("textarea", {
        rows: "3",
        maxlength: "4000",
        placeholder: tr("chat_ph"),
        "aria-label": tr("chat_ph"),
    });
    const send = h(
        "button",
        {type: "button", class: "btn primary", onclick: () => (run ? stop() : ask1(input.value))},
        tr("chat_send"),
    );
    const grow = () => {
        input.style.height = "auto";
        input.style.height = Math.min(220, input.scrollHeight) + "px";
    }; // the box grows with the text, up to a limit
    input.addEventListener("input", grow);
    input.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
            e.preventDefault();
            if (!run) ask1(input.value);
        }
    });
    const form = h(
            "div",
            {class: "chatform"},
            h("div", {class: "chatbox"}, input, h("div", {class: "chatbar"}, send)),
        ),
        note = h("div", {class: "chatnote"}, tr("chat_hint"));
    const el = h("div", {class: "chat"}, head, ask, log, mgr, form, note);
    const down = () => {
        log.scrollTop = log.scrollHeight;
    };
    const askDelete = (on) => {
        ask.hidden = !on;
    };

    function editName(on) {
        // the dropdown turns into a text field: Enter saves, Esc or leaving cancels
        if (on && !cur.id) return;
        select.el.hidden = on;
        nameIn.hidden = !on;
        if (on) {
            nameIn.value = cur.title || "";
            nameIn.focus();
            nameIn.select();
        }
    }

    async function saveName() {
        const title = nameIn.value.trim(),
            id = cur.id;
        editName(false);
        if (!title || title === cur.title) return;
        try {
            const r = await api("/api/chats/" + id, json("PATCH", {title}));
            if (!r.ok) throw new Error("rename");
            if (cur.id === id) cur.title = title;
        } catch (e) {
            if (e.message !== "not authenticated") toast(tr("chat_rename_failed"), "bad", 4000);
        }
        loadList();
    }

    nameIn.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.isComposing) {
            e.preventDefault();
            saveName();
        } else if (e.key === "Escape") {
            e.preventDefault();
            e.stopPropagation();
            editName(false);
        }
    });
    nameIn.addEventListener("blur", () => {
        if (!nameIn.hidden) editName(false);
    });

    function fillList(value) {
        select.set(
            [
                {value: "", label: tr("chat_new")},
                ...convs.map((c) => ({value: String(c.id), label: c.title || tr("chat_untitled")})),
            ],
            value,
        );
        del.hidden = rename.hidden = !cur.id;
    }

    async function loadList() {
        try {
            const r = await api("/api/chats");
            if (r.ok) convs = await r.json();
        } catch (e) {
            /* the list is a convenience: a new chat still works */
        }
        const mine = cur.id && convs.find((c) => c.id === cur.id);
        if (mine) cur.title = mine.title;
        fillList(cur.id ? String(cur.id) : "");
    }

    async function openConv(id) {
        if (run) return; // an answer is being written: the list stays where it is
        askDelete(false);
        editName(false);
        cur = {id: null, messages: []};
        if (id) {
            try {
                const r = await api("/api/chats/" + id);
                if (!r.ok) throw new Error("chat");
                cur = await r.json();
            } catch (e) {
                if (e.message !== "not authenticated") toast(tr("load_failed"), "bad");
                await loadList();
            }
        }
        fillList(cur.id ? String(cur.id) : "");
        draw();
        input.focus();
    }

    async function removeConv() {
        const id = cur.id;
        askDelete(false);
        try {
            const r = await api("/api/chats/" + id, {method: "DELETE"});
            if (r.status !== 204 && r.status !== 404) throw new Error("delete");
        } catch (e) {
            if (e.message !== "not authenticated") toast(tr("chat_delete_failed"), "bad", 4000);
            return;
        }
        cur = {id: null, messages: []};
        await loadList();
        draw();
    }

    const md = (text) => h("article", {class: "md"}, mdBlocksDom(mdParse(text), {tk: [], heads: [], lang: ""}));

    function sources(list) {
        if (!list.length) return null;
        return h(
            "div",
            {class: "chatsrc"},
            h("span", {class: "lbl"}, tr("chat_sources")),
            list.map((s, i) =>
                s.deleted
                    ? h("span", {
                        class: "srcchip gone",
                        title: tr("chat_source_deleted")
                    }, h("b", {}, String(i + 1)), s.title)
                    : h(
                        "button",
                        {type: "button", class: "srcchip", onclick: () => cb.openNote(s.id, s.title)},
                        h("b", {}, String(i + 1)),
                        s.title,
                    ),
            ),
        );
    }

    const bubble = (m) =>
        m.role === "user"
            ? h("div", {class: "chatmsg user"}, m.text)
            : h("div", {class: "chatmsg bot"}, md(m.text), sources(m.sources || []));

    function draw() {
        log.replaceChildren(
            ...(cur.messages.length
                ? cur.messages.map(bubble)
                : [h("div", {class: "chatempty"}, icon("chat-compass", 28), h("div", {}, tr("chat_empty")))]),
        );
        down();
    }

    const thinking = (text) => h("div", {class: "aithink", role: "status"}, icon("spark", 16), h("span", {}, text));

    function stop() {
        if (run) run.ctrl.abort();
    }

    async function ask1(raw) {
        const question = raw.trim();
        if (!question || run) return;
        askDelete(false);
        const ctrl = new AbortController();
        run = {ctrl};
        send.textContent = tr("chat_stop");
        input.value = "";
        grow();
        const user = h("div", {class: "chatmsg user"}, question),
            bot = h("div", {class: "chatmsg bot"}, thinking(tr("chat_thinking")));
        if (!cur.messages.length) log.replaceChildren();
        log.append(user, bot);
        down();
        const fail = (code) =>
            bot.replaceChildren(
                h(
                    "div",
                    {class: "err aierr", role: "alert"},
                    tr(CHAT_ERRORS[code] || "ai_err_failed_chat"),
                    h(
                        "button",
                        {
                            type: "button",
                            class: "btn",
                            onclick: () => {
                                user.remove();
                                bot.remove();
                                if (!log.children.length) draw();
                                ask1(question);
                            },
                        },
                        tr("retry"),
                    ),
                ),
            );
        aiBusy(() => el);
        let finished = false,
            text = "",
            frame = 0;
        const show = () => {
            frame = 0;
            bot.replaceChildren(md(text));
            down();
        };
        try {
            if (!cur.id) {
                const c = await api("/api/chats", {method: "POST"});
                if (!c.ok) throw new Error("chat");
                cur.id = (await c.json()).id;
            }
            const resp = await api("/api/chats/" + cur.id + "/ask", {...json("POST", {question}), signal: ctrl.signal});
            if (!resp.ok) {
                const d = (await resp.json().catch(() => ({}))).detail;
                fail(d && d.code);
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
                    if (e.type === "indexing")
                        bot.replaceChildren(thinking(tr("chat_indexing", {done: e.done, total: e.total})));
                    else if (e.type === "excerpts") bot.replaceChildren(thinking(tr("chat_reading")));
                    else if (e.type === "delta") {
                        text += e.text;
                        if (!frame) frame = requestAnimationFrame(show);
                    } else if (e.type === "error") {
                        fail(e.code);
                        return;
                    } else if (e.type === "done") {
                        cancelAnimationFrame(frame);
                        finished = true;
                        cur.messages.push(
                            {role: "user", text: question},
                            {role: "assistant", text: e.text, sources: e.sources},
                        );
                        draw();
                        loadList();
                    }
                }
            }
            if (!finished) fail("failed");
        } catch (e) {
            if (e.message === "not authenticated") return;
            if (e.name === "AbortError") {
                cancelAnimationFrame(frame);
                user.remove();
                bot.remove();
                input.value = question;
                grow();
                if (!cur.messages.length) draw();
            } // stopped: nothing was saved, the question comes back
            else fail("failed");
        } finally {
            aiBusy(null);
            run = null;
            send.textContent = tr("chat_send");
            if (cur.id && !convs.some((c) => c.id === cur.id)) loadList();
        }
    }

    draw();
    loadList();
    return {
        el,
        show: () => {
            loadList();
            setTimeout(() => input.focus());
        },
    };
}
