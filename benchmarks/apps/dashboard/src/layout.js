import { h } from "./h.js";

export function Page({ title, children }) {
  return h("div", { className: "app" },
    h("nav", null, ["Overview", "Charts", "Calendar", "Tasks", "Reports"].map((name) =>
      h("a", { key: name, href: "#" + name.toLowerCase(), "aria-current": name === title ? "page" : undefined }, name))),
    h("main", null, h("h1", null, title), children));
}

export function Table({ columns, rows }) {
  return h("table", null,
    h("thead", null, h("tr", null, columns.map((c) => h("th", { key: c }, c)))),
    h("tbody", null, rows.map((r, i) => h("tr", { key: i }, r.map((cell, j) => h("td", { key: j }, cell))))));
}
