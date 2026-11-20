// ---- Markdown: text -> blocks (pure functions, no DOM)
const MD_LIST = /^(\s*)([-*+]|\d{1,9}[.)])\s+(.*)$/;
const MD_HR = /^\s{0,3}(?:(?:\*\s*){3,}|(?:-\s*){3,}|(?:_\s*){3,})$/;
const MD_HEAD = /^\s{0,3}(#{1,6})\s+(.*?)(?:\s+#+)?\s*$/;
const MD_FENCE = /^\s{0,3}(```+|~~~+)\s*([^\s`]*)[^`]*$/;
const MD_QUOTE = /^\s{0,3}>\s?(.*)$/;
const MD_SEP = /^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$/;
const MD_CALLOUT = /^\[!(note|info|tip|warning|caution|important|success)\]\s*(.*)$/i;
const mdIndent = (s) => s.length - s.trimStart().length;

function mdCells(line) {
    let s = line.trim();
    if (s.startsWith("|")) s = s.slice(1);
    if (s.endsWith("|") && !s.endsWith("\\|")) s = s.slice(0, -1);
    return s.split(/(?<!\\)\|/).map((c) => c.trim().replace(/\\\|/g, "|"));
}

function mdTableAt(lines, i) {
    if (i + 1 >= lines.length || !lines[i].includes("|") || !MD_SEP.test(lines[i + 1]) || !lines[i + 1].includes("-"))
        return false;
    return mdCells(lines[i]).length === mdCells(lines[i + 1]).length;
}

function mdStartsBlock(lines, i) {
    const l = lines[i];
    if (MD_FENCE.test(l) || MD_HR.test(l) || MD_HEAD.test(l) || MD_QUOTE.test(l) || mdTableAt(lines, i)) return true;
    const m = MD_LIST.exec(l);
    return !!m && (!/\d/.test(m[2]) || parseInt(m[2], 10) === 1); // only "1." may interrupt a paragraph
}

function mdList(lines, i) {
    const first = MD_LIST.exec(lines[i]),
        base = mdIndent(first[1]),
        ordered = /\d/.test(first[2]);
    const block = {t: ordered ? "ol" : "ul", start: ordered ? parseInt(first[2], 10) : 1, items: []};
    const n = lines.length;
    while (i < n) {
        const m = MD_LIST.exec(lines[i]);
        if (!m || mdIndent(m[1]) < base || mdIndent(m[1]) > base + 1 || /\d/.test(m[2]) !== ordered) break;
        const body = [m[3]];
        i++;
        let sameList = false;
        while (i < n) {
            const l = lines[i];
            if (!l.trim()) {
                let j = i;
                while (j < n && !lines[j].trim()) j++;
                if (j >= n) {
                    i = j;
                    break;
                }
                const nm = MD_LIST.exec(lines[j]);
                if (mdIndent(lines[j]) > base + 1) {
                    body.push("");
                    i++;
                    continue;
                } // still inside this item
                if (nm && mdIndent(nm[1]) >= base && /\d/.test(nm[2]) === ordered) {
                    i = j;
                    sameList = true;
                } // loose list
                break;
            }
            if (mdIndent(l) > base + 1) {
                body.push(l.slice(Math.min(mdIndent(l), base + 2)));
                i++;
                continue;
            }
            if (MD_LIST.test(l) || mdStartsBlock(lines, i)) break;
            body.push(l.trim()); // lazy continuation
            i++;
        }
        block.items.push({c: mdBlocks(body)});
        if (!sameList && (i >= n || !MD_LIST.test(lines[i]))) break;
    }
    return {block, next: i};
}

function mdBlocks(lines) {
    const out = [],
        n = lines.length;
    let i = 0;
    while (i < n) {
        const line = lines[i];
        if (!line.trim()) {
            i++;
            continue;
        }
        let m;
        if ((m = MD_FENCE.exec(line))) {
            const fence = m[1],
                code = [];
            i++;
            while (i < n && !new RegExp("^\\s{0,3}" + fence[0] + "{" + fence.length + ",}\\s*$").test(lines[i])) {
                code.push(lines[i]);
                i++;
            }
            if (i < n) i++; // the closing fence (an unclosed one runs to the end)
            out.push({t: "code", lang: m[2].toLowerCase(), text: code.join("\n")});
        } else if (MD_HR.test(line)) {
            out.push({t: "hr"});
            i++;
        } else if ((m = MD_HEAD.exec(line))) {
            out.push({t: "h", level: m[1].length, c: mdInline(m[2])});
            i++;
        } else if (MD_QUOTE.test(line)) {
            const inner = [];
            while (i < n && MD_QUOTE.test(lines[i])) {
                inner.push(MD_QUOTE.exec(lines[i])[1]);
                i++;
            }
            const co = MD_CALLOUT.exec(inner[0].trim());
            if (co) {
                const rest = co[2] ? [co[2], ...inner.slice(1)] : inner.slice(1);
                const kind = co[1].toLowerCase();
                out.push({t: "callout", kind: kind === "caution" ? "warning" : kind, c: mdBlocks(rest)});
            } else out.push({t: "quote", c: mdBlocks(inner)});
        } else if (mdTableAt(lines, i)) {
            const head = mdCells(lines[i]).map(mdInline);
            const align = mdCells(lines[i + 1]).map((c) =>
                c.startsWith(":") && c.endsWith(":") ? "center" : c.endsWith(":") ? "right" : c.startsWith(":") ? "left" : "",
            );
            i += 2;
            const rows = [];
            while (i < n && lines[i].trim() && lines[i].includes("|") && !mdStartsBlock(lines, i)) {
                const cells = mdCells(lines[i]);
                rows.push(head.map((_, k) => mdInline(cells[k] || "")));
                i++;
            }
            out.push({t: "table", head, align, rows});
        } else if (MD_LIST.test(line)) {
            const r = mdList(lines, i);
            out.push(r.block);
            i = r.next;
        } else {
            const para = [line.trim()];
            i++;
            while (i < n && lines[i].trim() && !mdStartsBlock(lines, i)) {
                para.push(lines[i].trim());
                i++;
            }
            out.push({t: "p", c: mdInline(para.join("\n"))});
        }
    }
    return out;
}

const mdParse = (text) => mdBlocks(text.replace(/\r\n?/g, "\n").replace(/\t/g, "    ").split("\n"));

// ---- Markdown: inline text -> nodes
const mdSafeUrl = (u) => /^(https?:\/\/|mailto:|\/|#)/i.test(u);

function mdClose(s, from, d, single) {
    // index of a closing delimiter, or -1
    for (let j = s.indexOf(d, from); j !== -1; j = s.indexOf(d, j + 1)) {
        if (/\s/.test(s[j - 1] || " ")) continue;
        if (single && (s[j - 1] === d || s[j + 1] === d)) continue;
        if (d[0] === "_" && /[\p{L}\p{N}]/u.test(s[j + d.length] || " ")) continue;
        return j;
    }
    return -1;
}

function mdInline(s) {
    const out = [];
    let buf = "",
        i = 0;
    const flush = () => {
        if (buf) {
            out.push({t: "text", v: buf});
            buf = "";
        }
    };
    while (i < s.length) {
        const c = s[i];
        if (c === "\\" && i + 1 < s.length && /[\\`*_{}\[\]()#+\-.!|~>]/.test(s[i + 1])) {
            buf += s[i + 1];
            i += 2;
            continue;
        }
        if (c === "\n") {
            flush();
            out.push({t: "br"});
            i++;
            continue;
        }
        if (c === "`") {
            let k = i;
            while (s[k] === "`") k++;
            const run = s.slice(i, k),
                end = s.indexOf(run, k);
            if (end !== -1) {
                flush();
                let v = s.slice(k, end);
                if (v.length > 2 && v.startsWith(" ") && v.endsWith(" ")) v = v.slice(1, -1);
                out.push({t: "code", v});
                i = end + run.length;
                continue;
            }
            buf += run;
            i = k;
            continue;
        }
        if (c === "[") {
            const close = s.indexOf("](", i);
            if (close !== -1) {
                const end = s.indexOf(")", close + 2);
                const url =
                    end === -1
                        ? ""
                        : s
                            .slice(close + 2, end)
                            .trim()
                            .split(/\s+/)[0];
                if (end !== -1 && mdSafeUrl(url) && close > i + 1) {
                    flush();
                    out.push({t: "link", href: url, c: mdInline(s.slice(i + 1, close))});
                    i = end + 1;
                    continue;
                }
            }
        }
        if (c === "~" && s[i + 1] === "~" && s[i + 2] && !/\s/.test(s[i + 2])) {
            const end = mdClose(s, i + 2, "~~", false);
            if (end !== -1) {
                flush();
                out.push({t: "del", c: mdInline(s.slice(i + 2, end))});
                i = end + 2;
                continue;
            }
        }
        if (
            (c === "*" || c === "_") &&
            s[i + 1] === c &&
            s[i + 2] &&
            !/\s/.test(s[i + 2]) &&
            (c === "*" || !/[\p{L}\p{N}]/u.test(s[i - 1] || " "))
        ) {
            const end = mdClose(s, i + 2, c + c, false);
            if (end !== -1) {
                flush();
                out.push({t: "strong", c: mdInline(s.slice(i + 2, end))});
                i = end + 2;
                continue;
            }
        }
        if (
            (c === "*" || c === "_") &&
            s[i + 1] &&
            !/\s/.test(s[i + 1]) &&
            s[i + 1] !== c &&
            (c === "*" || !/[\p{L}\p{N}]/u.test(s[i - 1] || " "))
        ) {
            const end = mdClose(s, i + 1, c, true);
            if (end !== -1) {
                flush();
                out.push({t: "em", c: mdInline(s.slice(i + 1, end))});
                i = end + 1;
                continue;
            }
        }
        if (c === "h" && /^https?:\/\//.test(s.slice(i, i + 8)) && !/[\p{L}\p{N}]/u.test(s[i - 1] || " ")) {
            const m = /^https?:\/\/[^\s<>]+/.exec(s.slice(i));
            const url = m[0].replace(/[.,;:!?'")\]]+$/, "");
            flush();
            out.push({t: "link", href: url, c: [{t: "text", v: url}]});
            i += url.length;
            continue;
        }
        buf += c;
        i++;
    }
    flush();
    return out;
}

