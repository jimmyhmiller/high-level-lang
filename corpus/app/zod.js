import { z } from "zod";
const S = z.object({ name: z.string().min(2), age: z.number().int().positive(), tags: z.array(z.string()).optional() });
console.log(JSON.stringify(S.parse({ name: "ada", age: 36, tags: ["x"] })));
const r = S.safeParse({ name: "a", age: -1 });
console.log(r.success, r.success ? "" : r.error.issues.map((i) => i.path.join(".")).join());
