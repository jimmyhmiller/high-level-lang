import { format } from "./util.js";
document.addEventListener("click", async () => {
  const { report } = await import("./report.js");
  console.log(format(report()));
});
console.log(format("admin"));
