import * as R from "ramda";
const people = [{ n: "a", age: 30 }, { n: "b", age: 20 }, { n: "c", age: 40 }];
const out = [
  R.pipe(R.sortBy(R.prop("age")), R.map(R.prop("n")), R.join(""))(people),
  R.sum(R.range(0, 100)), JSON.stringify(R.groupBy(x => x % 3 ? "y" : "n", R.range(0, 10))),
  JSON.stringify(R.mergeDeepRight({ a: { b: 1, c: 2 } }, { a: { c: 3 } })),
  R.compose(R.toUpper, R.reverse)("hello"), JSON.stringify(R.zip([1,2,3], ["a","b","c"])),
  R.equals({ a: [1, { b: 2 }] }, { a: [1, { b: 2 }] }), JSON.stringify(R.lensPath(["a", "b"]) && R.set(R.lensPath(["a","b"]), 9, {a:{b:1}})),
  JSON.stringify(R.uniqBy(Math.abs, [-1, 1, 2, -2, 3])), R.curry((a, b, c) => a + b * c)(1)(2)(3),
];
console.log(Object.keys(R).length, out.join("|"));
