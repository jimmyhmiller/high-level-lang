import x = require("./cjs-dep.cjs");
import y = x.prop;
import unused = x.gone;
console.log(x, y);
export = { x };
