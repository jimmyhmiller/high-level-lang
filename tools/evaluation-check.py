#!/usr/bin/env python3
"""Compare split-bundle module evaluation against native ESM, in either entry load order."""
from pathlib import Path
import json
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
ESB = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / 'out/bin/esb'
WORK = ROOT / 'out/evaluation-check'
shutil.rmtree(WORK, ignore_errors=True)
WORK.mkdir(parents=True)
MODES = [(p, f, m) for p in ('exact', 'package', 'balanced') for f in (False, True) for m in (False, True)]


def fixture(name, files):
    folder = WORK / name
    folder.mkdir()
    for name, code in {'package.json': '{"type":"module"}', **files}.items():
        (folder / name).write_text(code)
    return folder


def observe(folder, order, extra=''):
    code = 'const records = []; const modules = {}; let previous;\n'
    for entry in order:
        code += f'''try {{ const m = await import({json.dumps((folder / (entry + '.js')).as_uri())});
modules[{json.dumps(entry)}] = m; records.push(["ok",m.value,globalThis.__eval_trace?.slice()]); }}
catch (e) {{ records.push(["error",typeof e,e?.message ?? e,e === previous,globalThis.__eval_trace?.slice()]); previous = e; }}\n'''
        code += extra + "\n"
    code += '\nconsole.log(JSON.stringify(records));'
    p = subprocess.run(['node', '--input-type=module', '-e', code], capture_output=True, text=True, timeout=20)
    assert p.returncode == 0, p.stdout + p.stderr
    return p.stdout.strip()


def check(name, files, extra=''):
    folder = fixture(name, files)
    expected = {order: observe(folder, order, extra) for order in [('a', 'b'), ('b', 'a')]}
    for policy, fragments, minify in MODES:
        output = folder / f'{policy}-{fragments}-{minify}'
        flags = ['--minify', '--sourcemap', '--pipeline=full'] if minify else []
        p = subprocess.run([str(ESB), 'a.js', 'b.js', '--splitting', '--format=esm', f'--outdir={output}',
                            f'--chunk-policy={policy}', f'--fragments={str(fragments).lower()}', *flags],
                           cwd=folder, capture_output=True, text=True, timeout=120)
        assert p.returncode == 0, (name, policy, fragments, minify, p.stdout + p.stderr)
        for order, want in expected.items():
            got = observe(output, order, extra)
            assert got == want, (name, policy, fragments, minify, order, got, want)
    print(f'ok   {name}: native ESM matches for both entry orders, every policy, modules/fragments and minification', flush=True)


