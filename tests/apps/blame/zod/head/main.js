import { z } from "zod/v4";
const schemas = z;
const User = schemas.object({ name: schemas.string().min(2) });
console.log(User.parse({ name: "ada" }).name, Object.keys(schemas).length > 0);
