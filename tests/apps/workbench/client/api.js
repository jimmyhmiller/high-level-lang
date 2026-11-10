import { Portfolio, ProjectInput, Project } from "#domain/model";
async function request(path, options) {
  const response = await fetch("/api/" + path, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Request failed");
  return data;
}
export async function loadProjects() { return Portfolio.parse(await request("projects")); }
export async function saveProject(input, id) {
  const value = ProjectInput.parse(input);
  return Project.parse(await request("projects" + (id ? "/" + encodeURIComponent(id) : ""), {
    method: id ? "PUT" : "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(value)
  }));
}
