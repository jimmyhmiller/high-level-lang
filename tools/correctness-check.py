#!/usr/bin/env python3
"""Programs a bundle once got wrong, each against what it must do:
  - writes the language forbids (to a `const`, a class's own name, an import, a namespace import's
    property; `delete x` and `with` in code that is not strict, for ES module output) are errors
    where esbuild reports them, with its message, and the writes it allows still build;
  - legacy octal numbers and escapes in code that is not strict still mean what they did in an ES
    module output;
  - lowered class fields evaluate computed keys in the class's order, after its heritage;
  - with fragments, a value computed as its chunk loads is never computed later than its module
    was: not after an `import()`, nor by a second entry on the page;
  - dead code a define decides is cut down to the `var`s it hoists, which still shadow what they
    did, and nothing else (not a nested function's `var`s, nor a pattern's defaults);
  - a module loaded by `import()` without splitting is shaken as any is, yet what it reads through
    an `export *` barrel is initialised first, and a package with no side effects is not loaded
    for an import nothing reads;
  - minified names reuse what a scope does not read from outside, as Terser's do, yet never where
    the language or lowering forbids it: a catch body's declarations, a block's `var`, a name a
    class's code means the class by;
  - `?.` before a digit is a conditional and a number (`a?.5:b`, as minifiers write it), a
    TypeScript namespace exports its members in a file that is no module, and a TypeScript import
    a local value shadows names a type and goes;
  - a module imported `with { type: "json" }` is a JSON module of its own, its value as JSON.parse
    makes it with only a default export, whether bundled, loaded by import(), or left outside with
    its attribute kept; what the build cannot honour is an error; and a default-only module that
    import() loads has its namespace filled;
  - a direct `eval`, called by name or in parentheses, sees its module's names as written, while
    `eval` read any other way does not stop minifying; and one module reading `eval` leaves the
    names linking makes (`init_x`) distinct.
Every built program is run under Node and compared with the unbundled one.
   usage: correctness-check.py [ESB]"""
import json, os, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ESB = str(Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / 'out/bin/esb').resolve())
ESBUILD = str(ROOT / 'tests/node_modules/.bin/esbuild')
WORK = ROOT / 'out/correctness'
shutil.rmtree(WORK, ignore_errors=True)
WORK.mkdir(parents=True)
(WORK / 'package.json').write_text('{"type":"module"}')
checks, failures = 0, []


def run(cmd, cwd=WORK):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=120)


def ok(cond, label):
    global checks
    checks += 1
    if not cond:
        failures.append(label)
        print('FAIL', label, flush=True)


def write(files):
    for name, text in files.items():
        (WORK / name).parent.mkdir(parents=True, exist_ok=True)
        (WORK / name).write_text(text)


