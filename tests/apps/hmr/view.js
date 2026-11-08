import { greet } from "./text.js";

export const label = "view v1";
export function render(n) {
  return greet() + " clicked " + n;
}

if (import.meta.hot) {
  import.meta.hot.accept();
  import.meta.hot.dispose((data) => { data.disposed = label; });
  if (import.meta.hot.data.disposed) console.log("view replaced, was", import.meta.hot.data.disposed);
}
