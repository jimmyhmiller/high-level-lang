import fs from "node:fs";
import { join, basename } from "path";
import * as os from "os";
const cp = require("child_process");
console.log(typeof fs.readFileSync, join("a", "b"), basename("/x/y.txt"), typeof os.platform, typeof cp.spawn);
import("node:url").then((u) => console.log(typeof u.pathToFileURL));
