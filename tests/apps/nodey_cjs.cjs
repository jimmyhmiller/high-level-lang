const path = require("path");
module.exports = { sep: path.sep, base: path.basename("/a/b.js") };
console.log(module.exports.base);
