// Two `export *` with the name: neither is exported (an ambiguous star export).
export * from "./flags.js";
export * from "./other.js";
export const fine = 0;
