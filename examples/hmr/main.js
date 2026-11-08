// A page to watch hot module replacement in a browser:
//   out/bin/esb examples/hmr/main.js --hmr --serve=8123 --outfile=out/hmr-demo/app.js
// then open http://127.0.0.1:8123 and edit view.js (replaced in place, the count kept) or this
// file (the page reloads, the count starts over).
import { view } from "./view.js";

let count = 0;
const root = document.createElement("div");
document.body.append(root);

function draw() {
  root.innerHTML = view(count);
  root.querySelector("button").onclick = () => {
    count += 1;
    draw();
  };
}

// view.js calls this after it is replaced, so the new view shows at once.
globalThis.redraw = draw;
draw();
