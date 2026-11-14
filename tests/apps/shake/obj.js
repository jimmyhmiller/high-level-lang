import { heavy } from "./heavy.js";
export const Utils = {
  clamp(x) { return Math.min(1, Math.max(0, x)); },
  lerp(a, b, t) { return heavy() + "LERP_UNUSED" + a + b + t; },
  smooth: (x) => "SMOOTH_UNUSED" + x,
  version: "VERSION_UNUSED",
};
export default { parse(s) { return s.split(","); }, stringify(xs) { return "STRINGIFY_UNUSED" + xs.join(); } };
