// Statement-level hot updates: an edit to a function, a value or a class's methods is patched into
// the running modules, which keep their state; nothing here accepts updates, so a module that has
// to run again makes the page reload, unless `registry.js`, which does, is between them.
import { bump, count } from "./counter.js";
import anon, { greeting } from "./words.js";
import { Counter, Twice } from "./shapes.js";
import * as registry from "./registry.js";

globalThis.tick = () => bump();
globalThis.show = () => greeting(count());
globalThis.counter = new Counter();
globalThis.twice = new Twice();
globalThis.anon = () => anon();
globalThis.vault = new registry.Vault();
globalThis.newVault = () => new registry.Vault();
globalThis.dispatch = () => registry.store.dispatch();
globalThis.handle = (k) => registry.handlers[k]();
console.log("main ran");
