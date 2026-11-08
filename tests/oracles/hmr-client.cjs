// Runs a development bundle in Node, connected to its server; lines on stdin are expressions to evaluate.
const fs = require("fs"), vm = require("vm"), readline = require("readline");
globalThis.require = require;
globalThis.__hmr_reloaded = (why) => console.log("RELOAD " + why);
vm.runInThisContext(fs.readFileSync(process.argv[2], "utf8"), { filename: process.argv[2] });
readline.createInterface({ input: process.stdin }).on("line", (line) => {
  try { console.log("=> " + vm.runInThisContext(line)); } catch (e) { console.log("!! " + e.message); }
});
