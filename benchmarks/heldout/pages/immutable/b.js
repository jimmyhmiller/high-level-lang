import { Record, Seq, OrderedMap, fromJS } from "immutable";
const R = Record({ x: 1 }); console.log(new R().x, Seq([1, 2, 3]).map(x => x * 2).toArray().join(","), OrderedMap({ z: 1, a: 2 }).keySeq().join(""), JSON.stringify(fromJS({ a: [1] }).toJS()));
