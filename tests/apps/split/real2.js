import { chunk, sortBy } from "lodash-es";
import { Subject } from "rxjs";
const s = new Subject();
s.subscribe((v) => console.log(JSON.stringify(chunk(sortBy(v), 1))));
s.next([2, 1]);
const again = await import("./real-dyn.js");
console.log(again.summary([1]));
