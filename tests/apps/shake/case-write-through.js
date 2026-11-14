import * as ns from "./lib.js";
const api = ns;
try { api.alpha = () => "replaced"; } catch (e) { console.log(e.constructor.name); }
console.log(api.alpha());
