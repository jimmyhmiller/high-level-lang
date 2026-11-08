// An app for hot module replacement: state lives here, and the view is replaced under it.
import { render, label } from "./view.js";
import * as shapes from "./shapes.js";
import config from "./config.cjs";

let clicks = 0;
globalThis.click = () => {
  clicks += 1;
  return render(clicks);
};
console.log("main ran", label, shapes.area(2), config.name);