A = 'globalThis.__eval_trace ??= []; globalThis.__eval_trace.push("A"); export const a = 1;'
B = 'globalThis.__eval_trace ??= []; globalThis.__eval_trace.push("B"); export const b = 2;'
check('inert-initializer-forwarders', {
    'effect.js': 'globalThis.__eval_trace ??= []; globalThis.__eval_trace.push("core"); export function core(){return 7;}',
    'left.js': 'import {core} from "./effect.js"; export function left(){return core();}',
    'right.js': 'import {core} from "./effect.js"; export function right(){return core()+1;}',
    'diamond.js': 'import {left} from "./left.js"; import {right} from "./right.js"; export function value(){return left()+right();}',
    'other.js': B,
    'a.js': 'import {value as run} from "./diamond.js"; import {b} from "./other.js"; globalThis.__eval_trace.push("entry-a"); export const value=run()+b;',
    'b.js': 'import {b} from "./other.js"; import {right} from "./right.js"; globalThis.__eval_trace.push("entry-b"); export const value=right()+b;',
})
check('inert-forwarded-failure', {
    'effect.js': 'globalThis.__eval_trace=["failure"]; throw 0; export function run(){return 1;}',
    'left.js': 'import {run} from "./effect.js"; export function left(){return run();}',
    'right.js': 'import {run} from "./effect.js"; export function right(){return run();}',
    'a.js': 'import {left} from "./left.js"; export const value=left();',
    'b.js': 'import {right} from "./right.js"; export const value=right();',
})
check('sibling-shared', {
    'dep-a.js': A, 'dep-b.js': B,
    'a.js': 'import {a} from "./dep-a.js"; import {b} from "./dep-b.js"; globalThis.__eval_trace.push("first"); export const value = a+b;',
    'b.js': 'import {b} from "./dep-b.js"; globalThis.__eval_trace.push("second"); export const value = b;',
})
check('bare-side-effect-imports', {
    'dep-a.js': 'globalThis.__eval_trace ??= []; globalThis.__eval_trace.push("A"); export {};',
    'dep-b.js': 'globalThis.__eval_trace ??= []; globalThis.__eval_trace.push("B"); export {};',
    'a.js': 'import "./dep-a.js"; import "./dep-b.js"; export const value=3;',
    'b.js': 'import "./dep-b.js"; export const value=2;',
})
check('opposite-import-orders', {
    'dep-a.js': A, 'dep-b.js': B,
    'a.js': 'import {a} from "./dep-a.js"; import {b} from "./dep-b.js"; export const value = a+b;',
    'b.js': 'import {b} from "./dep-b.js"; import {a} from "./dep-a.js"; export const value = b+a;',
})
check('imports-before-body', {
    'dep-a.js': A, 'dep-b.js': B,
    'a.js': 'globalThis.__eval_trace.push("body-before-import"); import {a} from "./dep-a.js"; globalThis.__eval_trace.push("middle"); import {b} from "./dep-b.js"; export const value = a+b;',
    'b.js': 'import {b} from "./dep-b.js"; export const value = b;',
})
check('diamond', {
    'core.js': 'globalThis.__eval_trace = ["core"]; export const core = 3;',
    'left.js': 'import {core} from "./core.js"; globalThis.__eval_trace.push("left"); export const left = core+1;',
    'right.js': 'import {core} from "./core.js"; globalThis.__eval_trace.push("right"); export const right = core+2;',
    'a.js': 'import {left} from "./left.js"; import {right} from "./right.js"; export const value = left+right;',
    'b.js': 'import {right} from "./right.js"; import {left} from "./left.js"; export const value = left+right;',
})
check('independent-entry-after-failure', {
    'dep-a.js': 'globalThis.__eval_trace ??= []; globalThis.__eval_trace.push("A"); throw new Error("A failed"); export const a=1;',
    'dep-b.js': B,
    'a.js': 'import {a} from "./dep-a.js"; import {b} from "./dep-b.js"; export const value=a+b;',
    'b.js': 'import {b} from "./dep-b.js"; export const value=b;',
})
check('cached-initialization-error', {
    'failure.js': 'globalThis.__eval_trace=["failure"]; throw new Error("cached"); export const x=1;',
    'a.js': 'import {x} from "./failure.js"; export const value=x;',
    'b.js': 'import {x} from "./failure.js"; export const value=x;',
})
check('cached-falsy-error', {
    'failure.js': 'globalThis.__eval_trace=["failure"]; throw 0; export const x=1;',
    'a.js': 'import {x} from "./failure.js"; export const value=x;',
    'b.js': 'import {x} from "./failure.js"; export const value=x;',
})
check('cyclic-evaluation', {
    'left.js': 'import {getRight} from "./right.js"; globalThis.__eval_trace ??= []; globalThis.__eval_trace.push("left"); export var label="left"; export function getLeft(){return label;} export function other(){return getRight();}',
    'right.js': 'import {getLeft} from "./left.js"; globalThis.__eval_trace ??= []; globalThis.__eval_trace.push("right"); export var label="right"; export function getRight(){return label;} export function other(){return getLeft();}',
    'a.js': 'import {getLeft,other} from "./left.js"; export const value=[getLeft(),other()];',
    'b.js': 'import {getRight,other} from "./right.js"; export const value=[getRight(),other()];',
})
check('lazy-initialization', {
    'dep-a.js': A, 'dep-b.js': B,
    'lazy.js': 'import {a} from "./dep-a.js"; import {b} from "./dep-b.js"; export const value=a+b;',
    'a.js': 'export const value="loader"; export async function load(){return (await import("./lazy.js")).value;}',
    'b.js': 'import {b} from "./dep-b.js"; export const value=b;',
}, extra='''if(modules.a?.load && !globalThis.__eval_did_load) {globalThis.__eval_did_load=true; records.push(["lazy",await modules.a.load(),await modules.a.load(),globalThis.__eval_trace?.slice()]);}''')
check('reexport-evaluation', {
    'dep-a.js': A, 'dep-b.js': B,
    'first.js': 'export {a} from "./dep-a.js"; export {b} from "./dep-b.js";',
    'second.js': 'export {b} from "./dep-b.js"; export {a} from "./dep-a.js";',
    'a.js': 'import {a,b} from "./first.js"; export const value=a+b;',
    'b.js': 'import {a,b} from "./second.js"; export const value=a+b;',
})
for name,bridge in [('namespace-star','export * as ns from "./child.js";'),('namespace-local','import * as ns from "./child.js"; export {ns};'),('namespace-async','export * as ns from "./child.js";')]:
    check(name, {
        'package.json':'{"type":"module","sideEffects":false}',
        'child.js':('await Promise.resolve(); ' if name=='namespace-async' else '')+'const original=7; export const value=original;',
        'bridge.js':bridge,
        'a.js':'import {ns} from "./bridge.js"; export const value=ns.value;',
        'b.js':'import {value as child} from "./child.js"; export const value=child;',
    })
