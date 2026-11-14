import { Utils } from "./obj.js";
const names = [];
for (const k in Utils) names.push(k);
console.log(names.join());
