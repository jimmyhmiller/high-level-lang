import { z } from "./lib/index.js";
import { greet, shout } from "./greet.js";
const api = z;
console.log(api.string(), Object.keys(api).length, greet("a"), shout("b"));
