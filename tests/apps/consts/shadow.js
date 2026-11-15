// The module's own export of the name wins over `export *`.
export * from "./flags.js";
export let isServer = Math.random() < 2;
