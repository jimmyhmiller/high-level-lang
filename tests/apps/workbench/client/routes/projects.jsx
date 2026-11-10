import React, { useState } from "react";
import { statuses } from "#domain/model";
import "./projects.css";
export default function Projects({ projects, onSave }) {
  const [filter, setFilter] = useState("all");
  const [query, setQuery] = useState("");
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const shown = projects.filter(p => (filter === "all" || p.status === filter) && p.name.toLowerCase().includes(query.toLowerCase()));
  async function submit(event) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setSaving(true); setError("");
    try {
      await onSave({ name: form.get("name"), owner: form.get("owner"), budget: Number(form.get("budget")), status: form.get("status") });
      setEditing(false);
    } catch (e) { setError(e.message); } finally { setSaving(false); }
  }
  async function complete(project) {
    try { await onSave({ name: project.name, owner: project.owner, budget: project.budget, status: "done" }, project.id); }
    catch (e) { setError(e.message); }
  }
  return <section className="page projects" data-testid="projects"><div className="page-heading"><div><h1>Projects</h1><p className="subtitle">The work, the people, and what comes next.</p></div><button className="primary" onClick={() => setEditing(!editing)}>New project</button></div>
    {error && <p role="alert">{error}</p>}
    {editing && <form className="card project-form" onSubmit={submit}><h2>Create project</h2><label>Name<input name="name" required minLength="2"/></label><label>Owner<input name="owner" required/></label><label>Budget<input name="budget" type="number" min="0" defaultValue="1000" required/></label><label>Status<select name="status">{statuses.map(s => <option key={s}>{s}</option>)}</select></label><button className="primary" disabled={saving}>{saving ? "Saving…" : "Save project"}</button></form>}
    <div className="filters"><input aria-label="Search projects" placeholder="Search projects…" value={query} onChange={e => setQuery(e.target.value)}/><select aria-label="Filter status" value={filter} onChange={e => setFilter(e.target.value)}><option value="all">All statuses</option>{statuses.map(s => <option key={s}>{s}</option>)}</select><span>{shown.length} projects</span></div>
    <div className="card table-wrap"><table><thead><tr><th>Project</th><th>Owner</th><th>Status</th><th>Budget</th><th>Action</th></tr></thead><tbody>{shown.map(p => <tr key={p.id}><td>{p.name}</td><td>{p.owner}</td><td>{p.status}</td><td>${p.budget.toLocaleString("en-US")}</td><td>{p.status !== "done" && <button aria-label={"Complete " + p.name} onClick={() => complete(p)}>Complete</button>}</td></tr>)}</tbody></table></div>
  </section>;
}
