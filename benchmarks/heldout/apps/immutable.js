import { Map, List, Set, Record, fromJS, Seq, OrderedMap, is } from "immutable";
const m = Map({ a: 1, b: 2 }).set("c", 3).update("a", x => x + 10);
const l = List([1, 2, 3]).push(4).map(x => x * x).filter(x => x > 1);
const R = Record({ x: 0, y: 0 }); const p = new R({ x: 3 });
const deep = fromJS({ a: { b: [1, 2, { c: 3 }] } }).setIn(["a", "b", 2, "c"], 9);
console.log(JSON.stringify(m), JSON.stringify(l), Set([1, 1, 2]).size, p.x + p.y, JSON.stringify(deep.toJS()),
  Seq([1, 2, 3, 4, 5]).filter(x => x % 2).map(x => x * 3).toArray().join(","), OrderedMap([["z", 1], ["a", 2]]).keySeq().join(""), is(Map({a: List([1])}), Map({a: List([1])})));
