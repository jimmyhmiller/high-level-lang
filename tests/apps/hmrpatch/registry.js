// Takes its own updates: what it imports may run again without the page reloading.
export { store } from "./store.js";
export { handlers } from "./captured.js";
export { Vault } from "./secret.js";
import "./effects.js";

if (import.meta.hot) {
  import.meta.hot.accept();
  console.log("registry ran");
}
