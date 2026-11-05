console.log("re-exporting module");
export { used } from "./used.js";
export * from "./star.js";
import { viaLocal } from "./local.js";
export { viaLocal };
export { other } from "./other.js";
