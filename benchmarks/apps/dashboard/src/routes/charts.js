import { scaleLinear, scaleBand, scaleTime, line, area, arc, pie, curveMonotoneX, schemeTableau10, max, timeMonth } from "d3";
import { h, rendered } from "../h.js";
import { Page } from "../layout.js";
import { projects } from "../data.js";

export function charts() {
  const width = 640, height = 240;
  const budgets = projects.map((p, i) => ({ x: i, y: p.budget }));
  const x = scaleLinear().domain([0, budgets.length - 1]).range([0, width]);
  const y = scaleLinear().domain([0, max(budgets, (d) => d.y)]).nice().range([height, 0]);
  const path = line().x((d) => x(d.x)).y((d) => y(d.y)).curve(curveMonotoneX)(budgets);
  const fill = area().x((d) => x(d.x)).y0(height).y1((d) => y(d.y)).curve(curveMonotoneX)(budgets);
  const band = scaleBand().domain(projects.map((p) => p.id)).range([0, width]).padding(0.2);
  const months = scaleTime().domain([new Date(2024, 0, 1), new Date(2024, 11, 31)]).range([0, width]);
  const ticks = months.ticks(timeMonth.every(1)).map((d) => [months(d).toFixed(1), months.tickFormat()(d)]);
  const slices = pie().value((d) => d.value)(["ui", "api", "infra", "docs", "research"].map((tag) => ({
    tag, value: projects.flatMap((p) => p.tasks).filter((t) => t.tags.includes(tag)).length })));
  const wedge = arc().innerRadius(40).outerRadius(90);
  return rendered(h(Page, { title: "Charts" },
    h("svg", { width, height, viewBox: `0 0 ${width} ${height}` },
      h("path", { d: fill, fill: schemeTableau10[0], opacity: 0.3 }),
      h("path", { d: path, stroke: schemeTableau10[0], fill: "none" }),
      projects.map((p) => h("rect", { key: p.id, x: band(p.id), width: band.bandwidth(), y: y(p.budget), height: height - y(p.budget), fill: schemeTableau10[1] })),
      ticks.map(([at, label]) => h("text", { key: label, x: at, y: height - 2 }, label))),
    h("svg", { width: 200, height: 200 },
      h("g", { transform: "translate(100,100)" }, slices.map((s, i) => h("path", { key: s.data.tag, d: wedge(s), fill: schemeTableau10[i] }))))));
}
