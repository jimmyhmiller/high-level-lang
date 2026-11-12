import { object, number, array } from "yup";
console.log(JSON.stringify(object({ n: number().integer(), xs: array(number()) }).cast({ n: "3", xs: ["1"] })));
