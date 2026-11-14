import { z } from "./lib/index.js";
import { greet, shout } from "./greet.js";
const api = z;
console.log(api.string(), greet("a"), shout("b"));