check('commonjs-interoperation', {
    'dep-a.js': A,
    'legacy.cjs': 'globalThis.__eval_trace ??= []; globalThis.__eval_trace.push("CJS"); module.exports={value:2};',
    'a.js': 'import {a} from "./dep-a.js"; import legacy from "./legacy.cjs"; export const value=a+legacy.value;',
    'b.js': 'import legacy from "./legacy.cjs"; import {a} from "./dep-a.js"; export const value=a+legacy.value;',
})
check('native-root-await', {
    'dep-b.js': B,
    'a.js': 'globalThis.__eval_trace.push("root:start"); import {b} from "./dep-b.js"; await Promise.resolve(); globalThis.__eval_trace.push("root:end"); export const value=b+1;',
    'b.js': 'import {b} from "./dep-b.js"; export const value=b;',
})
check('async-sibling-start', {
    'dep-a.js': 'globalThis.__eval_trace ??= []; globalThis.__eval_trace.push("A:start"); await Promise.resolve(); globalThis.__eval_trace.push("A:end"); export const a=1;',
    'dep-b.js': B,
    'a.js': 'import {a} from "./dep-a.js"; import {b} from "./dep-b.js"; export const value=a+b;',
    'b.js': 'import {b} from "./dep-b.js"; export const value=b;',
})
check('async-shared-diamond', {
    'core.js': 'globalThis.__eval_trace=["core:start"]; await new Promise(r=>setTimeout(r,0)); globalThis.__eval_trace.push("core:end"); export const core=3;',
    'left.js': 'import {core} from "./core.js"; globalThis.__eval_trace.push("left"); export const left=core+1;',
    'right.js': 'import {core} from "./core.js"; globalThis.__eval_trace.push("right"); export const right=core+2;',
    'a.js': 'import {left} from "./left.js"; import {right} from "./right.js"; export const value=left+right;',
    'b.js': 'import {right} from "./right.js"; import {left} from "./left.js"; export const value=left+right;',
})
check('async-cycle', {
    'left.js': 'import {getRight} from "./right.js"; globalThis.__eval_trace ??= []; globalThis.__eval_trace.push("left:start"); await Promise.resolve(); globalThis.__eval_trace.push("left:end"); export var label="left"; export function getLeft(){return label;} export function other(){return getRight();}',
    'right.js': 'import {getLeft} from "./left.js"; globalThis.__eval_trace ??= []; globalThis.__eval_trace.push("right"); export var label="right"; export function getRight(){return label;} export function other(){return getLeft();}',
    'a.js': 'import {getLeft,other} from "./left.js"; export const value=[getLeft(),other()];',
    'b.js': 'import {getRight,other} from "./right.js"; export const value=[getRight(),other()];',
})
check('cached-async-error', {
    'failure.js': 'globalThis.__eval_trace=["failure:start"]; await Promise.resolve(); globalThis.__eval_trace.push("failure:end"); throw new Error("cached async"); export const x=1;',
    'a.js': 'import {x} from "./failure.js"; export const value=x;',
    'b.js': 'import {x} from "./failure.js"; export const value=x;',
})
check('async-error-and-sibling', {
    'failure.js': 'globalThis.__eval_trace ??= []; globalThis.__eval_trace.push("failure:start"); await Promise.resolve(); globalThis.__eval_trace.push("failure:end"); throw new Error("async failure"); export const x=1;',
    'dep-b.js': B,
    'a.js': 'import {x} from "./failure.js"; import {b} from "./dep-b.js"; export const value=x+b;',
    'b.js': 'import {b} from "./dep-b.js"; export const value=b;',
})
check('for-await-initialization', {
    'loop.js': 'globalThis.__eval_trace ??= []; globalThis.__eval_trace.push("loop:start"); export var sum=0; for await (const n of [1,2]) {sum+=n;} globalThis.__eval_trace.push("loop:end");',
    'dep-b.js': B,
    'a.js': 'import {sum} from "./loop.js"; import {b} from "./dep-b.js"; export const value=sum+b;',
    'b.js': 'import {b} from "./dep-b.js"; export const value=b;',
})
check('async-parent-microtasks', {
    'core.js': 'globalThis.__eval_trace=["core:start"]; await Promise.resolve(); globalThis.__eval_trace.push("core:end"); export const core=3;',
    'left.js': 'import {core} from "./core.js"; globalThis.__eval_trace.push("left"); queueMicrotask(()=>globalThis.__eval_trace.push("left:microtask")); export const left=core+1;',
    'right.js': 'import {core} from "./core.js"; globalThis.__eval_trace.push("right"); queueMicrotask(()=>globalThis.__eval_trace.push("right:microtask")); export const right=core+2;',
    'a.js': 'import {left} from "./left.js"; import {right} from "./right.js"; globalThis.__eval_trace.push("entry:a"); export const value=left+right;',
    'b.js': 'import {right} from "./right.js"; import {left} from "./left.js"; globalThis.__eval_trace.push("entry:b"); export const value=left+right;',
})
check('async-awaiting-parents', {
    'core.js': 'globalThis.__eval_trace=["core:start"]; await Promise.resolve(); globalThis.__eval_trace.push("core:end"); export const core=3;',
    'left.js': 'import {core} from "./core.js"; globalThis.__eval_trace.push("left:start"); await Promise.resolve(); globalThis.__eval_trace.push("left:end"); export const left=core+1;',
    'right.js': 'import {core} from "./core.js"; globalThis.__eval_trace.push("right:start"); await Promise.resolve(); globalThis.__eval_trace.push("right:end"); export const right=core+2;',
    'a.js': 'import {left} from "./left.js"; import {right} from "./right.js"; export const value=left+right;',
    'b.js': 'import {right} from "./right.js"; import {left} from "./left.js"; export const value=left+right;',
})
# Start the second entry while the cycle root is suspended. Its synchronously completed
# member is still part of that pending async cycle, so outsiders must await the cycle root.
for failing in (False, True):
    folder = fixture('pending-cycle-' + str(failing), {
        'left.js': 'import {marker} from "./right.js"; globalThis.__eval_trace ??= []; globalThis.__eval_trace.push("left:start"); globalThis.__signal(); export var ready=false; await new Promise(r=>setTimeout(r,20)); globalThis.__eval_trace.push("left:end"); ' + ('throw new Error("cycle failed");' if failing else 'ready=true;'),
        'right.js': 'import {ready} from "./left.js"; globalThis.__eval_trace ??= []; globalThis.__eval_trace.push("right"); export const marker=1; export function read(){return ready;}',
        'a.js': 'import {ready} from "./left.js"; globalThis.__eval_trace.push("entry:a"); export const value=ready;',
        'b.js': 'import {read} from "./right.js"; globalThis.__eval_trace.push("entry:b"); export const value=read();',
    })
    def pending_cycle(output):
        code='const started=new Promise(r=>globalThis.__signal=r);const first=import('+json.dumps((output/'a.js').as_uri())+');first.catch(()=>{});await started;const second=import('+json.dumps((output/'b.js').as_uri())+');const r=await Promise.allSettled([first,second]);console.log(JSON.stringify([r.map(x=>[x.status,x.value?.value,x.reason?.message]),r[0].reason===r[1].reason,globalThis.__eval_trace]));'
        result=subprocess.run(['node','--input-type=module','-e',code],capture_output=True,text=True,timeout=20)
        assert result.returncode==0,result.stderr
        return result.stdout.strip()
    expected=pending_cycle(folder)
    for policy,fragments,minify in MODES:
        output=folder/f'{policy}-{fragments}-{minify}'
        result=subprocess.run([str(ESB),'a.js','b.js','--splitting','--format=esm',f'--outdir={output}',f'--chunk-policy={policy}',f'--fragments={str(fragments).lower()}',*(['--minify','--pipeline=full'] if minify else [])],cwd=folder,capture_output=True,text=True,timeout=120)
        assert result.returncode==0,result.stdout+result.stderr
        actual=pending_cycle(output)
        assert actual==expected,(failing,policy,fragments,minify,actual,expected)
    print(f'ok   pending async cycle (failure={failing}) matches native ESM for a concurrent outside entry',flush=True)

