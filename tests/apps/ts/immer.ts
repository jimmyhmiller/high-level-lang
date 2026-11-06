import { produce, enableMapSet, enablePatches, produceWithPatches, freeze, original, current } from "../../node_modules/immer/src/immer";
enableMapSet(); enablePatches();
const base = { a: 1, list: [1, 2], m: new Map([["k", 1]]), nested: { x: 1 } };
const next = produce(base, (d) => { d.a = 2; d.list.push(3); d.m.set("j", 2); d.nested.x = 5; });
console.log(JSON.stringify([next.a, next.list, [...next.m], next.nested, base.a, Object.isFrozen(next)]));
console.log(JSON.stringify(produceWithPatches({ x: 1 }, (d) => { d.x = 2; })));