const mdPlain = (nodes) =>
    nodes.map((n) => (n.t === "text" || n.t === "code" ? n.v : n.t === "br" ? " " : n.c ? mdPlain(n.c) : "")).join("");

// ---- syntax highlighting: code -> [[class, text], ...] (small, dependency free)
const HL_WORDS = (s) => new RegExp("^(?:" + s.split(" ").join("|") + ")\\b");
const HL_LANGS = {
    js: {
        kw: "const let var function return if else for while do switch case break continue new class extends import export from default async await try catch finally throw typeof instanceof in of delete yield static this super",
        lit: "true false null undefined NaN Infinity",
        com: ["//[^\n]*", "/\\*[\\s\\S]*?(?:\\*/|$)"],
        str: ["`(?:\\\\[\\s\\S]|[^`\\\\])*`?", '"(?:\\\\.|[^"\\\\\n])*"?', "'(?:\\\\.|[^'\\\\\n])*'?"],
    },
    python: {
        kw: "def class return if elif else for while in not and or is import from as with try except finally raise lambda yield pass break continue global nonlocal async await del assert self",
        lit: "True False None",
        com: ["#[^\n]*"],
        str: ['"""[\\s\\S]*?(?:"""|$)', "'''[\\s\\S]*?(?:'''|$)", '"(?:\\\\.|[^"\\\\\n])*"?', "'(?:\\\\.|[^'\\\\\n])*'?"],
    },
    sql: {
        kw: "select from where group by order having insert into values update set delete create table alter drop index join inner left right outer full cross on as and or not in is like between limit offset union all distinct case when then else end primary key foreign references default null unique with begin commit rollback explain count sum avg min max",
        lit: "",
        ci: true,
        com: ["--[^\n]*", "/\\*[\\s\\S]*?(?:\\*/|$)"],
        str: ["'(?:''|[^'])*'?", '"[^"\n]*"?'],
    },
    json: {kw: "", lit: "true false null", com: [], str: ['"(?:\\\\.|[^"\\\\\n])*"?']},
    bash: {
        kw: "if then else elif fi for while do done case esac function in echo cd ls cat grep sed awk export source sudo docker git npm pip uv make curl mkdir rm cp mv",
        lit: "",
        com: ["#[^\n]*"],
        str: ['"(?:\\\\.|[^"\\\\])*"?', "'[^']*'?"],
        extra: [["tk-lit", "\\$\\{?[A-Za-z_][\\w]*\\}?"]],
    },
    yaml: {
        kw: "",
        lit: "true false null yes no",
        com: ["#[^\n]*"],
        str: ['"(?:\\\\.|[^"\\\\\n])*"?', "'[^'\n]*'?"],
        extra: [["tk-fn", "[\\w.-]+(?=\\s*:(?:\\s|$))"]],
    },
    css: {
        kw: "",
        lit: "",
        com: ["/\\*[\\s\\S]*?(?:\\*/|$)"],
        str: ['"[^"\n]*"?', "'[^'\n]*'?"],
        extra: [
            ["tk-kw", "@[\\w-]+"],
            ["tk-fn", "[\\w-]+(?=\\s*:)"],
            ["tk-num", "#[0-9a-fA-F]{3,8}\\b"],
        ],
    },
    html: {
        kw: "",
        lit: "",
        com: ["<!--[\\s\\S]*?(?:-->|$)"],
        str: ['"[^"\n]*"?', "'[^'\n]*'?"],
        extra: [
            ["tk-tag", "</?[A-Za-z][\\w:-]*"],
            ["tk-tag", "/?>"],
            ["tk-attr", "[\\w:-]+(?==)"],
        ],
    },
};
const HL_ALIAS = {
    javascript: "js",
    jsx: "js",
    ts: "js",
    tsx: "js",
    typescript: "js",
    node: "js",
    py: "python",
    python3: "python",
    sh: "bash",
    shell: "bash",
    zsh: "bash",
    console: "bash",
    yml: "yaml",
    xml: "html",
    svg: "html",
    scss: "css",
    postgres: "sql",
    postgresql: "sql",
    sqlite: "sql",
    mysql: "sql",
    json5: "json",
};
const HL_LABELS = {
    js: "JavaScript",
    python: "Python",
    sql: "SQL",
    json: "JSON",
    bash: "Bash",
    yaml: "YAML",
    css: "CSS",
    html: "HTML",
};
const hlLang = (name) => {
    const n = (name || "").toLowerCase();
    return HL_LANGS[HL_ALIAS[n] || n] ? HL_ALIAS[n] || n : "";
};