# ---------------------------------------------------------------- forbidden writes
write({'lib.js': 'export let v = 1; export const c = 2;\n'})
FORBIDDEN = {
    'top-const': ('const C = 1; function f(){ C = 2; } f();', 'Cannot assign to "C" because it is a constant'),
    'nested-const': ('function f(){ const C = 1; C++; } f();', 'Cannot assign to "C" because it is a constant'),
    'for-of-const': ('for (const x of [1]) { x = 2; }', 'Cannot assign to "x" because it is a constant'),
    'pattern': ('const C = 1; [C] = [2];', 'Cannot assign to "C" because it is a constant'),
    'for-in-target': ('const C = 1; for (C in {a: 1});', 'Cannot assign to "C" because it is a constant'),
    'logical-assign': ('const C = 1; C ||= 2;', 'Cannot assign to "C" because it is a constant'),
    'exported-const': ('export const X = 1; X = 2;', 'Cannot assign to "X" because it is a constant'),
    'class-name': ('class A { m(){ A = 1; } } new A().m();', 'Cannot assign to "A" because it is a constant'),
    'nested-class-name': ('function f(){ class Q { m(){ Q = 1; } } }', 'Cannot assign to "Q" because it is a constant'),
    'import': ('import { v } from "./lib.js"; v = 3;', 'Cannot assign to import "v"'),
    'import-compound': ('import { c } from "./lib.js"; c += 1;', 'Cannot assign to import "c"'),
    'namespace-property': ('import * as ns from "./lib.js"; ns.v = 3;', 'Cannot assign to import "v"'),
    'namespace': ('import * as ns from "./lib.js"; ns = 3;', 'Cannot assign to import "ns"'),
}
for name, (src, message) in FORBIDDEN.items():
    write({f'{name}.js': src + '\n'})
    oracle = run([ESBUILD, f'{name}.js', '--bundle', '--format=esm', '--log-level=error', '--outfile=o.mjs'])
    ours = run([ESB, f'{name}.js', '--format=esm', '--outfile=o.mjs'])
    ok(oracle.returncode != 0 and message in oracle.stderr, f'{name}: esbuild rejects it with {message!r}')
    ok(ours.returncode == 1 and message in ours.stderr and 'stack trace' not in ours.stderr,
       f'{name}: rejected with {message!r}: {ours.stderr[-300:]!r}')
print(f'ok   {len(FORBIDDEN)} forbidden writes rejected as esbuild rejects them', flush=True)

STRICT_ONLY = {
    'delete-name': ('var x = 1; delete x; console.log(1);', 'Delete of a bare identifier cannot be used with the "esm" output format'),
    'with': ('var o = {a: 1}; with (o) console.log(a);', 'With statements cannot be used with the "esm" output format'),
}
for name, (src, message) in STRICT_ONLY.items():
    write({f'{name}.cjs': src + '\n'})
    ours = run([ESB, f'{name}.cjs', '--format=esm', '--outfile=o.mjs'])
    ok(ours.returncode == 1 and message in ours.stderr, f'{name}: ESM output rejected with {message!r}: {ours.stderr[-300:]!r}')
    for fmt in ('iife', 'cjs'):
        built = run([ESB, f'{name}.cjs', f'--format={fmt}', '--outfile=o.cjs'])
        want = run(['node', f'{name}.cjs'])
        got = run(['node', 'o.cjs'])
        ok(built.returncode == 0 and got.stdout == want.stdout, f'{name}: {fmt} output builds and runs as the original')
print('ok   `delete x` and `with` rejected for ES module output only', flush=True)

ALLOWED = {
    'shadowed': 'const C = 1; function f(C){ C = 2; return C; } console.log(f(0), C);',
    'let-var': 'const C = 1; function f(){ let L = 1; L = 2; var V = 1; V++; return [L, V, C]; } console.log(f());',
    'class-outside': 'let B = class {}; B = 1; class D {} D = 2; console.log(B, D);',
    'namespace-copy': 'import * as ns from "./lib.js"; const o = { ns }; o.ns = 1; console.log(ns.v, o.ns);',
    'function-name': '(function f(){ f = 1; })(); console.log(1);',
}
for name, src in ALLOWED.items():
    write({f'{name}.js': src + '\n'})
    ours = run([ESB, f'{name}.js', '--format=esm', '--outfile=o.mjs'])
    ok(ours.returncode == 0 and run(['node', 'o.mjs']).stdout == run(['node', f'{name}.js']).stdout,
       f'{name}: builds and runs as the original: {ours.stderr[-300:]!r}')
print(f'ok   {len(ALLOWED)} allowed writes build and run as the original', flush=True)

# ---------------------------------------------------------------- legacy octal in an ES module output
write({'octal.cjs': 'console.log(010, 08, 019, 00, 0777, "\\101\\42\\47\\134\\08\\8\\0z\\400", "\\1", 08.5, 0.5, 0x10);\n',
       'octal-user.js': 'import v from "./octal.cjs";\n'})
