import { query } from "../db/query.js";
import { fmt } from "./format.js";

export function render(c, title) {
  console.log("render", title);
  document.body.textContent = fmt(query(c.publicUrl));
}

export function unusedHelper() {
  return "nothing reads this";
}
