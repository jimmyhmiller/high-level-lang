import { mergeDeepRight, lensPath, set, view, equals } from "ramda";
const l = lensPath(["a", "b"]); console.log(JSON.stringify(mergeDeepRight({ a: { b: 1 } }, { a: { c: 2 } })), view(l, set(l, 3, {})), equals([1, { a: 2 }], [1, { a: 2 }]));
