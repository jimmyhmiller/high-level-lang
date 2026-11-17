// Vite's builds, for tools/bench.py: Vite 8's own build (Rolldown underneath), as an application
// would run it. Prints JSON.
//   once:  a build in this process, then exit (bench.py times the process from outside)
//   watch: `build.watch`, Vite's incremental build: the first build, then after each edit to one
//          module, from the moment the edit is written until Vite says the bundle is written again
//          (noticing the edit included, as Turbopack's rebuild is measured)
//   usage: node bench-vite.mjs VITE-PACKAGE-DIR ROOT ENTRY MODULE once|watch EDITS [--minify]
import fs from "fs";
import path from "path";
import { pathToFileURL } from "url";

const [pkg, root, entry, module, mode, edits, ...flags] = process.argv.slice(2);
const { build } = await import(pathToFileURL(path.join(pkg, "dist", "node", "index.js")).href);
const file = path.join(root, module);
const original = fs.readFileSync(file, "utf8");

const write = (text) => {
  fs.writeFileSync(file + ".bench-tmp", text);
  fs.renameSync(file + ".bench-tmp", file);
};

const config = (watch) => ({
  configFile: false,
  logLevel: "silent",
  mode: "production",
  root,
  base: "./",
  build: {
    outDir: path.join(root, "out", "vite"),
    emptyOutDir: true,
    minify: flags.includes("--minify"),
    sourcemap: false,
    target: "esnext",
    reportCompressedSize: false,
    copyPublicDir: false,
    // The edited module is in a package: Vite's watcher leaves node_modules out unless told not to.
    watch: watch ? { exclude: [], chokidar: { ignored: [] } } : null,
    rolldownOptions: { input: path.join(root, entry), output: { format: "es", entryFileNames: "[name].js" } },
  },
});

if (mode === "once") {
  await build(config(false));
  process.exit(0);
}

const watcher = await build(config(true));
// Each bundle written, in turn.
let waiting = null;
const ended = () => new Promise((resolve, reject) => { waiting = { resolve, reject }; });
watcher.on("event", (e) => {
  if (e.code === "BUNDLE_END" && e.result) e.result.close?.();
  if (!waiting) return;
  if (e.code === "BUNDLE_END") { const w = waiting; waiting = null; w.resolve(); }
  else if (e.code === "ERROR") { const w = waiting; waiting = null; w.reject(e.error); }
});
let t = performance.now();
await ended();
const first = performance.now() - t;
const rebuilds = [];
let missing = 0;
for (let i = 0; i < Number(edits); i++) {
  // Let the watcher settle after the build it just finished, so the edit is a new event.
  await new Promise((r) => setTimeout(r, 200));
  const marker = `vite edit ${i}`;
  const done = ended();
  t = performance.now();
  write(`console.log("${marker}");\n` + original);
  const timeout = setTimeout(() => { if (waiting) waiting.reject(new Error("vite never rebuilt after the edit")); }, 30000);
  await done;
  clearTimeout(timeout);
  rebuilds.push(performance.now() - t);
  const out = fs.readdirSync(path.join(root, "out", "vite")).filter((f) => f.endsWith(".js"))
    .map((f) => fs.readFileSync(path.join(root, "out", "vite", f), "utf8")).join("\n");
  // A package that says it has no side effects may let Rolldown drop a statement made only for its
  // effect: the rebuild happened all the same, and is counted, but said so.
  if (!out.includes(marker)) missing++;
}
write(original);
await watcher.close();
console.log(JSON.stringify({ first, rebuilds, missing }));
process.exit(0);
