import { format } from "./util.js";
import { report } from "./report.js";
document.addEventListener("click", () => {
  console.log(format(report()));
});
console.log(format("admin"));
