// CommonJS modules whose bodies a minifier changes at their end: an early `return` with code after
// it, and a bare `return` last. Built in parts, their bodies must come out as they do whole.
const early = require("./cjsret/early.js");
const bare = require("./cjsret/bare.js");
console.log(early.total(4), bare.label("x"));
