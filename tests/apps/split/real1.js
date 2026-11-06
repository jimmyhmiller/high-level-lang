import { chunk, groupBy, uniq } from "lodash-es";
console.log(JSON.stringify(chunk([1, 2, 3, 4], 2)), JSON.stringify(uniq([1, 1, 2])));
const heavy = await import("./real-dyn.js");
console.log(heavy.summary([3, 1, 2]), JSON.stringify(groupBy([1, 2, 3], (x) => x % 2)));
