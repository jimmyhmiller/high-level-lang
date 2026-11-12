import { Map, List } from "immutable";
console.log(JSON.stringify(Map({ a: 1 }).set("b", 2)), List([1, 2]).push(3).size);
