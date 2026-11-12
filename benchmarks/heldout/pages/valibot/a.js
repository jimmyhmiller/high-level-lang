import { object, string, number, safeParse, pipe, minLength } from "valibot";
console.log(JSON.stringify(safeParse(object({ n: pipe(string(), minLength(2)), a: number() }), { n: "x", a: 1 }).issues.map(i => i.type)));
