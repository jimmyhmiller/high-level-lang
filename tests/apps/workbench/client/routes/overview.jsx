import React from "react";
import { summarize } from "@workbench/app/domain/model";
import { format, parseISO } from "date-fns";
import "./overview.css";
export default function Overview({ projects }) {
  const summary = summarize(projects);
  return <section className="page overview" data-testid="overview">
    <div className="page-heading"><div><h1>A little clarity. A lot of progress.</h1><p className="subtitle">Your studio at a glance.</p></div><a className="primary new-link" href="#projects">View projects ↗</a></div>
    <div className="metrics">{[["Total projects", summary.count], ["In progress", summary.active], ["Completed", summary.done], ["Portfolio budget", "$" + summary.budget.toLocaleString("en-US")]].map(([label, value]) => <div className="card" key={label}><span>{label}</span><strong>{value}</strong></div>)}</div>
    <div className="overview-grid"><div className="card"><h2>Recent work</h2>{projects.map(p => <div className="recent-project" key={p.id}><div><strong>{p.name}</strong><p>{p.owner} · Updated {format(parseISO(p.updated), "MMM d")}</p></div><span className={"badge " + p.status}>{p.status}</span></div>)}</div>
      <div className="card note"><span className="eyebrow">ROOM TO THINK</span><h2>Make space for<br/>your next good idea.</h2><p>Bring the work into focus. Keep the details close.</p><a href="#reports">Explore reports →</a></div></div>
  </section>;
}
