import { hashKey, replaceEqualDeep, matchQuery, notifyManager } from "@tanstack/query-core";
const a = { x: [1] }; console.log(hashKey(["k", { b: 1, a: 2 }]), replaceEqualDeep(a, { x: [1] }) === a, typeof matchQuery, typeof notifyManager.batch);
