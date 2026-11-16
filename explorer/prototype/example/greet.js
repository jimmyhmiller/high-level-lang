export function greet(name) {
  return !(name === "") ? "hello, " + name : "hello";
}
export function shout(name) { return greet(name).toUpperCase(); }
