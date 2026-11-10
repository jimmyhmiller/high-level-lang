import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { loadProjects, saveProject } from "./api.js";
import mark from "./assets/mark.svg";
import welcome from "./assets/welcome.txt";
import "./shell.css";

const routes = {
  overview: () => import("./routes/overview.jsx"),
  projects: () => import("./routes/projects.jsx"),
  reports: () => import("./routes/reports.jsx")
};
function App() {
  const [route, setRoute] = useState(location.hash.slice(1) || "overview");
  const [page, setPage] = useState(null);
  const [projects, setProjects] = useState([]);
  const [error, setError] = useState("");
  const [theme, setTheme] = useState(localStorage.getItem("workbench-theme") || "light");
  useEffect(() => {
    const changed = () => setRoute(location.hash.slice(1) || "overview");
    addEventListener("hashchange", changed);
    loadProjects().then(setProjects).catch(e => setError(e.message));
    return () => removeEventListener("hashchange", changed);
  }, []);
  useEffect(() => {
    let current = true;
    setPage(null);
    const load = routes[route] || routes.overview;
    load().then(mod => { if (current) setPage({ Component: mod.default }); }).catch(e => { if (current) setError(e.message); });
    return () => { current = false; };
  }, [route]);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("workbench-theme", theme);
  }, [theme]);
  async function save(input, id) {
    const saved = await saveProject(input, id);
    setProjects(previous => id ? previous.map(p => p.id === id ? saved : p) : [...previous, saved]);
  }
  return <div className="shell">
    <aside><a className="brand" href="#overview"><img src={mark} alt=""/>Workbench</a>
      <p className="workspace-label">STUDIO NORTH / WORKSPACE</p>
      <nav aria-label="Main navigation">{Object.keys(routes).map(name => <a key={name} href={"#" + name} aria-current={route === name ? "page" : undefined}>{name[0].toUpperCase() + name.slice(1)}</a>)}</nav>
      <button className="theme" onClick={() => setTheme(theme === "light" ? "dark" : "light")}>Switch theme</button>
      <small>Built with high-level policies</small>
    </aside>
    <main><header><span>{welcome}</span><span className="avatar">MN</span></header>
      {error && <div role="alert">{error}<button onClick={() => { setError(""); setRoute("overview"); location.hash = "overview"; }}>Dismiss</button></div>}
      {page ? <page.Component projects={projects} onSave={save}/> : <p role="status">Loading workspace…</p>}
    </main>
  </div>;
}
createRoot(document.getElementById("app")).render(<App/>);
