import * as yup from "yup";
const schema = yup.object({ name: yup.string().required().min(2), age: yup.number().positive().integer().max(150), email: yup.string().email(), tags: yup.array(yup.string()).min(1) });
const out = [];
out.push(JSON.stringify(schema.cast({ name: "Al", age: "42", tags: ["a"] })));
try { schema.validateSync({ name: "A", age: -1, email: "nope", tags: [] }, { abortEarly: false }); } catch (e) { out.push(e.errors.join(";")); }
out.push(schema.isValidSync({ name: "Bob", age: 3, tags: ["x"] }), JSON.stringify(schema.describe().fields.age.tests.map(t => t.name)));
console.log(out.join("|"));