want = run(['node', 'octal.cjs']).stdout
for flags in ([], ['--minify']):
    for fmt, out in (('esm', 'o.mjs'), ('iife', 'o.cjs')):
        built = run([ESB, 'octal.cjs', f'--format={fmt}', f'--outfile={out}'] + flags)
        got = run(['node', out])
        ok(built.returncode == 0 and got.returncode == 0 and got.stdout == want, f'octal {fmt} {flags}: {got.stdout!r} {got.stderr[-200:]!r}')
print('ok   legacy octal numbers and escapes mean what they did, ES module output included', flush=True)

# ---------------------------------------------------------------- computed keys of lowered fields
write({'keys.js': '''const log = [];
const k = (name) => { log.push(name); return name; };
function mk() {
  return class extends (log.push("heritage"), Object) {
    [k("f1")] = 1;
    [k("m1")]() { return 1; }
    static [k("s1")] = 2;
    constructor() { super(); }
    #p() {}
    plain() {}
    [k("f2")] = 3;
    get [k("g1")]() { return 4; }
    static { log.push("block"); }
    static [k("s2")] = 4;
  };
}
const C = mk(), c = new C();
console.log(log.join(","), Object.keys(c).join(","), Object.getOwnPropertyNames(C.prototype).join(","), Object.keys(C).join(","));
'''})
want = run(['node', 'keys.js']).stdout
for target in ('es2021', 'es2020', 'es2015'):
    for flags in ([], ['--minify']):
        built = run([ESB, 'keys.js', f'--target={target}', '--outfile=o.cjs'] + flags)
        got = run(['node', 'o.cjs'])
        ok(built.returncode == 0 and got.stdout == want, f'computed keys {target} {flags}: {got.stdout!r} want {want!r}')
print('ok   lowered class fields evaluate computed keys in order, after the heritage', flush=True)

# ---------------------------------------------------------------- fragments computed no later
write({'frag/m.js': '''export const config = { scale: 1 };
export class W { constructor() { this.g = globalThis.G; this.s = config.scale; } }
export const w = /* @__PURE__ */ new W();
export class V { constructor(x) { this.x = x; } }
V.ORIGIN = /* @__PURE__ */ new V(globalThis.G);
''',
       'frag/a.js': 'import { config } from "./m.js";\nconfig.scale = 7;\nglobalThis.G = 7;\nimport("./route.js").then((r) => r.go());\n',
       'frag/route.js': 'import { w, V } from "./m.js";\nexport function go() { console.log(w.g, w.s, V.ORIGIN.x); }\n',
       'frag/e1.js': 'import "./m.js";\nglobalThis.G = 9;\n',
       'frag/e2.js': 'import { w, V } from "./m.js";\nconsole.log(w.g, V.ORIGIN.x);\n',
       'frag/page.js': 'await import("./e1.js"); await import("./e2.js");\n'})
lazy_want = run(['node', 'frag/a.js']).stdout
page_want = run(['node', 'frag/page.js']).stdout
for flags in ([], ['--fragments'], ['--fragments', '--minify'], ['--fragments', '--chunk-policy=balanced']):
    shutil.rmtree(WORK / 'frag-out', ignore_errors=True)
    built = run([ESB, 'frag/a.js', '--splitting', '--format=esm', '--outdir=frag-out'] + flags)
    got = run(['node', 'frag-out/a.js'])
    ok(built.returncode == 0 and got.stdout == lazy_want, f'eager value after import() {flags}: {got.stdout!r} want {lazy_want!r}')
    shutil.rmtree(WORK / 'frag-out', ignore_errors=True)
    built = run([ESB, 'frag/e1.js', 'frag/e2.js', '--splitting', '--format=esm', '--outdir=frag-out'] + flags)
    (WORK / 'frag-out/page.mjs').write_text('await import("./e1.js"); await import("./e2.js");\n')
    got = run(['node', 'frag-out/page.mjs'])
    ok(built.returncode == 0 and got.stdout == page_want, f'eager value, second entry {flags}: {got.stdout!r} want {page_want!r}')
