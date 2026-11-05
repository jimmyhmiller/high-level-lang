// A differential oracle: call every lodash function on a matrix of inputs and print
// everything, so two builds of lodash can be compared by their stdout.
export function exercise(_) {
  const skip = new Set(["now", "random", "uniqueId", "debounce", "throttle", "delay", "defer", "shuffle",
    "sample", "sampleSize", "runInContext", "noConflict", "mixin", "bindAll", "templateSettings", "memoize"]);
  // Fixed text for functions: a build's minification must not show through a stringify.
  const fn = (f) => { Object.defineProperty(f, "toString", { value: () => "FN", enumerable: false }); return f; };
  const inputs = () => [
    undefined, null, 0, 1, -2.5, NaN, Infinity, "", "hello big World", "a.b[0]", true, false,
    [], [1, 2, 3, 2], ["b", "a", "c"], [[1, [2]], [3]], [{ a: 1, b: "x" }, { a: 2, b: "y" }, { a: 1, b: "z" }],
    {}, { a: 1, b: { c: [1, 2] } }, { x: "1", y: 2 }, new Date(0), /a+/g, new Map([[1, 2]]), new Set([1]),
    Symbol.iterator, fn((x) => x), fn((a, b) => (a < b ? -1 : 1)), "a", 2, ["a"], { a: 1 },
  ];
  const show = (v, depth = 0) => {
    if (depth > 4) return "…";
    if (typeof v === "function") return "fn:" + v.length;
    if (typeof v === "symbol") return v.toString();
    if (v === undefined) return "undefined";
    if (v === null) return "null";
    if (typeof v === "number") return Object.is(v, -0) ? "-0" : String(v);
    if (typeof v !== "object") return JSON.stringify(v);
    if (Array.isArray(v)) return "[" + v.slice(0, 40).map((x) => show(x, depth + 1)).join(",") + "]";
    if (v instanceof Date) return "Date(" + v.getTime() + ")";
    if (v instanceof RegExp) return String(v);
    if (v instanceof Map) return "Map" + show([...v], depth + 1);
    if (v instanceof Set) return "Set" + show([...v], depth + 1);
    return "{" + Object.keys(v).slice(0, 40).map((k) => k + ":" + show(v[k], depth + 1)).join(",") + "}";
  };
  const names = Object.keys(_).filter((k) => typeof _[k] === "function" && !skip.has(k)).sort();
  let calls = 0, hash = 0;
  const record = (s) => { for (let i = 0; i < s.length; i++) hash = (hash * 31 + s.charCodeAt(i)) | 0; };
  for (const name of names) {
    const lines = [];
    const run = (args) => {
      calls++;
      let out;
      try { out = show(_[name](...args)); } catch (e) { out = "throws"; }
      lines.push(out);
    };
    const one = inputs(), two = inputs();
    for (let i = 0; i < one.length; i++) {
      run([one[i]]);
      for (let j = 0; j < two.length; j += 3) run([inputs()[i], two[j]]);
    }
    const joined = lines.join("|");
    record(joined);
    console.log(name, lines.length, joined);
  }
  console.log("TOTAL", names.length, calls, hash);
}
