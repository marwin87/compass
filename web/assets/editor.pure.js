// ---- Markdown editing helpers: (text, selectionStart, selectionEnd, ...) -> one replacement (pure, no DOM)
// {from, to, insert}: replace text[from:to] with `insert`; {selFrom, selTo}: the selection in the NEW text.
const edResult = (from, to, insert, selFrom, selTo) => ({from, to, insert, selFrom, selTo});

function edWrap(text, a, b, before, after, ph) {
    // **bold**, *italic*, ~~strike~~, `code`: wraps, or unwraps when already wrapped
    const sel = text.slice(a, b),
        single = before.length === 1;
    const around =
        text.slice(a - before.length, a) === before &&
        text.slice(b, b + after.length) === after &&
        !(single && (text[a - before.length - 1] === before || text[b + after.length] === after)); // "**x**" is not "*x*"
    if (a >= before.length && around) {
        const from = a - before.length;
        return edResult(from, b + after.length, sel, from, from + sel.length);
    }
    if (
        sel.length >= before.length + after.length &&
        sel.startsWith(before) &&
        sel.endsWith(after) &&
        !(single && sel[1] === before)
    ) {
        const inner = sel.slice(before.length, sel.length - after.length);
        return edResult(a, b, inner, a, a + inner.length);
    }
    const inner = sel || ph;
    return edResult(a, b, before + inner + after, a + before.length, a + before.length + inner.length);
}

function edLineRange(text, a, b) {
    // the whole lines touched by the selection
    const start = a === 0 ? 0 : text.lastIndexOf("\n", a - 1) + 1;
    const from = b > a && text[b - 1] === "\n" ? b - 1 : b; // a selection that ends at a line start does not include that line
    let end = text.indexOf("\n", from);
    if (end === -1) end = text.length;
    return [start, end];
}

const ED_LINE = {
    // per line kind: how a marker looks, what counts as "already has it", what to strip
    h2: {make: () => "## ", has: /^##(?!#)\s+/, strip: /^#{1,6}\s+/},
    h3: {make: () => "### ", has: /^###(?!#)\s+/, strip: /^#{1,6}\s+/},
    ul: {make: () => "- ", has: /^[-*+]\s+/, strip: /^([-*+]|\d+[.)])\s+/},
    ol: {make: (i) => i + 1 + ". ", has: /^\d+[.)]\s+/, strip: /^([-*+]|\d+[.)])\s+/},
    quote: {make: () => "> ", has: /^>\s?/, strip: /^>\s?/},
};

function edLines(text, a, b, kind) {
    // headings, lists, quotes: toggle a marker on every selected line
    const [start, end] = edLineRange(text, a, b),
        k = ED_LINE[kind];
    const lines = text.slice(start, end).split("\n"),
        filled = lines.filter((l) => l.trim());
    const remove = filled.length > 0 && filled.every((l) => k.has.test(l));
    let n = 0;
    const out = lines
        .map((l) => {
            if (!l.trim() && lines.length > 1) return l; // blank lines inside a selection stay blank
            const bare = l.replace(k.strip, "");
            return remove ? bare : k.make(n++) + bare;
        })
        .join("\n");
    return edResult(start, end, out, start, start + out.length);
}

function edCode(text, a, b, ph) {
    // inline `code` for one line, a fenced block for several
    const sel = text.slice(a, b);
    if (!sel.includes("\n")) return edWrap(text, a, b, "`", "`", ph);
    const [start, end] = edLineRange(text, a, b),
        block = text.slice(start, end);
    const fenced = /^```[^\n]*\n([\s\S]*)\n```$/.exec(block);
    if (fenced) return edResult(start, end, fenced[1], start, start + fenced[1].length);
    return edResult(start, end, "```\n" + block + "\n```", start + 4, start + 4 + block.length);
}

function edLink(text, a, b, ph) {
    // [text](url): the part to type next is selected
    const sel = text.slice(a, b);
    if (/^https?:\/\/\S+$/.test(sel)) return edResult(a, b, "[" + ph + "](" + sel + ")", a + 1, a + 1 + ph.length);
    const label = sel || ph,
        url = "https" + "://"; // (the scheme is split so the page never contains a literal URL: a test checks that)
    const ins = "[" + label + "](" + url + ")";
    return sel
        ? edResult(a, b, ins, a + label.length + 3, a + label.length + 3 + url.length)
        : edResult(a, b, ins, a + 1, a + 1 + label.length);
}

function edBlock(text, from, to, body, selOff, selLen) {
    // a block on its own lines, with a blank line before and after
    const before = text.slice(0, from),
        after = text.slice(to);
    const lead = from === 0 || before.endsWith("\n\n") ? "" : before.endsWith("\n") ? "\n" : "\n\n";
    const trail = after === "" || after.startsWith("\n\n") ? "" : after.startsWith("\n") ? "\n" : "\n\n";
    return edResult(from, to, lead + body + trail, from + lead.length + selOff, from + lead.length + selOff + selLen);
}

function edTable(text, a, b, labels) {
    // a 2x2 table; the first header is selected
    const body =
        "| " + labels.col1 + " | " + labels.col2 + " |\n| --- | --- |\n| " + labels.cell + " | " + labels.cell + " |";
    return edBlock(text, b, b, body, 2, labels.col1.length);
}

function edCallout(text, a, b, kind, ph) {
    // > [!TIP] + the selected lines (or a placeholder) as the callout body
    const tag = "> [!" + kind.toUpperCase() + "]\n";
    if (a === b) return edBlock(text, a, a, tag + "> " + ph, tag.length + 2, ph.length);
    const [start, end] = edLineRange(text, a, b),
        lines = text
            .slice(start, end)
            .split("\n")
            .map((l) => "> " + l)
            .join("\n");
    return edBlock(text, start, end, tag + lines, tag.length, lines.length);
}
