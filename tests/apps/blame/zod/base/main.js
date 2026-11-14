import { object, string } from "zod/v4";
const User = object({ name: string().min(2) });
console.log(User.parse({ name: "ada" }).name);
