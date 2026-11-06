function log(target: any, key?: any, desc?: any): any { console.log("dec", typeof target, key); return desc; }
function param(target: any, key: any, index: number) { console.log("param", key, index); }
const factory = (n: number) => (t: any, k?: any) => { console.log("factory", n, k); };
@log @factory(1)
class A {
  @log prop = 1;
  @factory(2) static sp = 2;
  @log method(@param a: number) { return a; }
  @log get acc() { return 1; }
  constructor(@param private x: number) {}
}
console.log(new A(3).method(4));
function sealed<T extends Function>(ctor: T) { Object.seal(ctor); Object.seal((ctor as any).prototype); return ctor; }
function replaceWith(n: number) { return (ctor: any) => class extends ctor { extra = n; }; }
function readonly(target: any, key: string, desc: PropertyDescriptor) { desc.writable = false; return desc; }
function enumerable(v: boolean) { return (t: any, k: string, d: PropertyDescriptor) => { d.enumerable = v; }; }
@sealed @replaceWith(7)
export class B { @readonly fixed() { return "fixed"; } @enumerable(true) get e() { return 1; } @log static st() {} }
const b = new B() as any;
let threw = false; try { (B.prototype as any).fixed = () => 1; } catch { threw = true; }
console.log(b.extra, b.fixed(), Object.isSealed(B), Object.keys(B.prototype), threw);
class OnlyParams { constructor(@param a: number) {} method(@param x: number, @param y: number) {} }
console.log(typeof OnlyParams);
