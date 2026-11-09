// esbuild's own incremental builds, for tools/bench.py: a context's first build, then a rebuild
// after each edit to one module, each timed in the process. Prints JSON.
//   usage: node bench-esbuild.mjs ESBUILD-PACKAGE-DIR ROOT ENTRY MODULE EDITS [--minify]
import { createRequire } from "module";
import fs from "fs";
import path from "path";

const [pkg, root, entry, module, edits, ...flags] = process.argv.slice(2);
const esbuild = createRequire(path.join(pkg, "package.json"))(pkg);
const file = path.join(root, module);
const original = fs.readFileSync(file, "utf8");

const write = (text) => {
  fs.writeFileSync(file + ".bench-tmp", text);
  fs.renameSync(file + ".bench-tmp", file);
};

const ctx = await esbuild.context({
  entryPoints: [path.join(root, entry)],
  bundle: true,
  outfile: path.join(root, "out", "esbuild.js"),
  minify: flags.includes("--minify"),
  logLevel: "silent",
  absWorkingDir: root,
});
let t = performance.now();
await ctx.rebuild();
const first = performance.now() - t;
const rebuilds = [];
for (let i = 0; i < Number(edits); i++) {
  write(`console.log("esbuild edit ${i}");\n` + original);
  t = performance.now();
  await ctx.rebuild();
  rebuilds.push(performance.now() - t);
}
write(original);
await ctx.dispose();
console.log(JSON.stringify({ first, rebuilds }));
