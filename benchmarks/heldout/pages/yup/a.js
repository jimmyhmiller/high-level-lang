import { string } from "yup";
console.log(string().email().isValidSync("a@b.co"), string().min(3).isValidSync("ab"));
