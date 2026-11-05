import area, { PI, inc, counter, Shape } from "./feat/math.js";
import * as math from "./feat/math.js";
import Anon, { own, areaOf, TAU_ISH, mathNs, inc as inc2 } from "./feat/more.js";
import * as more from "./feat/more.js";
import "./feat/effects.js";
import util, { add, named } from "./feat/util.cjs";
import * as utilNs from "./feat/util.cjs";
import data from "./feat/data.json";
import { viaA } from "./feat/circ_b.js";
import requiresEsm from "./feat/cjs_requires_esm.cjs";

const out = [];
out.push(area(2), PI, inc(), counter, inc2(), counter, new Shape().name());
out.push(math.PI, math.inc(), Object.keys(math).sort().join());
out.push(new Anon().hello(), own, areaOf(1), TAU_ISH, mathNs.PI, Object.keys(more).sort().join());
out.push(globalThis.__log.join());
out.push(add(1, 2), named, util.named, utilNs.add(2, 2), typeof utilNs.default);
out.push(util.me());
out.push(data.name, data.items.length);
out.push(viaA());
out.push(requiresEsm.join());
let { a: renamed, ...rest } = { a: 1, b: 2 };
function shadow(PI) { return { PI, renamed, rest }; }
out.push(JSON.stringify(shadow(9)));
class Local { #p = 1; static s = 2; get p() { return this.#p; } }
out.push(new Local().p, Local.s);
const tag = (s, ...v) => s.raw.join("|") + v.join();
out.push(tag`x${1}y${2}z`, `t${1 + 1}`);
async function later() { await 0; return "async"; }
function* gen() { yield 1; yield* [2]; }
out.push([...gen()].join());
later().then((v) => { console.log(v); });
if (typeof SERVER !== "undefined") out.push("server?", SERVER);
out.push(typeof process.env.NODE_ENV);
import("./feat/esm_for_cjs.js").then((m) => console.log(m.fromEsm, m.default));
console.log(JSON.stringify(out));