print('ok   fragments: a value computed as its chunk loads is never computed later than its module', flush=True)

# ---------------------------------------------------------------- dead code that hoists
write({'dead/m.js': '''var x = "outer", z = "outer z", inner = "outer inner";
import { helper } from "./h.js";
function shadowed() { if (process.env.NODE_ENV !== "production") { var x = helper(); } return typeof x; }
function elsed() { if (process.env.NODE_ENV === "production") { return "kept"; } else { var y = helper(); } return y; }
function loops() { if (process.env.NODE_ENV !== "production") { for (var k in { a: 1 }) helper(); for (var z of [1]) helper(); } return [typeof k, typeof z]; }
function patterns() {
  if (process.env.NODE_ENV !== "production") { var { a, b: [c = function () { var inner = 1; return inner; }] = [], ...d } = helper(); }
  return [typeof a, typeof c, typeof d, inner];
}
function nested() { if (process.env.NODE_ENV !== "production") { (function* () { var inner = 2; })(); } return inner; }
console.log(shadowed(), elsed(), loops().join(), patterns().join(), nested());
''',
       'dead/h.js': 'export function helper() { return { HELPER_BODY: 1 }; }\n'})
want = run(['node', '--input-type=module', '-e', (WORK / 'dead/m.js').read_text().replace('import { helper } from "./h.js";', 'const helper = () => ({});').replace('process.env.NODE_ENV', '"production"')]).stdout
for flags in ([], ['--minify']):
    built = run([ESB, 'dead/m.js', '--format=esm', '--outfile=dead-out.mjs', '--define:process.env.NODE_ENV="production"'] + flags)
    got = run(['node', 'dead-out.mjs'])
    text = (WORK / 'dead-out.mjs').read_text() if built.returncode == 0 else ''
    ok(built.returncode == 0 and got.stdout == want and 'HELPER_BODY' not in text,
       f'dead code keeps only its vars {flags}: {got.stdout!r} want {want!r}, helper kept: {"HELPER_BODY" in text}')
print('ok   dead code is cut down to the vars it hoists', flush=True)

# ---------------------------------------------------------------- import() without splitting
write({'lazy/main.js': 'const a = await import("./a.js");\nconsole.log(a.used, a.viaBarrel(), Object.keys(a).join());\n',
       'lazy/a.js': 'import { x } from "./b.js";\nimport { clampWrapper } from "./barrel.js";\nimport { unusedLocale } from "pkg";\n'
                    'const UNUSED_IN_A = "UNUSED_IN_A";\nexport const used = x + 1;\nexport function viaBarrel() { return clampWrapper(7); }\n',
       'lazy/b.js': 'export * from "./c.js";\nexport const x = 1;\nexport const UNUSED_IN_B = "UNUSED_IN_B";\n',
       'lazy/c.js': 'export const UNUSED_IN_C = "UNUSED_IN_C";\n',
       'lazy/barrel.js': 'export * from "./inner-barrel.js";\n',
       'lazy/inner-barrel.js': 'export * from "./color.js";\n',
       'lazy/color.js': 'import clampDefault from "./clamp.js";\nexport function clampWrapper(v) { return clampDefault(v, 0, 5); }\n',
       'lazy/clamp.js': 'function clamp(v, lo, hi) { return Math.max(lo, Math.min(v, hi)); }\nconst clampDefault = clamp;\nexport default clampDefault;\n',
       'lazy/node_modules/pkg/package.json': '{"name":"pkg","type":"module","main":"index.js","sideEffects":false}',
       'lazy/node_modules/pkg/index.js': 'globalThis.PKG_LOADED = "PKG_LOADED";\nexport const unusedLocale = "UNUSED_LOCALE";\n'})
