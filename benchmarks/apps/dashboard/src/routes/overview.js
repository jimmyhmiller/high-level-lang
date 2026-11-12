import { sum, mean, extent, rollup, descending } from "d3";
import { format } from "d3";
import { h, rendered } from "../h.js";
import { Page, Table } from "../layout.js";
import { createStore } from "../store.js";

export function overview() {
  const store = createStore();
  store.dispatch({ type: "toggle", id: "t4" });
  store.dispatch({ type: "assign", id: "t7", who: "grace" });
  const { projects } = store.get();
  const money = format("$,.0f"), pct = format(".1%");
  const byOwner = rollup(projects, (ps) => sum(ps, (p) => p.budget), (p) => p.owner);
  const rows = projects.map((p) => {
    const done = p.tasks.filter((t) => t.done).length;
    return [p.name, p.owner, money(p.budget), pct(done / p.tasks.length), String(mean(p.tasks, (t) => t.estimate).toFixed(1))];
  });
  const [lo, hi] = extent(projects, (p) => p.budget);
  const owners = [...byOwner].sort((a, b) => descending(a[1], b[1])).slice(0, 5);
  return rendered(h(Page, { title: "Overview" },
    h("p", null, `Budgets from ${money(lo)} to ${money(hi)}`),
    h(Table, { columns: ["Owner", "Budget"], rows: owners.map(([o, b]) => [o, money(b)]) }),
    h(Table, { columns: ["Project", "Owner", "Budget", "Done", "Mean estimate"], rows })));
}
