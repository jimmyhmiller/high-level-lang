import { createServer } from "node:http";
import { readFile, writeFile, mkdir, rename } from "node:fs/promises";
import { resolve, dirname, extname, sep } from "node:path";
import { randomUUID } from "node:crypto";
import { Portfolio, ProjectInput, summarize } from "#domain/model";
import seed from "../domain/seed.json";

const dataFile = resolve(process.env.WORKBENCH_DATA || "out/workbench/data/projects.json");
const publicRoot = resolve(process.env.WORKBENCH_PUBLIC || "out/workbench/public");
const mime = { ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml", ".json": "application/json", ".map": "application/json" };
let projects;
try { projects = Portfolio.parse(JSON.parse(await readFile(dataFile, "utf8"))); }
catch (error) { if (error.code !== "ENOENT") throw error; projects = Portfolio.parse(seed); }
let transaction = Promise.resolve();
function json(response, status, value) {
  response.writeHead(status, { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" });
  response.end(JSON.stringify(value));
}
async function input(request) {
  let size = 0, chunks = [];
  for await (const chunk of request) {
    size += chunk.length;
    if (size > 65536) throw Object.assign(new Error("Request body too large"), { status: 413 });
    chunks.push(chunk);
  }
  try { return JSON.parse(Buffer.concat(chunks).toString("utf8")); }
  catch { throw Object.assign(new Error("Invalid JSON"), { status: 400 }); }
}
async function persist(next) {
  await mkdir(dirname(dataFile), { recursive: true });
  const temporary = dataFile + "." + randomUUID() + ".tmp";
  await writeFile(temporary, JSON.stringify(next, null, 2));
  await rename(temporary, dataFile);
  projects = next;
}
async function handle(request, response) {
  const url = new URL(request.url, "http://localhost");
  if (url.pathname === "/api/projects" && request.method === "GET") return json(response, 200, projects);
  if (url.pathname === "/api/summary" && request.method === "GET") return json(response, 200, summarize(projects));
  if ((url.pathname === "/api/projects" && request.method === "POST") || (url.pathname.startsWith("/api/projects/") && request.method === "PUT")) {
    const checked = ProjectInput.safeParse(await input(request));
    if (!checked.success) return json(response, 422, { error: "Invalid project", issues: checked.error.issues });
    const id = request.method === "PUT" ? decodeURIComponent(url.pathname.slice("/api/projects/".length)) : randomUUID();
    // Serialize mutations and persistence together; failed writes leave the previous state intact.
    const change = transaction.then(async () => {
      if (request.method === "PUT" && !projects.some(p => p.id === id)) return json(response, 404, { error: "Project not found" });
      const value = { ...checked.data, id, updated: new Date().toISOString() };
      await persist(request.method === "PUT" ? projects.map(p => p.id === id ? value : p) : [...projects, value]);
      json(response, request.method === "POST" ? 201 : 200, value);
    });
    transaction = change.catch(() => {});
    return change;
  }
  if (url.pathname.startsWith("/api/")) return json(response, 404, { error: "Unknown endpoint" });
  if (request.method !== "GET" && request.method !== "HEAD") return json(response, 405, { error: "Method not allowed" });
  const relative = url.pathname === "/" ? "index.html" : url.pathname.startsWith("/static/") ? decodeURIComponent(url.pathname.slice(8)) : "";
  const file = resolve(publicRoot, relative);
  if (!relative || !file.startsWith(publicRoot + sep)) return json(response, 404, { error: "Not found" });
  try {
    const data = await readFile(file);
    response.writeHead(200, { "Content-Type": mime[extname(file)] || "application/octet-stream", "Cache-Control": "no-cache", "X-Content-Type-Options": "nosniff" });
    response.end(request.method === "HEAD" ? undefined : data);
  } catch (error) {
    if (error.code === "ENOENT" || error.code === "EISDIR") return json(response, 404, { error: "Not found" });
    throw error;
  }
}
const server = createServer((request, response) => {
  handle(request, response).catch(error => {
    console.error(error);
    if (!response.headersSent) json(response, error.status || 500, { error: error.status ? error.message : "Internal server error" });
    else response.destroy();
  });
});
server.listen(Number(process.env.PORT || 8000), "127.0.0.1", () => {
  console.log("Workbench http://127.0.0.1:" + server.address().port);
});
for (const signal of ["SIGTERM", "SIGINT"]) process.on(signal, () => server.close());
