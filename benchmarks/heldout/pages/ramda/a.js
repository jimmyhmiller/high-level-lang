import { pipe, sortBy, prop, map, join } from "ramda";
console.log(pipe(sortBy(prop("a")), map(prop("b")), join(""))([{ a: 2, b: "y" }, { a: 1, b: "x" }]));