want = run(['node', 'lazy/main.js']).stdout
for flags in ([], ['--minify']):
    built = run([ESB, 'lazy/main.js', '--format=esm', '--outfile=lazy-out.mjs'] + flags)
    got = run(['node', 'lazy-out.mjs'])
    text = (WORK / 'lazy-out.mjs').read_text() if built.returncode == 0 else ''
    ok(built.returncode == 0 and got.stdout == want, f'import() without splitting {flags}: {got.stdout!r} want {want!r}')
    ok(not any(x in text for x in ['UNUSED_IN_A', 'UNUSED_IN_B', 'UNUSED_IN_C', 'PKG_LOADED', 'UNUSED_LOCALE']),
       f'import() without splitting shakes what is loaded {flags}: {text!r}')
print('ok   import() without splitting: shaken, and initialised through barrels', flush=True)

# ---------------------------------------------------------------- minified names that may not shadow
write({'shadow/m.js': '''export function caught(input) {
  try { throw new Error(input); } catch (failure) { const message = failure.message; let length = message.length; return [message, length]; }
}
export function hoisted(flag) { var outer = 1; { let inner = 2; var later = inner + outer; } return later + (flag ? 1 : 0); }
export class Counter {
  static base = 10;
  #count = Counter.base;
  set #value(next) { this.#count = next; }
  bump(amount) { this.#value = this.#count + amount; return this.#count; }
  static make(start) { const made = new Counter(); made.bump(start); return made; }
}
console.log(JSON.stringify([caught("boom"), hoisted(true), Counter.make(5).bump(1)]));
'''})
want = run(['node', 'shadow/m.js']).stdout
for flags in (['--minify'], ['--minify', '--target=es2015'], ['--minify', '--target=es2020']):
    built = run([ESB, 'shadow/m.js', '--format=esm', '--outfile=shadow-out.mjs'] + flags)
    got = run(['node', 'shadow-out.mjs'])
    ok(built.returncode == 0 and got.stdout == want, f'minified names that may not shadow {flags}: {got.stdout!r}{got.stderr[-200:]!r} want {want!r}')
print('ok   minified names never shadow where the language or lowering forbids it', flush=True)

# ---------------------------------------------------------------- syntax real code has
write({'syntax/ternary.js': 'const t = true, f = false;\nconsole.log(t?.5:1, f?.25:2, t?.0:3, [1]?.[0], ({a:4})?.a);\n',
       'syntax/space.ts': 'namespace Shapes { export class Square { constructor(public side: number) {} area() { return this.side ** 2; } } export namespace Inner { export const unit = "cm"; } }\n'
                          'module Legacy { export const answer = 42; }\nconsole.log(new Shapes.Square(3).area(), Shapes.Inner.unit, Legacy.answer);\n'})
# An import that names only a type, shadowed by a value of the module's own (as TypeScript's own
# checker.ts has `import { SymbolLinks }` and `const SymbolLinks = class implements SymbolLinks`).
write({'syntax/types.ts': 'export interface Links { a: number }\nexport const other = 2;\n',
       'syntax/shadow.ts': 'import { Links, other, Made } from "./types";\nconst Links = class implements Links { a = 1 };\n'
                           'function Made(this: Made) { this.a = 3; }\nconsole.log(new Links().a, other, new (Made as any)().a);\n'})
for entry, want in (('syntax/ternary.js', '0.5 2 0 1 4\n'), ('syntax/space.ts', '9 cm 42\n'), ('syntax/shadow.ts', '1 2 3\n')):
    built = run([ESB, entry, '--bundle', '--outfile=syntax-out.js'])
    got = run(['node', 'syntax-out.js'])
    ok(built.returncode == 0 and got.stdout == want, f'{entry}: {got.stdout!r}{built.stderr[-200:]!r} want {want!r}')
print('ok   `?.` before a digit, namespaces in a script, and a type import a value shadows, as real code writes them', flush=True)

