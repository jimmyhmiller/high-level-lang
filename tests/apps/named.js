import { chunk, groupBy, sortBy, cloneDeep, merge, uniq, camelCase, debounce, get, isEqual } from "lodash-es";

const data = [{ n: "ada", age: 36 }, { n: "bob", age: 25 }, { n: "cy", age: 36 }];
console.log(JSON.stringify(chunk([1, 2, 3, 4, 5], 2)));
console.log(JSON.stringify(groupBy(data, "age")));
console.log(JSON.stringify(sortBy(data, ["age", "n"])));
const copy = cloneDeep(data);
copy[0].n = "changed";
console.log(data[0].n, copy[0].n);
console.log(JSON.stringify(merge({ a: { b: 1 } }, { a: { c: 2 } })));
console.log(JSON.stringify(uniq([1, 1, 2, 3, 3])));
console.log(camelCase("hello big world"), get({ a: { b: [1, 2] } }, "a.b[1]"), isEqual({ x: 1 }, { x: 1 }));
console.log(typeof debounce(() => 1, 10));
