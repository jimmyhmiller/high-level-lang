import { QueryClient, QueryObserver, hashKey, replaceEqualDeep, matchQuery } from "@tanstack/query-core";
const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
const log = [];
const res = await qc.fetchQuery({ queryKey: ["todo", { id: 2 }], queryFn: async ({ queryKey }) => ({ id: queryKey[1].id, title: "t" + queryKey[1].id }) });
log.push(JSON.stringify(res), hashKey(["a", { z: 1, a: 2 }]), JSON.stringify(qc.getQueryData(["todo", { id: 2 }])));
const a = { x: [1, 2], y: { z: 1 } }; const b = replaceEqualDeep(a, { x: [1, 2], y: { z: 2 } }); log.push(a.x === b.x, a.y === b.y);
qc.setQueryData(["n"], 5); log.push(qc.getQueryCache().findAll().length, matchQuery({ queryKey: ["todo"] }, qc.getQueryCache().find({ queryKey: ["todo", { id: 2 }] })));
qc.clear(); console.log(log.join("|"));