# Independent dynamic imports can race; the host does not specify which entry wins. Check
# single-instance initialization and each entry's dependency constraints rather than an arbitrary
# total order chosen by one particular filesystem scheduling run.
folder = WORK / 'sibling-shared'
for output in [folder] + [folder / f'{p}-{f}-{m}' for p,f,m in MODES]:
    code = 'const [a,b] = await Promise.all([import(' + json.dumps((output/'a.js').as_uri()) + '),import(' + json.dumps((output/'b.js').as_uri()) + ')]);'
    code += "const t=globalThis.__eval_trace; if(a.value!==3 || b.value!==2 || t.length!==4 || new Set(t).size!==4 || t.indexOf('A')>t.indexOf('first') || t.indexOf('B')>t.indexOf('first') || t.indexOf('B')>t.indexOf('second')) throw new Error(JSON.stringify(t));"
    result = subprocess.run(['node','--input-type=module','-e',code],capture_output=True,text=True,timeout=20)
    assert result.returncode == 0, result.stderr
print('ok   concurrent entry imports initialize shared modules once and respect dependency constraints')
folder=fixture('require-async-rejected', {
    'async.js':'await Promise.resolve(); export const value=1;',
    'a.js':'export const value=require("./async.js");',
    'b.js':'export const value=2;',
})
for policy,fragments,minify in MODES:
    result=subprocess.run([str(ESB),'a.js','b.js','--splitting','--format=esm',f'--outdir={folder / "built"}',f'--chunk-policy={policy}',f'--fragments={str(fragments).lower()}',*(['--minify'] if minify else [])],cwd=folder,capture_output=True,text=True,timeout=120)
    assert result.returncode != 0 and 'cannot require async ES module' in result.stderr,result.stdout+result.stderr
print('ok   synchronous require of an async graph is rejected explicitly')
print('all evaluation checks passed')


