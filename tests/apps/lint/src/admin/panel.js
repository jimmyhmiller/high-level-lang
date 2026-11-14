import { query } from "../db/query.js";
import { fmt } from "../ui/format.js";

export function open() {
  debugger;
  return fmt(query("admin"));
}
