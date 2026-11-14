export function assert(condition, message) {
  if (!condition) throw new Error("assertion failed: " + message + ", which should never happen in production");
}
