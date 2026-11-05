import { shared } from "../shared.js";
import { chunk } from "lodash-es";
console.log("nested", shared(), chunk([1, 2, 3], 2));
import("../dyn.js").then((m) => console.log("nested dyn", m.value));
