import { isServer, tag } from "./flags.js";
export function run() { return isServer ? "DEAD_lazy" : "lazy " + tag; }
