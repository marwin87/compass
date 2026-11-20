var i = /** @type {HTMLInputElement} */ (document.querySelector(".pwbox input")),
    b = /** @type {HTMLButtonElement} */ (document.querySelector(".pwtoggle"));
b.addEventListener("click", function () {
    var show = i.type === "password";
    i.type = show ? "text" : "password";
    b.setAttribute("aria-pressed", String(show));
    b.setAttribute("aria-label", b.dataset[show ? "hide" : "show"]);
    b.title = b.dataset[show ? "hide" : "show"];
    b.firstElementChild.toggleAttribute("hidden", show);
    b.lastElementChild.toggleAttribute("hidden", !show);
    i.focus();
});
