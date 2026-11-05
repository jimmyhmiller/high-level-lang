import { shared, unusedShared } from "./shared.js";
import { onlyA } from "./onlya.js";
console.log("a", shared(), onlyA);
import("./dyn.js").then((m) => console.log("a dyn", m.default, m.value));
export const fromA = 1;
