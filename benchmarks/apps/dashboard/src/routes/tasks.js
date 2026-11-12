import { z } from "zod";
import { orderBy, chunk, partition, uniq } from "lodash-es";
import { produce, enableMapSet } from "immer";
import { h, rendered } from "../h.js";
import { Page, Table } from "../layout.js";
import { createStore } from "../store.js";
import { Task } from "../data.js";

const Edit = Task.pick({ title: true, estimate: true, tags: true }).extend({ note: z.string().max(140).optional() });

export function tasks() {
  enableMapSet();
  const store = createStore();
  for (const id of ["t1", "t2", "t30", "t31"]) store.dispatch({ type: "toggle", id });
  store.dispatch({ type: "filter", text: "cache" });
  const { projects, filter } = store.get();
  const all = projects.flatMap((p) => p.tasks.map((t) => ({ ...t, project: p.name })));
  const [open, closed] = partition(all.filter((t) => t.title.includes(filter)), (t) => !t.done);
  const edits = [{ title: "Make it fast", estimate: 3, tags: ["ui"] }, { title: "x", estimate: 99, tags: [] }, { title: "Docs", estimate: 2, tags: ["docs"], note: "soon" }]
    .map((e) => Edit.safeParse(e)).map((r) => (r.success ? "ok" : r.error.issues.map((i) => i.path.join(".")).join(",")));
  const seen = produce(new Set(), (s) => { for (const t of open) s.add(t.assignee || "nobody"); });
  const pages = chunk(orderBy(open, ["estimate", "id"], ["desc", "asc"]), 10);
  return rendered(h(Page, { title: "Tasks" },
    h("p", null, `${open.length} open, ${closed.length} done; edits: ${edits.join(" / ")}; people: ${uniq([...seen]).sort().join(", ")}`),
    pages.map((page, i) => h(Table, { key: i, columns: ["Task", "Project", "Estimate", "Due", "Tags"],
      rows: page.map((t) => [t.title, t.project, String(t.estimate), t.due, t.tags.join(" ")]) }))));
}
