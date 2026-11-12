import { picklist, array, safeParse, flatten, email, pipe, string } from "valibot";
const r = safeParse(array(picklist(["a", "b"])), ["a", "c"]); const e = safeParse(pipe(string(), email()), "no");
console.log(r.success, JSON.stringify(flatten(r.issues)), e.issues[0].type);