# ---------------------------------------------------------------- import attributes
# A JSON module (`with { type: "json" }`) is its value as JSON.parse makes it, a `__proto__` key an
# own property, with only a default export; imported statically or by import(), bundled or left
# outside, where the output keeps the attribute Node requires. The plain JSON import is a module of
# its own. A default-only module that import() loads without splitting has its namespace filled.
write({'attrs/data.json': '{"a":1,"b":[2,3],"__proto__":{"p":1},"s":"x\\u0041","n":-1.5e3}\n',
       'attrs/only-default.js': 'export default { kind: "default only" };\n',
       'attrs/node_modules/extjson/package.json': '{"name":"extjson","exports":{"./data.json":"./data.json"}}',
       'attrs/node_modules/extjson/data.json': '{"outside":true}\n',
       'attrs/main.js': 'import d from "./data.json" with { type: "json" };\n'
                        'import * as ns from "./data.json" with { "type": "json", };\n'
                        'import ext from "extjson/data.json" with { type: "json" };\n'
                        'const dyn = await import("./data.json", { with: { type: "json" } });\n'
                        'const only = await import("./only-default.js");\n'
                        'console.log(JSON.stringify([d, Object.keys(ns), dyn.default === d, ns.default === d, Object.keys(d), Object.getPrototypeOf(d) === Object.prototype, ext, only.default]));\n'})
want = run(['node', 'attrs/main.js']).stdout
# The output is written beside the package the build leaves outside, where Node finds it.
for flags in ([], ['--minify'], ['--splitting', '--outdir=attrs/split'], ['--splitting', '--minify', '--outdir=attrs/split-min']):
    out = [f[len('--outdir='):] for f in flags if f.startswith('--outdir=')]
    target = out[0] + '/main.js' if out else 'attrs/out.mjs'
    built = run([ESB, 'attrs/main.js', '--bundle', '--format=esm', '--external:extjson/data.json'] + flags + ([] if out else ['--outfile=' + target]))
    got = run(['node', target]) if built.returncode == 0 else built
    ok(built.returncode == 0 and got.stdout == want, f'JSON modules {flags}: {got.stdout!r}{built.stderr[-300:]!r}{got.stderr[-300:]!r} want {want!r}')
write({'attrs/plain.js': 'import plain from "./data.json"; import typed from "./data.json" with { type: "json" };\n'
                         'console.log(plain === typed, JSON.stringify(plain) === JSON.stringify(typed), Object.keys(plain).join());\n'})
built = run([ESB, 'attrs/plain.js', '--bundle', '--format=esm', '--outfile=attrs-plain.mjs'])
got = run(['node', 'attrs-plain.mjs'])
ok(built.returncode == 0 and got.stdout == 'false true a,b,__proto__,s,n\n', f'a plain JSON import is not the JSON module: {got.stdout!r}{built.stderr[-300:]!r}')
write({'attrs/bad.json': '{"a": 1,}\n', 'attrs/comment.json': '{"a": 1} // no\n'})
for name, source, message in (
        ('css', 'import x from "./data.json" with { type: "css" }; console.log(x);', 'importing with a type attribute of "css" is not supported'),
        ('key', 'import x from "./data.json" with { mode: "x" }; console.log(x);', 'importing with the "mode" attribute is not supported'),
        ('twice', 'import x from "./data.json" with { type: "json", type: "json" }; console.log(x);', 'this import attribute is given twice'),
        ('named', 'import { a } from "./data.json" with { type: "json" }; console.log(a);', 'No matching export in "attrs/data.json with { type: \'json\' }" for import "a"'),
        ('options', 'const o = { with: { type: "json" } }; import("./data.json", o);', "import()'s options must be an object literal"),
        ('notjson', 'import x from "./bad.json" with { type: "json" }; console.log(x);', 'bad.json:1:9:'),
        # The json loader reads JSON, as esbuild's does: no comments, no trailing commas.
        ('loader', 'import x from "./comment.json"; console.log(x);', 'comment.json:1:10:')):
    write({f'attrs/err-{name}.js': source + '\n'})
    built = run([ESB, f'attrs/err-{name}.js', '--bundle', '--format=esm', '--outfile=attrs-err.mjs'])
    ok(built.returncode != 0 and message in built.stderr, f'import attributes error {name}: {built.returncode} {built.stderr[-300:]!r} want {message!r}')
