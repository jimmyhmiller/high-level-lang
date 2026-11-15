// A constant made of an imported one is not one: each file's are found by itself.
import { isServer } from "./flags.js";
export const derived = isServer;
