const doc = { createElement: () => ({ style: {}, setAttribute() {}, appendChild() {}, removeChild() {}, getElementsByTagName: () => [], querySelectorAll: () => [], cloneNode() { return this; }, lastChild: { checked: false, cloneNode() { return this; } } }), documentElement: { appendChild() {}, removeChild() {}, nodeName: "html", contains: () => true }, implementation: { createHTMLDocument: () => doc }, createDocumentFragment: () => ({ appendChild(x) { return x; } }), addEventListener() {}, readyState: "complete", createComment: () => ({}) };
// jQuery reads `location` as a global as it loads.
globalThis.location = { href: "http://x/" };
// As much of a window as jQuery's factory touches without a DOM.
export const win = { document: doc, Symbol, setTimeout, location: globalThis.location };