print('ok   import attributes: JSON modules bundled and left outside, and what the build cannot honour', flush=True)

# ---------------------------------------------------------------- eval
write({'ev/direct.js': 'const secretValue = 41;\nexport function viaDirect() { return eval("secretValue + 1"); }\n',
       'ev/paren.js': 'const otherValue = 7;\nexport function viaParen() { return (eval)("otherValue * 2"); }\n',
       'ev/indirect.js': 'const thirdValue = 3;\nconst ev = eval;\nexport function viaIndirect() { return ev("typeof thirdValue"); }\nexport const total = thirdValue + 1;\n',
       'ev/main.js': 'import { viaDirect } from "./direct.js"; import { viaParen } from "./paren.js"; import { viaIndirect, total } from "./indirect.js";\n'
                     'console.log(viaDirect(), viaParen(), viaIndirect(), total);\n'})
want = run(['node', 'ev/main.js']).stdout
for flags in ([], ['--minify']):
    built = run([ESB, 'ev/main.js', '--format=esm', '--outfile=ev-out.mjs'] + flags)
    got = run(['node', 'ev-out.mjs'])
    ok(built.returncode == 0 and got.stdout == want, f'direct and indirect eval {flags}: {got.stdout!r} want {want!r}')
    if flags:
        text = (WORK / 'ev-out.mjs').read_text()
        ok('secretValue=' in text and 'otherValue=' in text and 'thirdValue=' not in text,
           f'only the direct evals keep their modules\' names: {text!r}')
# Two packages' own copies of one file, each wrapped (loaded with import()), so each has an init_y;
# and a CommonJS module that reads `eval` without calling it.
write({'evdup/node_modules/a/package.json': '{"name":"a","type":"module","main":"index.js"}',
       'evdup/node_modules/a/index.js': 'import { y } from "x"; export const fromA = () => y();\n',
       'evdup/node_modules/a/node_modules/x/package.json': '{"name":"x","type":"module","main":"y.js"}',
       'evdup/node_modules/a/node_modules/x/y.js': 'export const y = () => "x for a";\n',
       'evdup/node_modules/b/package.json': '{"name":"b","type":"module","main":"index.js"}',
       'evdup/node_modules/b/index.js': 'import { y } from "x"; export const fromB = () => y();\n',
       'evdup/node_modules/b/node_modules/x/package.json': '{"name":"x","type":"module","main":"y.js"}',
       'evdup/node_modules/b/node_modules/x/y.js': 'export const y = () => "x for b";\n',
       'evdup/intrinsics.cjs': 'module.exports = { "%eval%": eval };\n',
       'evdup/main.js': 'import intrinsics from "./intrinsics.cjs";\nconst a = await import("a"); const b = await import("b");\n'
                        'console.log(a.fromA(), b.fromB(), typeof intrinsics["%eval%"]);\n'})
want = run(['node', 'evdup/main.js']).stdout
built = run([ESB, 'evdup/main.js', '--format=esm', '--outfile=evdup-out.mjs'])
got = run(['node', 'evdup-out.mjs'])
ok(built.returncode == 0 and got.stdout == want, f'a module reading eval leaves made names distinct: {got.stdout!r} want {want!r}')
print('ok   direct eval keeps its names; eval read otherwise, and made names, do not', flush=True)

if failures:
    print(f'{len(failures)} of {checks} correctness checks failed')
    sys.exit(1)
print(f'all {checks} correctness checks passed')
