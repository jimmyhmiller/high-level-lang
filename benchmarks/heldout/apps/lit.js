import { html, svg, nothing, noChange } from "lit-html";
import { classMap } from "lit-html/directives/class-map.js";
const t = html`<div class=${"x"}>${[1, 2].map(i => html`<b>${i}</b>`)}</div>`;
console.log(t.strings.join("#"), t.values.length, typeof svg, typeof nothing, typeof noChange, typeof classMap);
