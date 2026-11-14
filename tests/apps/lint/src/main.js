import { render } from "./ui/view.js";
import { config } from "./config.js";
import { label } from "other-lib";
import "fxlib-l";

render(config, label("main"));
document.addEventListener("click", () => import("./admin/panel.js").then((m) => m.open()));
