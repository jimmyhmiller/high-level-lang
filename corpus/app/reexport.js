import * as star from "./feat2/star.js";
import { renamed, b, whole } from "./feat2/named.js";
console.log(Object.keys(star).sort().join(), star.a, star.own, renamed, b, Object.keys(whole).sort().join());
const d = require("./feat2/destruct.js");
console.log(JSON.stringify(d.get()), d.p, d.r);
import("./feat2/destruct.js").then((m) => console.log(m.first, m.third));