function hlDetect(code) {
    // guess a language when the fence names none
    const t = code.trim();
    if ((t.startsWith("{") || t.startsWith("[")) && t.length < 20000) {
        try {
            JSON.parse(t);
            return "json";
        } catch (e) {
            /* not json */
        }
    }
    if (/^<[!A-Za-z][^>]*>/.test(t) && /<\/[A-Za-z]/.test(t)) return "html";
    if (
        /^\s*(select|insert\s+into|update|delete\s+from|create\s+table|with)\b[\s\S]*\b(from|into|set|values|table|as)\b/i.test(
            t,
        )
    )
        return "sql";
    if (
        /^#!.*\b(ba|z)?sh\b/.test(t) ||
        /^\s*\$\s+\S/m.test(t) ||
        /^\s*(sudo|docker|git|npm|pip|uv|curl|cd|ls|mkdir|export)\s+\S/m.test(t)
    )
        return "bash";
    if (
        /^\s*(def|class)\s+\w+.*:\s*$/m.test(t) ||
        (/^\s*(import|from)\s+\w+.*$/m.test(t) && /:\s*$/m.test(t)) ||
        (/\bprint\(/.test(t) && !/;\s*$/m.test(t))
    )
        return "python";
    if (/\b(const|let|var|function)\s+[\w$]+|=>|console\.log|\bimport\s.+\sfrom\s/.test(t)) return "js";
    if (/^[\w.-]+:\s*(\S.*)?$/m.test(t) && !/[;{}]/.test(t) && t.split("\n").length > 1) return "yaml";
    if (/[.#]?[\w-]+\s*\{[^}]*:[^}]*\}/.test(t)) return "css";
    return "";
}

const HL_CACHE = {};

function hlRules(lang) {
    if (HL_CACHE[lang]) return HL_CACHE[lang];
    const d = HL_LANGS[lang],
        rules = [];
    for (const re of d.com) rules.push(["tk-com", new RegExp(re, "y")]);
    for (const re of d.str) rules.push(["tk-str", new RegExp(re, "y")]);
    for (const [cls, re] of d.extra || []) rules.push([cls, new RegExp(re, "y")]);
    rules.push(["tk-num", /(?:0x[0-9a-fA-F]+|\d+(?:\.\d+)?(?:e[+-]?\d+)?)\b/y]);
    if (d.lit) rules.push(["tk-lit", new RegExp("(?:" + d.lit.split(" ").join("|") + ")\\b", "y")]);
    if (d.kw) rules.push(["tk-kw", new RegExp("(?:" + d.kw.split(" ").join("|") + ")\\b", d.ci ? "iy" : "y")]);
    rules.push(["tk-fn", /[A-Za-z_$][\w$]*(?=\()/y]);
    return (HL_CACHE[lang] = rules);
}

function mdHighlight(code, lang) {
    if (!lang || code.length > 30000) return [["", code]];
    const rules = hlRules(lang),
        out = [];
    let plain = "",
        i = 0;
    const wordStart = (p) => p === 0 || !/[\w$]/.test(code[p - 1]);
    while (i < code.length) {
        let hit = null;
        for (const [cls, re] of rules) {
            if ((cls === "tk-kw" || cls === "tk-lit" || cls === "tk-num" || cls === "tk-fn") && !wordStart(i)) continue;
            re.lastIndex = i;
            const m = re.exec(code);
            if (m && m[0]) {
                hit = [cls, m[0]];
                break;
            }
        }
        if (hit) {
            if (plain) {
                out.push(["", plain]);
                plain = "";
            }
            out.push(hit);
            i += hit[1].length;
        } else {
            plain += code[i];
            i++;
        }
    }
    if (plain) out.push(["", plain]);
    return out;
}
