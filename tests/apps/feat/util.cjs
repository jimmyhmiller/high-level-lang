const secret = require("./util2.cjs");
exports.add = (a, b) => a + b + secret.zero;
exports.me = function () { return this === exports; };
module.exports.named = "cjs-named";
