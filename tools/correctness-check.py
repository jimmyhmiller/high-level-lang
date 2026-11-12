#!/usr/bin/env python3
"""Programs a bundle once got wrong, each against what it must do:
  - writes the language forbids (to a `const`, a class's own name, an import, a namespace import's
    property; `delete x` and `with` in code that is not strict, for ES module output) are errors
    where esbuild reports them, with its message, and the writes it allows still build;
  - legacy octal numbers and escapes in code that is not strict still mean what they did in an ES
    module output;
  - lowered class fields evaluate computed keys in the class's order, after its heritage;
  - with fragments, a value computed as its chunk loads is never computed later than its module
    was: not after an `import()`, nor by a second entry on the page.
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

if failures:
    print(f'{len(failures)} of {checks} correctness checks failed')
    sys.exit(1)
print(f'all {checks} correctness checks passed')
