import { z } from "../../node_modules/zod/src/v3/index";
const S = z.object({ a: z.string().min(1), b: z.number().optional(), c: z.enum(["x", "y"]), d: z.array(z.union([z.string(), z.number()])) });
console.log(JSON.stringify(S.parse({ a: "s", c: "x", d: [1, "2"] })));
console.log(JSON.stringify(S.safeParse({ a: "", c: "q", d: [{}] })));
