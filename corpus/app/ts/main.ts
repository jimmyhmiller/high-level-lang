import { Base, helper, type OnlyType, Kind } from "./lib";
import type { Other } from "./lib";
import { UnusedValue } from "./lib";
import * as NotUsed from "./sideeffect-free";
import "./sideeffect";
import Def, { named as renamed } from "./lib";
export type { Other };
export { helper as exportedHelper };

type Alias<T> = T extends string ? { a: T } : T extends (infer U)[] ? U : never;
interface Shape<T = unknown> extends Base2, Array<T> { x: number; y?: string; readonly z: T; m(a: number): void; new (x: T): Shape; (y: T): T; [k: string]: any; }
interface Base2 {}
declare const ambient: number;
declare function ambientFn(x: number): string;
declare class AmbientC { m(): void; x: number; }
declare namespace AmbientN { const a: number; function f(): void; }
declare module "made-up" { export const q: number; }
declare global { interface Window { w: number } }

const show = (x: unknown) => console.log(JSON.stringify(x));

// expressions
const a1 = 1 as number + 2;
const a2 = 3 satisfies number;
const a3 = <number>4;
const a4 = (5 as any) as number;
let a5!: number; a5 = 6;
const a6 = [1, 2, 3]!.length;
const a7 = { k: 1 }!.k;
const a8 = (a1 as number) < 5;
const a9 = a1 < 5 && a2 > 2;
const a10 = true ? (a1) : (a2);
const a11 = true ? (x: number) => x + 1 : (y: number): number => y;
const a12 = false ? (a1) : a2 => a2;
const a13 = a1 as unknown as string;
const a14 = a1 as number * 2;
const a15 = 2 * a1 as number + 1;
show([a1, a2, a3, a4, a5, a6, a7, a8, a9, a10, a11(1), typeof a12, a13, a14, a15]);

// generics
function id<T>(x: T): T { return x; }
const g1 = id<number>(1);
const g2 = <T,>(x: T): T => x;
const g3 = async <T>(x: T): Promise<T> => x;
const g4 = new Map<string, number>([["a", 1]]);
const g5 = new Set<number>;
const g6 = id<string>`x`;
const g7 = id<number>;
const g8 = g1 < 2;
const g9 = id<Array<Array<number>>>([[1]]);
show([g1, g2(2), g4.size, g5.size, g6, typeof g7, g8, g9]);

// functions
function over(a: string): string;
function over(a: number): number;
function over(a: any): any { return a; }
function withThis(this: { v: number }, a?: number, b: number = 2, ...rest: number[]) { return this.v + (a ?? 0) + b + rest.length; }
function guard(x: unknown): x is string { return typeof x === "string"; }
function assertIt(x: unknown): asserts x { if (!x) throw 1; }
function assertIs(x: unknown): asserts x is number { }
show([over(1), withThis.call({ v: 1 }, 1, 2, 3), guard("x"), assertIt(1), assertIs(2)]);

// classes
abstract class Abs<T> implements Shape2<T>, Base2 {
  abstract ab: number;
  abstract am(): void;
  declare dec: string;
  static sf: number = 1;
  public pf = 2;
  private readonly rf: number = 3;
  protected static psf = 4;
  override toString(): string { return "abs"; }
  uninit: number;
  opt?: string;
  def!: string;
  [key: string]: any;
  get acc(): number { return 1; }
  set acc(v: number) { }
  private async *gen<U>(x: U): AsyncGenerator<U> { yield x; }
  over2(a: string): void;
  over2(a: number): void;
  over2(a: any) { }
  readonly = 5;
  public public = 6;
  static static = 7;
  constructor(public a: number, private readonly b = 2, protected c?: string) { this.x = a; }
}
interface Shape2<T> {}
class Sub extends Abs<number> {
  ab = 1;
  am() {}
  field = 9;
  constructor(public extra: number) {
    super(1);
    this.after = 1;
  }
}
class Plain<T> extends (Object as any)<T> { }
const CE = class<T> implements Base2 { y: T; };
show(new Sub(5));
show(Object.getOwnPropertyNames(Abs.prototype));
show([Abs.sf, Abs.static, Object.keys(new Sub(1))]);
show(new CE());

// enums
enum Color { Red, Green = 5, Blue, Str = "s", Shift = 1 << 3, Or = Red | 4, Neg = -1, Ref = Blue * 2, Computed = "abc".length, After = 100 }
enum Color { Again = 3 }
const enum CE2 { A = 1, B = A + 1 }
export enum Exported { X = "x" }
enum Empty {}
enum Keys { "quoted key" = 1, 'other' = 2 }
declare enum Never1 { A }
show([Color, CE2.B, Exported, Empty, Keys, Color.Red, Color[5]]);
enum Unused { A }

// namespaces
namespace NS {
  export const x = 1;
  const y = x + 1;
  export let z = y;
  export function f(x: number) { return x + z; }
  export function g() { return x + y; }
  export class C { v = x; }
  export enum E { a = 2 }
  export namespace Inner { export const w = x + 1; export function h() { return w + z; } }
  export type T = number;
  export interface I {}
  function shadow() { const x = 10; { let z = 20; return x + z; } }
  export const sh = shadow();
  export const obj = { x, z };
  z = 5;
}
namespace NS { export const again = x + 100; }
namespace TypesOnly { export type A = 1; export interface B {} }
namespace A.B.C { export const deep = 1; }
function Fn() { return 1; }
namespace Fn { export const extra = 2; }
class Kl {}
namespace Kl { export const st = 3; }
export namespace ExportedNS { export const e = 1; }
show([NS, NS.f(1), NS.g(), new NS.C().v, NS.Inner.h(), A.B.C.deep, Fn.extra, Kl.st, typeof TypesOnly, ExportedNS]);

// imports and names
show([Kind.K1, helper(), Def, renamed, new Base().v]);
for (const q of [1] as number[]) show(q);
try { throw 1; } catch (e: unknown) { show(e); }
let tup: [a: string, b?: number, ...c: boolean[]] = ["x"];
let fnT: (a: number) => void, ctor: new () => Object, abs: abstract new () => Object;
let tmpl: `a${string}b`, idx: Shape["x"], kof: keyof Shape, ty: typeof show, unq: unique symbol;
let mapped: { readonly [K in "a" | "b"]?: K }, mapped2: { -readonly [K in "a" as `x${K}`]-?: K };
let imp: import("./lib").OnlyType, cond: string extends infer U extends string ? U : never;
let obj2 = { m<T>(x: T): T { return x; }, async am<T>() {}, get g(): number { return 1; }, *gm(): Generator<number> { yield 1; } };
show([tup, obj2.m(1), obj2.g]);
var type = 1, declare = 2, namespace = 3, module2 = 4, abstract = 5, as = 6, satisfies = 7, keyof = 8, infer = 9, is = 10, asserts = 11;
show([type, declare, namespace, abstract, as, satisfies, keyof, infer, is, asserts]);
declare
show("newline after declare");
abstract
class AfterAbstract {}
show(typeof AfterAbstract);
type
Foo = 1;
