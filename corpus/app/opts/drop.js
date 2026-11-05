import { chunk } from "lodash-es";
function noisy(x) { console.log("drop me", x); debugger; return x * 2; }
const kept = noisy(2);
console.info?.("maybe");
var lib = { factory: (x) => x };
function makeThing(x) { return { x }; }
const unusedPure = makeThing(1);
const unusedPure2 = lib.factory(2);
process.stdout.write(JSON.stringify([kept, chunk([1, 2, 3], 2)]) + "\n");
