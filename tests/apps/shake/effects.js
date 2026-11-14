globalThis.log = [];
function note(x) { globalThis.log.push(x); return x; }
export const Mixed = { kept: note("SIDE_EFFECT_RUNS"), read() { return "read"; }, dropped() { return "DROPPED_UNUSED"; } };
export const Selfish = { a() { return this.b(); }, b() { return "this is used"; }, c() { return "C_KEPT_THIS"; } };
