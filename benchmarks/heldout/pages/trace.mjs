import { registerHooks } from "node:module";
import { writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
const seen = new Set();
registerHooks({ load(url, ctx, next) { if (url.startsWith("file:")) seen.add(fileURLToPath(url)); return next(url, ctx); } });
process.on("exit", () => writeFileSync(process.env.TRACE_OUT, JSON.stringify([...seen])));
