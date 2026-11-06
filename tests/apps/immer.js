import { produce } from "immer";
const a = { list: [{ n: 1 }], other: { k: 1 } };
const b = produce(a, (d) => { d.list[0].n = 2; d.list.push({ n: 3 }); });
console.log(JSON.stringify(a), JSON.stringify(b), a.other === b.other);
