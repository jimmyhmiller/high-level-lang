import React from "react";
import { scaleLinear, scaleBand } from "d3-scale";
import { max, sum } from "d3-array";
import { summarize } from "#domain/model";
import "./reports.css";
export default function Reports({ projects }) {
  const summary = summarize(projects);
  const width = 720, height = 280;
  const x = scaleBand().domain(projects.map(p => p.id)).range([0, width]).padding(0.25);
  const y = scaleLinear().domain([0, max(projects, p => p.budget) || 1]).nice().range([height, 0]);
  return <section className="page reports" data-testid="reports"><div className="page-heading"><div><h1>Perspective on your portfolio.</h1><p className="subtitle">See where your team's investment is going.</p></div></div>
    <div className="card"><h2>Budget by project</h2><svg className="budget-chart" viewBox={"0 0 " + width + " " + (height + 50)} role="img" aria-label="Project budgets">{projects.map(p => <g key={p.id}><rect x={x(p.id)} y={y(p.budget)} width={x.bandwidth()} height={height - y(p.budget)} fill={p.status === "done" ? "#a3b789" : "#42674c"}/><text x={x(p.id) + x.bandwidth() / 2} y={height + 24} textAnchor="middle">{p.name.split(" ")[0]}</text></g>)}</svg></div>
    <div className="card report-summary"><h2>Investment summary</h2><p data-testid="report-total">Total investment: ${sum(projects, p => p.budget).toLocaleString("en-US")}</p><p>{summary.active} active projects · {summary.done} completed</p></div>
  </section>;
}
