import { sideEffect } from "./effect";
import type { T } from "./effect";
class Base { constructor() { console.log("base sees", Object.keys(this)); } }
class D extends Base {
  a = 1; b: number; static s = "static"; static t: string; #p = 2; static #q = 3; c = this.a + 1;
  constructor(public x: number, private y = 2) { super(); console.log("ctor", Object.keys(this), this.#p, D.#q); }
  m() { return this.#p; }
}
class NoCtor { f = "f"; static g = NoCtor.name; }
class Derived extends NoCtor { h = this.f + "!"; }
const d = new D(5);
console.log(JSON.stringify([d, D.s, D.t, d.m(), new NoCtor(), NoCtor.g, new Derived()]));
