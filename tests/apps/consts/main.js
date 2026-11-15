import { isServer, level, tag, shown, changing } from "./flags.js";
import * as flags from "./flags.js";
import { late } from "./late.js";
import { derived } from "./again.js";
import { isServer as starred } from "./star.js";
import { server, level as lvl } from "./from.js";
import * as amb from "./ambiguous.js";
import { isServer as shadowed } from "./shadow.js";

if (isServer) console.log("DEAD_named");
if (flags.isServer) console.log("DEAD_namespace");
if (starred) console.log("DEAD_star");
if (server) console.log("DEAD_from");
if (!shown) console.log("DEAD_renamed");
console.log(level * 10 + lvl, tag, changing, late, derived, shadowed, amb.fine);
console.log(isServer ?? "nullish", flags.level, typeof flags.isServer, amb.isServer);
function f(x) { return (isServer ?? x.isServer) ? "DEAD_coalesce" : "live"; }
console.log(f({ isServer: true }));
import("./lazy.js").then((m) => console.log(m.run()));
