import { from, groupBy as groupBy$, mergeMap, map, toArray } from "rxjs";
import { sumBy, meanBy, maxBy, sortBy, round } from "lodash-es";
import { csvFormat, format as d3format } from "d3";
import { formatDistanceStrict, parseISO } from "date-fns";
import { h, rendered } from "../h.js";
import { Page, Table } from "../layout.js";
import { projects } from "../data.js";

export function reports() {
  const tasks = projects.flatMap((p) => p.tasks.map((t) => ({ ...t, project: p.name })));
  let byTag = [];
  from(tasks.flatMap((t) => t.tags.map((tag) => ({ tag, t }))))
    .pipe(groupBy$((x) => x.tag), mergeMap((g) => g.pipe(toArray(), map((xs) => ({ tag: g.key, list: xs.map((x) => x.t) })))), toArray())
    .subscribe((rows) => { byTag = sortBy(rows, "tag"); });
  const rows = byTag.map(({ tag, list }) => [tag, String(list.length), String(sumBy(list, "estimate")), String(round(meanBy(list, "estimate"), 2)),
    maxBy(list, (t) => t.estimate).title, formatDistanceStrict(parseISO("2024-01-01"), parseISO(maxBy(list, (t) => t.due).due))]);
  const csv = csvFormat(tasks.slice(0, 40).map((t) => ({ id: t.id, project: t.project, estimate: t.estimate, due: t.due })));
  if (byTag.length !== 5) throw new Error("expected five tags, got " + byTag.length);
  return rendered(h(Page, { title: "Reports" },
    h(Table, { columns: ["Tag", "Tasks", "Hours", "Mean", "Largest", "Last due"], rows }),
    h("pre", null, csv),
    h("p", null, d3format(",.2f")(sumBy(projects, "budget") / tasks.length))));
}
