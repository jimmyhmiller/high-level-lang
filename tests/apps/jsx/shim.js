// A React that prints what it was given, so two bundles can be compared by running them.
export function createElement(type, props, ...children) {
  return { type: typeof type === "function" ? "fn" : type, props, children };
}
export const Fragment = "<fragment>";
