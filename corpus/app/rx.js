import { from, of, map, filter, reduce, mergeMap, take, toArray } from "rxjs";
from([1, 2, 3, 4, 5]).pipe(filter((x) => x % 2), map((x) => x * 10), reduce((a, b) => a + b, 0)).subscribe((v) => console.log("sum", v));
of(1, 2, 3).pipe(mergeMap((x) => of(x, x + 100)), take(4), toArray()).subscribe((a) => console.log(a.join()));
