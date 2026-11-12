import * as v from "valibot";
const S = v.object({ name: v.pipe(v.string(), v.minLength(2)), age: v.pipe(v.number(), v.integer(), v.minValue(0)), email: v.optional(v.pipe(v.string(), v.email())), role: v.picklist(["a", "b"]) });
const ok = v.safeParse(S, { name: "Ann", age: 3, role: "a" });
const bad = v.safeParse(S, { name: "A", age: 1.5, email: "x", role: "c" });
console.log(ok.success, JSON.stringify(ok.output), bad.success, bad.issues.map(i => i.kind + ":" + i.type + ":" + (i.path?.map(p => p.key).join(".") ?? "")).join(","), JSON.stringify(v.flatten(bad.issues)));
