const out = [];
const show = (x) => out.push(JSON.stringify(x));
const f = () => null, o = { n: null, v: { w: 1 }, m(x) { return [this === o, x]; }, s: "x" }, k = "v";
let calls = 0; const once = () => (calls++, o);
// ?? and ?.
let u, z = 0;
show([u ?? 1, z ?? 2, f() ?? 3, once() ?? 4, calls]);
show([o?.v, o.n?.x, o.n?.x.y.z, o?.v.w, once()?.v.w, calls, o.m?.(1), o.nope?.(1), o?.m(2), o?.["v"], o.n?.[k], once()?.[k], f?.(), o.v?.w]);
show([o.m?.call, delete o.n?.x, delete o?.tmp, o?.m?.(3), o["m"]?.(4), once().m?.(5), calls]);
show([(o?.v).w, typeof o.nope?.x, o.v?.w ?? 9, o.nope?.x ?? 9, o?.v?.w, o?.n?.w?.q]);
// assignment operators
let a1 = 0, a2 = 1, a3 = null, p = { x: 0, y: 1, z: null, c: 2 }, name = "x";
a1 ||= 5; a2 &&= 6; a3 ??= 7; p.x ||= 8; p.y &&= 9; p.z ??= 10; p[name] ||= 11; once().added ??= 12;
show([a1, a2, a3, p, o.added, calls]);
let e = 2; e **= 3; p.c **= 2; show([e, p.c, 2 ** 10, (-2) ** 2, 2 ** 3 ** 2, once().added ** 2, calls]);
// catch, numbers
try { throw 1; } catch { show("caught"); }
show([1_000, 0xf_f, 1_0.5]);
// object spread and rest
const s1 = { a: 1 }, s2 = { b: 2, get g() { return 3; } }, sym = Symbol.for("s");
show([{ ...s1 }, { ...s1, ...s2 }, { x: 1, ...s1, y: 2, ...s2, z: 3 }, { ...null }, { ...s1, get h() { return 1; } }.h, { ...{ [sym]: 1 } }[sym]]);
const { a: ra, ...rest1 } = { a: 1, b: 2, c: 3 }; let { "q r": qr, 5: five, ...rest2 } = { "q r": 1, 5: 2, d: 4 };
function fr({ a, ...r }, b = 2, ...c) { return [a, r, b, c]; }
const ar = ({ a, ...r }) => r, ar2 = ({ a, ...r }) => { return [a, r]; };
var { ...only } = { o: 1 };
show([ra, rest1, qr, five, rest2, fr({ a: 1, b: 2 }), fr({ a: 1 }, 3, 4, 5), ar({ a: 1, z: 2 }), ar2({ a: 1, z: 2 }), only, fr.length]);
// classes
class Base { constructor() { this.order = ["base"]; } }
class C extends Base {
  x = 1; "quoted" = 2; 3 = 4; un; #p = 5; static s = 6; static #sp = 7;
  arrow = () => this.x;
  #m() { return this.#p + 1; } get #g() { return this.#p * 2; } set #g(v) { this.#p = v; }
  static #sm() { return C.#sp; } static get sg() { return C.#sm(); }
  static { C.block = C.s + 1; this.self = this === C; }
  constructor(a) { super(); this.order.push(a); this.y = this.x + 1; }
  m() { this.#p++; ++this.#p; this.#p += 1; this.#g = this.#g + 1; return [this.#p, this.#m(), this.#g, #p in this, #p in {}, this?.#p, this.#m?.()]; }
  static make() { return new C("made"); }
}
const K = class Named { static v = 1; static self = Named.v + 1; static t = this.v + 2; w = Named.v; };
const K2 = class { a = 1; }, K3 = class extends Base { b = 2; };
class NoCtor extends Base { c = 3; }
class Stat { static a = 1; static b = Stat.a + 1; static c = () => this.a; }
const c = new C("arg");
show([c, Object.keys(c), c.arrow(), c.m(), C.s, C.sg, C.block, C.self, C.make().order, new K(), K.self, K.t, new K2(), new K3(), new NoCtor(), Stat.b, Stat.c()]);
function nested() { return class { z = 9 ?? 1; #q = 1; get q() { return this.#q; } }; }
show([new (nested())().z, new (nested())().q]);
// async
const log = [];
const wait = (x) => new Promise((r) => setTimeout(() => r(x), 1));
async function af(a, b = 2, { c } = { c: 3 }) { const x = await wait(a); log.push(this === undefined ? "undef" : "this"); return x + b + c + arguments.length; }
const aa = async (x) => (await wait(x)) + 1, ab = async (x) => { await 1; return x; }, ac = async function () { return await wait(arguments.length); };
class AC { v = 1; async m(x) { return this.v + (await wait(x)); } static async s() { return 2; } async *ag() { yield this.v; yield* [2, 3]; yield await wait(4); } async #pm() { return 5; } callp() { return this.#pm(); } }
const objA = { async m() { return this === objA; }, async *g(a) { yield a; } };
async function* gen(n) { for (let i = 0; i < n; i++) yield await wait(i); return "end"; }
const ag2 = async function* () { const r = yield 1; yield r; yield* gen(1); };
(async () => {
  const results = [await af.call({}, 1), await aa(1), await ab(2), await ac(1, 2), await new AC().m(1), await AC.s(), await new AC().callp(), await objA.m()];
  const seen = [];
  for await (const v of gen(2)) seen.push(v);
  for await (let v of [wait(7), 8]) seen.push(v);
  let w; for await (w of new AC().ag()) seen.push(w);
  for await (const v of objA.g(9)) { seen.push(v); break; }
  const it = ag2(); seen.push(await it.next(), await it.next("sent"), await it.return(1));
  try { for await (const v of (async function* () { throw new Error("boom"); })()) seen.push(v); } catch (err) { seen.push(err.message); }
  try { await (async () => { throw 1; })(); } catch (err) { seen.push(err); }
  show([results, seen, log]);
  console.log(out.join("\n"));
})();
const q = { a: { b: { c() { return this === q.a.b; } }, n: null }, z: null };
console.log(JSON.stringify([q?.a.b.c?.(), q.a?.b.c?.(), q.z?.b.c?.(), q.a.n?.c.d(), q?.a?.b?.c?.(), q?.["a"]?.["b"]?.c(), delete q.z?.y.w, delete q?.a.n, q.a.n]));
class Sup { m() { return "sup"; } }
class Der extends Sup { o = 1; t() { return super.m?.(); } constructor(f) { if (f) { super(); } else { super(); } this.k = this.o; } }
console.log(JSON.stringify([new Der(1).k, new Der(0).t()]));
