import { shared } from "./shared.js";
import cjs from "./c.cjs";
export const value = shared() + cjs.x;
export default "dyn default";
