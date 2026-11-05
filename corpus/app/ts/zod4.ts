import * as z from "../../node_modules/zod/src/v4/index";
const S = z.object({ a: z.string().min(1), b: z.optional(z.number()), c: z.enum(["x", "y"]) });
console.log(JSON.stringify(S.parse({ a: "s", c: "x" })));
console.log(JSON.stringify(S.safeParse({ a: "", c: "q" }).success));
