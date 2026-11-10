import Counter, { mount } from "./Counter.jsx";
import { initialCount } from "./database.js";
import { title } from "./shared.js";

export function page() {
  return { title, component: Counter, mount, props: { initialCount: initialCount() } };
}

export function callClientOnServer() {
  return Counter({ initialCount: 0 });
}
