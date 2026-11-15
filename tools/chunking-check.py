#!/usr/bin/env python3
"""Check interchangeable chunk policies with whole-module and fragment placement units."""
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
ESB = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / "out/bin/esb"
SPEC = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else ROOT / "out/bin/spec"
WORK = ROOT / "out/chunking-check"
if WORK.exists():
    shutil.rmtree(WORK)
WORK.mkdir(parents=True)
MODES = [(policy, fragments) for policy in ("exact", "package", "balanced") for fragments in (False, True)]


def fixture(name, files):
    root = WORK / name
    root.mkdir()
    for name, text in {"package.json": '{"type":"module"}', **files}.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    return root


def build(root, entries, policy="exact", fragments=False, extra=(), tag=None):
    name = tag or f"{policy}-{'fragments' if fragments else 'modules'}"
    output = root / "built" / name
    result = subprocess.run([str(ESB), *entries, "--splitting", "--format=esm", f"--outdir={output}",
                             f"--chunk-policy={policy}", f"--fragments={str(fragments).lower()}", *extra],
                            cwd=root, capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
    return output


def node(root, code):
    result = subprocess.run(["node", "--input-type=module", "-e", code], cwd=root, capture_output=True,
                            text=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout.strip()


def execute(root, output, files, expression):
    imports = "\n".join(f"const m{i} = await import({json.dumps((output / name).as_uri())});" for i, name in enumerate(files))
    return node(root, imports + "\nconsole.log(JSON.stringify(" + expression + "));")


def dependency_files(output, entry):
    seen = set()
    pending = [entry]
    while pending:
        name = pending.pop()
        if name in seen:
            continue
        seen.add(name)
        text = (output / name).read_text()
        pending.extend(path[2:] for path in re.findall(r'(?:from\s*|import\s*)["\'](\./[^"\']+)["\']', text))
    return seen


def closure(output, entry):
    return "\n".join((output / name).read_text() for name in sorted(dependency_files(output, entry)))


def chunks(output):
    return sorted(output.glob("chunk-*.js"))


def data_chunks(output, markers=("ONE", "TWO")):
    # Runtime initialization helpers are separate indivisible units. Count the actual fixture
    # code here; the execution/evaluation tests check runtime behavior independently.
    return [p for p in chunks(output) if any(marker in p.read_text() for marker in markers)]


root = fixture("independent", {
    "library.js": 'export function core(x) { return "CORE_ONLY:" + x; }\nexport function admin(x) { return "ADMIN_ONLY:" + x; }\n',
    "home.js": 'import { core } from "./library.js"; export const result = core(1);\n',
    "admin.js": 'import { admin } from "./library.js"; export const result = admin(2);\n',
})
for policy, fragments in MODES:
    output = build(root, ["home.js", "admin.js"], policy, fragments)
    assert execute(root, output, ["home.js", "admin.js"], "[m0.result,m1.result]") == '["CORE_ONLY:1","ADMIN_ONLY:2"]'
    assert ("ADMIN_ONLY:" not in closure(output, "home.js")) == fragments
    assert ("CORE_ONLY:" not in closure(output, "admin.js")) == fragments
    optimized = build(root, ["home.js", "admin.js"], policy, fragments,
                      ["--minify", "--sourcemap"], tag=f"optimized-{policy}-{fragments}")
    assert execute(root, optimized, ["home.js", "admin.js"], "[m0.result,m1.result]") == '["CORE_ONLY:1","ADMIN_ONLY:2"]'
    maps = list(optimized.glob("*.map"))
    assert maps and all(json.loads(p.read_text())["version"] == 3 for p in maps)
print("ok   all three policies work with either modules or fragments; independent exports separate only with fragments")

root = fixture("fragment-cycle", {
    "library.js": 'export function one(n) { return n ? two(n-1) + 1 : 0; } export function two(n) { return n ? one(n-1) + 1 : 0; }\n',
    "a.js": 'import { one } from "./library.js"; export const value = one(3);\n',
    "b.js": 'import { two } from "./library.js"; export const value = two(4);\n',
})
for policy, fragments in MODES:
    output = build(root, ["a.js", "b.js"], policy, fragments, ["--chunk-max-size=1", "--chunk-min-size=0"])
    assert execute(root, output, ["a.js", "b.js"], "[m0.value,m1.value]") == "[3,4]"
    assert any("function one(" in p.read_text() and "function two(" in p.read_text() for p in chunks(output))
print("ok   mutually dependent declarations form one indivisible fragment cycle")

root = fixture("shared-state", {
    "counter.js": 'export let count = 0; export function increment() { return ++count; } export function read() { return count; }\n',
    "a.js": 'import { increment } from "./counter.js"; export const value = increment();\n',
    "b.js": 'import { read } from "./counter.js"; export const value = read();\n',
})
for policy, fragments in MODES:
    output = build(root, ["a.js", "b.js"], policy, fragments)
    assert execute(root, output, ["a.js", "b.js"], "[m0.value,m1.value]") == "[1,1]"
print("ok   mutable shared bindings retain one instance across entries and every policy")

root = fixture("effects", {
    "effects.js": 'globalThis.__chunking_events = (globalThis.__chunking_events || []); globalThis.__chunking_events.push("init"); export const state = { value: 1 };\n',
    "library.js": 'import { state } from "./effects.js"; export function get() { return state; } export function other() { return state; }\n',
    "a.js": 'import { get } from "./library.js"; export const state = get(); globalThis.__chunking_events.push("a");\n',
    "b.js": 'import { other } from "./library.js"; export const state = other(); globalThis.__chunking_events.push("b");\n',
})
for policy, fragments in MODES:
    output = build(root, ["a.js", "b.js"], policy, fragments)
    assert execute(root, output, ["a.js", "b.js"], "[m0.state===m1.state,globalThis.__chunking_events]") == '[true,["init","a","b"]]'
print("ok   initialization order, one-time effects and shared object identity are preserved")

root = fixture("cycles", {
    "left.js": 'import { right } from "./right.js"; export function left(n) { return n ? right(n-1) : "left"; }\n',
    "right.js": 'import { left } from "./left.js"; export function right(n) { return n ? left(n-1) : "right"; }\n',
    "a.js": 'import { left } from "./left.js"; export const value = left(2);\n',
    "b.js": 'import { right } from "./right.js"; export const value = right(2);\n',
})
for policy, fragments in MODES:
    output = build(root, ["a.js", "b.js"], policy, fragments)
    assert execute(root, output, ["a.js", "b.js"], "[m0.value,m1.value]") == '["left","right"]'
print("ok   import cycles keep working when policies regroup modules")

root = fixture("initialization", {
    "library.js": 'const initial = 7; let state = initial; export function value() { return state; } export function set(n) { state = n; }\n',
    "a.js": 'import { value, set } from "./library.js"; export const first = value(); set(8);\n',
    "b.js": 'import { value } from "./library.js"; export const next = value();\n',
})
for policy, fragments in MODES:
    output = build(root, ["a.js", "b.js"], policy, fragments)
    assert execute(root, output, ["a.js", "b.js"], "[m0.first,m1.next]") == "[7,8]"
print("ok   nontrivial initialization and writers stay coupled rather than becoming unsafe fragments")

root = fixture("lazy", {
    "main.js": 'export async function load() { return (await import("./lazy.js")).value; }\n',
    "lazy.js": 'globalThis.lazyRuns = (globalThis.lazyRuns || 0) + 1; export const value = 9;\n',
})
for policy, fragments in MODES:
    output = build(root, ["main.js"], policy, fragments)
    code = f'''const main = await import({json.dumps((output / 'main.js').as_uri())});
if (globalThis.lazyRuns !== undefined) throw new Error('lazy effect ran eagerly');
console.log(JSON.stringify([await main.load(), await main.load(), globalThis.lazyRuns]));'''
    assert node(root, code) == "[9,9,1]"
print("ok   lazy import boundaries preserve evaluation timing and execute once")

root = fixture("namespaces", {
    "library.js": 'export function one() { return 1; } export function two() { return 2; }\n',
    "bridge.js": 'export * from "./library.js";\n',
    "a.js": 'import * as ns from "./bridge.js"; export const value = [Object.keys(ns).sort(), ns.one()];\n',
    "b.js": 'import { two } from "./bridge.js"; export const value = two();\n',
})
for policy, fragments in MODES:
    output = build(root, ["a.js", "b.js"], policy, fragments)
    assert execute(root, output, ["a.js", "b.js"], "[m0.value,m1.value]") == '[[["one","two"],1],2]'
print("ok   namespace getters and reexports retain their dependencies across fragment homes")

root = fixture("commonjs", {
    "legacy.cjs": 'module.exports = { value: 3 };\n',
    "bridge.js": 'export * from "./legacy.cjs";\n',
    "a.js": 'import item from "./legacy.cjs"; export const value = item.value;\n',
    "b.js": 'import { value as imported } from "./bridge.js"; export const value = imported;\n',
})
for policy, fragments in MODES:
    output = build(root, ["a.js", "b.js"], policy, fragments)
    assert execute(root, output, ["a.js", "b.js"], "[m0.value,m1.value]") == "[3,3]"
print("ok   CommonJS wrappers and dynamic reexports remain opaque and execute correctly")

root = fixture("module-location", {
    "library.js": 'export function one() { return import.meta.url; } export function two() { return import.meta.url; }\n',
    "a.js": 'import { one } from "./library.js"; export const value = one();\n',
    "b.js": 'import { two } from "./library.js"; export const value = two();\n',
})
for policy, fragments in MODES:
    output = build(root, ["a.js", "b.js"], policy, fragments)
    assert execute(root, output, ["a.js", "b.js"], "m0.value===m1.value") == "true"
print("ok   import.meta keeps a module's exports in one execution location")

root = fixture("duplicate-bindings", {
    "library.js": 'var value = 1; var value = 2; export function one() { return value; } export function two() { return value; }\n',
    "a.js": 'import { one } from "./library.js"; export const value = one();\n',
    "b.js": 'import { two } from "./library.js"; export const value = two();\n',
})
for policy, fragments in MODES:
    output = build(root, ["a.js", "b.js"], policy, fragments, ["--chunk-max-size=1", "--chunk-min-size=0"])
    assert execute(root, output, ["a.js", "b.js"], "[m0.value,m1.value]") == "[2,2]"
print("ok   redeclarations of one binding cannot be split into separate instances")

root = fixture("loop-writes", {
    "library.js": 'export let value = 0; export function one() { for (value of [1, 2]) {} return value; } export function two() { return value; }\n',
    "a.js": 'import { one } from "./library.js"; export const value = one();\n',
    "b.js": 'import { two } from "./library.js"; export const value = two();\n',
})
for policy, fragments in MODES:
    output = build(root, ["a.js", "b.js"], policy, fragments, ["--chunk-max-size=1", "--chunk-min-size=0"])
    assert execute(root, output, ["a.js", "b.js"], "[m0.value,m1.value]") == "[2,2]"
print("ok   loop-target writes keep shared module bindings coupled")

root = fixture("eval", {
    "library.js": 'var hidden = 7; export function one() { return eval("hidden") + hidden - hidden; } export function two() { return eval("hidden"); }\n',
    "a.js": 'import { one } from "./library.js"; export const value = one();\n',
    "b.js": 'import { two } from "./library.js"; export const value = two();\n',
})
for policy, fragments in MODES:
    output = build(root, ["a.js", "b.js"], policy, fragments)
    assert execute(root, output, ["a.js", "b.js"], "[m0.value,m1.value]") == "[7,7]"
print("ok   dynamic eval scopes retain their module bindings")

vendor = {
    "node_modules/one/package.json": '{"type":"module","main":"index.js"}',
    "node_modules/one/index.js": 'export function one() { return "ONE"; }\n',
    "node_modules/two/package.json": '{"type":"module","main":"index.js"}',
    "node_modules/two/index.js": 'export function two() { return "TWO"; }\n',
    "a.js": 'import { one } from "one"; import { two } from "two"; export const value = one()+two();\n',
    "b.js": 'import { one } from "one"; import { two } from "two"; export const value = one()+two();\n',
}
root = fixture("packages", vendor)
for fragments in (False, True):
    exact = build(root, ["a.js", "b.js"], "exact", fragments)
    packages = build(root, ["a.js", "b.js"], "package", fragments)
    separate = build(root, ["a.js", "b.js"], "balanced", fragments,
                     ["--chunk-min-size=0", "--chunk-max-size=0"], tag=f"separate-{fragments}")
    merged = build(root, ["a.js", "b.js"], "balanced", fragments,
                   ["--chunk-min-size=100000", "--chunk-max-size=0"], tag=f"merged-{fragments}")
    limited = build(root, ["a.js", "b.js"], "balanced", fragments,
                    ["--chunk-min-size=0", "--chunk-max-size=0", "--chunk-max-requests=2"], tag=f"limited-{fragments}")
    assert len(data_chunks(exact)) == 1
    assert len(data_chunks(packages)) == len(data_chunks(separate)) == 2
    assert len(data_chunks(merged)) == len(data_chunks(limited)) == 1
    assert len(dependency_files(limited, "a.js")) <= 2 and len(dependency_files(limited, "b.js")) <= 2
print("ok   package grouping, minimum size and request budgets change packing independently of fragmentation")

root = fixture("max-size", {
    "library.js": 'export function one() { return "ONE"; } export function two() { return "TWO"; }\n',
    "a.js": 'import { one, two } from "./library.js"; export const value = one()+two();\n',
    "b.js": 'import { one, two } from "./library.js"; export const value = one()+two();\n',
})
for fragments in (False, True):
    output = build(root, ["a.js", "b.js"], "balanced", fragments,
                   ["--chunk-max-size=1", "--chunk-min-size=0"])
    assert len(data_chunks(output)) == (2 if fragments else 1)
    assert execute(root, output, ["a.js", "b.js"], "[m0.value,m1.value]") == '["ONETWO","ONETWO"]'
print("ok   maximum size splits between semantic units and never cuts an indivisible module")

root = fixture("cost-model", {
    **vendor,
    "b.js": 'import { one } from "one"; export const value = one();\n',
    "c.js": 'import { two } from "two"; export const value = two();\n',
})
for fragments in (False, True):
    low = build(root, ["a.js", "b.js", "c.js"], "balanced", fragments,
                ["--chunk-min-size=100000", "--chunk-max-size=0", "--chunk-request-cost=0"], tag=f"low-{fragments}")
    high = build(root, ["a.js", "b.js", "c.js"], "balanced", fragments,
                 ["--chunk-min-size=100000", "--chunk-max-size=0", "--chunk-request-cost=100000"], tag=f"high-{fragments}")
    assert len(data_chunks(low)) == 2 and len(data_chunks(high)) == 1
    assert execute(root, high, ["a.js", "b.js", "c.js"], "[m0.value,m1.value,m2.value]") == '["ONETWO","ONE","TWO"]'
print("ok   request cost trades extra inert code against requests without eagerly executing effects")

root = fixture("single-output", {"main.js": 'export const value = 42;\n'})
texts = []
for fragments in (False, True):
    out = root / f"single-{fragments}.mjs"
    subprocess.run([str(ESB), "main.js", "--format=esm", f"--outfile={out}", f"--fragments={str(fragments).lower()}"], cwd=root, check=True, capture_output=True)
    texts.append(out.read_bytes())
assert texts[0] == texts[1]
print("ok   fragmentation and output splitting are independent switches")

root = fixture("spec", vendor)
(root / "build.bundler").write_text('''bundler
target app
  entries "a.js" "b.js"
  outdir "dist"
  splitting
  format esm
  fragments on
  chunk-policy directories
end
''')
result = subprocess.run([str(SPEC), "build.bundler"], cwd=root, capture_output=True, text=True, timeout=120)
assert result.returncode == 0, result.stdout + result.stderr
assert execute(root, root / "dist", ["a.js", "b.js"], "[m0.value,m1.value]") == '["ONETWO","ONETWO"]'
print("ok   the build spec selects an application-supplied policy written in rules")

root = fixture("repeat", {
    "library.js": 'export function one() { return 1; } export function two() { return 2; }\n',
    "a.js": 'import { one } from "./library.js"; export const value = one();\n',
    "b.js": 'import { two } from "./library.js"; export const value = two();\n',
})
for policy, fragments in MODES:
    repeated = build(root, ["a.js", "b.js"], policy, fragments, ["--repeat=3"], tag="repeated")
    expected = build(root, ["a.js", "b.js"], policy, fragments, tag="fresh")
    assert all((repeated / p.name).read_bytes() == p.read_bytes() for p in expected.glob("*.js"))
    assert execute(root, repeated, ["a.js", "b.js"], "[m0.value,m1.value]") == "[1,2]"
print("ok   repeated builds preserve every policy's output and fragment ownership")

# Disk caching currently supports a single output only. Check the fragment flag there; multi-output cache/watch support remains the CLI's existing separate restriction.
cache = root / "cache"
for value in (1, 9, 1):
    (root / "library.js").write_text(f'export function one() {{ return {value}; }} export function two() {{ return 2; }}\n')
    for name, flag in [("cached", "--cache"), ("fresh", "--no-cache")]:
        result = subprocess.run([str(ESB), "a.js", "--format=esm", "--fragments", flag,
                                 f"--cache-dir={cache}", f"--outfile={name}.mjs"], cwd=root,
                                capture_output=True, text=True, timeout=120)
        assert result.returncode == 0, result.stdout + result.stderr
    assert (root / "cached.mjs").read_bytes() == (root / "fresh.mjs").read_bytes()
    assert execute(root, root, ["cached.mjs"], "m0.value") == str(value)
print("ok   cached single-output builds accept the fragment flag and preserve emission after edits")

# More expressive fragmentation: observable initialization stays coupled while independent
# exports separate. Compare runtime behavior to the original ESM in a fresh Node process.
def original(root, expression):
    return node(root, 'const m0 = await import("./a.js"); const m1 = await import("./b.js"); console.log(JSON.stringify(' + expression + '));')

root = fixture("allocation-fragments", {
    "library.js": '''export const home = { label: "HOME_OBJECT_ONLY", items: [1, 2], get value() { return this.items.length; } };
export const admin = { label: "ADMIN_OBJECT_ONLY", items: [3, 4, 5] };
export class Home { count = 2; static label = "HOME_CLASS_ONLY"; value() { return this.count; } }
export class Admin { static label = "ADMIN_CLASS_ONLY"; value() { return 3; } }
''',
    "a.js": 'import {home, Home} from "./library.js"; export const result = [home.label,home.value,new Home().value(),Home.label];\n',
    "b.js": 'import {admin, Admin} from "./library.js"; export const result = [admin.label,admin.items.length,new Admin().value(),Admin.label];\n',
})
expected = original(root, "[m0.result,m1.result]")
for policy, fragments in MODES:
    output = build(root, ["a.js", "b.js"], policy, fragments, ["--chunk-min-size=0", "--chunk-max-size=0"])
    assert execute(root, output, ["a.js", "b.js"], "[m0.result,m1.result]") == expected
    assert ("ADMIN_OBJECT_ONLY" not in closure(output, "a.js")) == fragments
    assert ("ADMIN_CLASS_ONLY" not in closure(output, "a.js")) == fragments
print("ok   objects, arrays, getters and classes can fragment without duplicating evaluation")

root = fixture("inert-demand", {
    "library.js": 'export const unused = {get value() {return "UNUSED_GETTER_BODY";}}; export function home() {return 7;}\n',
    "a.js": 'import {home} from "./library.js"; export const result = home();\n',
    "b.js": 'import {home} from "./library.js"; export const result = home();\n',
})
for policy, fragments in MODES:
    output = build(root, ["a.js", "b.js"], policy, fragments)
    assert execute(root, output, ["a.js", "b.js"], "[m0.result,m1.result]") == "[7,7]"
    assert ("UNUSED_GETTER_BODY" not in closure(output, "a.js")) == fragments
    retained = build(root, ["a.js", "b.js"], policy, fragments,
                     ["--tree-shaking=false"], tag=f"no-shake-{policy}-{fragments}")
    assert "UNUSED_GETTER_BODY" in closure(retained, "a.js")
print("ok   inert getter allocations use actual demand while no-tree-shaking retains all declarations")

root = fixture("effect-islands", {
    "library.js": '''globalThis.__islands = ["start"];
const state = { value: 1 };
function configure() { state.value = 7; globalThis.__islands.push("configured"); }
configure();
export function home() { return "HOME_ISLAND_ONLY:" + state.value; }
export function admin() { return "ADMIN_ISLAND_ONLY:" + state.value; }
globalThis.__islands.push("end");
''',
    "a.js": 'import {home} from "./library.js"; export const result = home(); globalThis.__islands.push("a");\n',
    "b.js": 'import {admin} from "./library.js"; export const result = admin(); globalThis.__islands.push("b");\n',
})
expression = "[m0.result,m1.result,globalThis.__islands]"
expected = original(root, expression)
for policy, fragments in MODES:
    output = build(root, ["a.js", "b.js"], policy, fragments, ["--chunk-min-size=0", "--chunk-max-size=0"])
    assert execute(root, output, ["a.js", "b.js"], expression) == expected
    assert ("ADMIN_ISLAND_ONLY:" not in closure(output, "a.js")) == fragments
print("ok   initialization calls and their transitive dependencies stay ordered while unrelated exports separate")

root = fixture("mutable-islands", {
    "library.js": '''export let count = 0;
export function increment() { return ++count; }
export function read() { return count; }
export function home() { return "HOME_FREE_ONLY"; }
export function admin() { return "ADMIN_FREE_ONLY"; }
''',
    "a.js": 'import {increment,home} from "./library.js"; export const result = [increment(),home()];\n',
    "b.js": 'import {read,admin} from "./library.js"; export const result = [read(),admin()];\n',
})
expected = original(root, "[m0.result,m1.result]")
for policy, fragments in MODES:
    output = build(root, ["a.js", "b.js"], policy, fragments, ["--chunk-min-size=0", "--chunk-max-size=0"])
    assert execute(root, output, ["a.js", "b.js"], "[m0.result,m1.result]") == expected
    assert ("ADMIN_FREE_ONLY" not in closure(output, "a.js")) == fragments
print("ok   mutable bindings and writers share one home without pinning unrelated functions")

root = fixture("class-initialization", {
    "base.js": 'globalThis.__class_order = ["base"]; export class Base { value() { return 3; } }\n',
    "library.js": '''import {Base} from "./base.js";
function key() { globalThis.__class_order.push("key"); return "value"; }
export class Derived extends Base { [key()]() { return 7; } static { globalThis.__class_order.push("static"); } }
const object = { get value() { globalThis.__class_order.push("getter"); return 9; } };
export const initialized = object.value;
export function home() { return "HOME_COMPLEX_ONLY"; }
export function admin() { return "ADMIN_COMPLEX_ONLY"; }
''',
    "a.js": 'import {Derived,initialized,home} from "./library.js"; export const result = [new Derived().value(),initialized,home()];\n',
    "b.js": 'import {Derived,admin} from "./library.js"; export const result = [new Derived().value(),admin()];\n',
})
expression = "[m0.result,m1.result,globalThis.__class_order]"
expected = original(root, expression)
for policy, fragments in MODES:
    output = build(root, ["a.js", "b.js"], policy, fragments, ["--chunk-min-size=0", "--chunk-max-size=0"])
    assert execute(root, output, ["a.js", "b.js"], expression) == expected
    assert ("ADMIN_COMPLEX_ONLY" not in closure(output, "a.js")) == fragments
print("ok   heritage, computed keys, static blocks and getter calls retain original initialization order")

# A dependency edge must not hoist a later var initializer ahead of a read that originally
# observed undefined. Keep those initializers in source order rather than topologically sorting.
root = fixture("forward-initialization", {
    "library.js": 'export var first = later; export var later = 9; export function home() { return first; } export function admin() { return later; }\n',
    "a.js": 'import {home} from "./library.js"; export const result = home();\n',
    "b.js": 'import {admin} from "./library.js"; export const result = admin();\n',
})
expected = original(root, "[m0.result,m1.result]")
assert expected == "[null,9]"
for policy, fragments in MODES:
    output = build(root, ["a.js", "b.js"], policy, fragments, ["--chunk-max-size=1", "--chunk-min-size=0"])
    assert execute(root, output, ["a.js", "b.js"], "[m0.result,m1.result]") == expected
print("ok   forward initialization dependencies preserve original read-before-initialization behavior")

def failure(root, path):
    return node(root, f'try {{ await import({json.dumps(path)}); console.log("NO_THROW"); }} catch (e) {{ console.log(JSON.stringify([e.name,globalThis.__before_throw])); }}')

root = fixture("abrupt-islands", {
    "library.js": '''globalThis.__before_throw = ["before"];
function fail() { throw new Error("initialization failed"); }
export const value = fail();
globalThis.__before_throw.push("after");
export function home() { return "HOME_AFTER_THROW"; }
export function admin() { return "ADMIN_AFTER_THROW"; }
''',
    "a.js": 'import {value,home} from "./library.js"; export const result = [value,home()];\n',
    "b.js": 'import {admin} from "./library.js"; export const result = admin();\n',
})
expected = failure(root, "./a.js")
for policy, fragments in MODES:
    output = build(root, ["a.js", "b.js"], policy, fragments, ["--chunk-max-size=1", "--chunk-min-size=0"])
    assert failure(root, (output / "a.js").as_uri()) == expected
    assert failure(root, (output / "b.js").as_uri()) == expected
    both = f'const first = await import({json.dumps((output / "a.js").as_uri())}).catch(e=>e); const second = await import({json.dumps((output / "b.js").as_uri())}).catch(e=>e); console.log(JSON.stringify([first === second,globalThis.__before_throw]));'
    assert node(root, both) == '[true,["before"]]'
print("ok   throwing initializers run once before any consumer and prevent following effects")

root = fixture("conditional-initializers", {
    "package.json": '{"type":"module","sideEffects":false}',
    "barrel.js": 'export * from "./used.js"; export * from "./noise-barrel.js";\n',
    "used.js": 'const value=7; const alias=value; export function used(){return alias;}\n',
    "noise-barrel.js": 'export * from "./unused.js"; export {used as other} from "./used.js"; const noise=3; export const unusedNoise=noise+"UNUSED_NOISE_BARREL";\n',
    "unused.js": 'const value=9; const alias=value; export function unused(){return "UNUSED_INITIALIZER_ONLY"+alias;}\n',
    "a.js": 'import {used} from "./barrel.js"; export const result=used();\n',
    "b.js": 'import {used} from "./barrel.js"; export const result=used();\n',
})
for policy, fragments in MODES:
    output=build(root,["a.js","b.js"],policy,fragments)
    assert execute(root,output,["a.js","b.js"],"[m0.result,m1.result]")=="[7,7]"
    code="\n".join(p.read_text() for p in output.glob("*.js"))
    assert "UNUSED_INITIALIZER_ONLY" not in code and "UNUSED_NOISE_BARREL" not in code
print("ok   conditional initializer calls retain used initialization without retaining unused side-effect-free barrel imports")

# A side-effect-free package's module that computes something as it loads: only the entry that uses
# it loads it, though both enter the barrel that re-exports it (date-fns's shape).
root = fixture("side-effect-free-barrel-initialization", {
    "package.json": '{"type":"module","sideEffects":false}',
    "index.js": 'export * from "./x.js"; export * from "./y.js";\n',
    "x.js": 'function make() { return { n: "ONLY_X_COMPUTES" }; }\nconst t = make();\nexport function x() { return t.n; }\n',
    "y.js": 'export function y() { return "ONLY_Y"; }\n',
    "a.js": 'import {x} from "./index.js"; export const result = x();\n',
    "b.js": 'import {y} from "./index.js"; export const result = y();\n',
})
for policy, fragments in MODES:
    output = build(root, ["a.js", "b.js"], policy, fragments)
    assert execute(root, output, ["a.js", "b.js"], "[m0.result,m1.result]") == '["ONLY_X_COMPUTES","ONLY_Y"]'
    assert "ONLY_X_COMPUTES" not in closure(output, "b.js")
print("ok   a side-effect-free module that computes as it loads is loaded only by the entry using it")

# What runs as a library loads (`/*@__PURE__*/` values, three.js's scratch vectors among them;
# classes extending a name; static blocks that mark a class; writes to a class's own properties) may
# be placed apart from its initialization, but loads wherever the library is initialized: in a chunk
# only its users load, it would be computed later than the library was, after code that may have
# changed what it reads. What runs nothing as it is defined, a function, is its users' alone.
def only_own(output, entry, own, other):
    text = closure(output, entry)
    return own in text and other not in text

root = fixture("eager-fragments", {
    "package.json": '{"type":"module"}',
    "library.js": """globalThis.__inits = (globalThis.__inits || 0) + 1;
export class Vec { constructor(x = 0) { this.x = x; } add(o) { _scratch.x = o.x; return new Vec(this.x + _scratch.x + "VEC_ONLY".length); } }
Vec.prototype.isVec = true;
Vec.ZERO = /*@__PURE__*/ new Vec(0);
const _scratch = /*@__PURE__*/ new Vec();
export class Late { size() { return "LATE_ONLY".length; } }
const _late = /*@__PURE__*/ new Late();
Late.prototype.isLate = true;
export function late() { return _late.size() + (new Late().isLate ? 1 : 0); }
class Base { static { this.prototype.isBase = true; } base() { return "BASE_ONLY"; } }
export class Shape extends Base { area() { return "SHAPE_ONLY".length; } }
export class Color { static NAMES = { red: 1 }; *[Symbol.iterator]() { yield "COLOR_ONLY"; } }
const _white = /*@__PURE__*/ new Color();
export function white() { return [..._white][0]; }
export function helperA() { return "HELPER_A"; }
export function helperB() { return "HELPER_B"; }
""",
    "a.js": 'import {Vec, helperA} from "./library.js"; export const result = [new Vec(1).add(new Vec(2)).x, new Vec().isVec, Vec.ZERO.x, helperA(), globalThis.__inits];\n',
    "b.js": 'import {Shape, white, late, helperB} from "./library.js"; export const result = [new Shape().area(), new Shape().isBase, new Shape().base(), white(), late(), helperB(), globalThis.__inits];\n',
})
expected = original(root, "[m0.result,m1.result]")
for policy, fragments in MODES:
    output = build(root, ["a.js", "b.js"], policy, fragments)
    assert execute(root, output, ["a.js", "b.js"], "[m0.result,m1.result]") == expected
    if fragments:
        # Values the library computes as it loads, marked pure and reading no global that may
        # change, compute whenever the chunk that uses them loads: each goes with its user, as a
        # function does; what each entry sees is still what the unbundled program does (above).
        for own, other, marker in (("a.js", "b.js", "VEC_ONLY"), ("b.js", "a.js", "SHAPE_ONLY"), ("b.js", "a.js", "COLOR_ONLY")):
            assert marker in closure(output, own) and marker not in closure(output, other), (policy, marker)
        # `_late` is made before `Late.prototype.isLate` is written, so the write stays where the
        # library initializes, and the class it writes to with it: loaded by both.
        assert "LATE_ONLY" in closure(output, "a.js") and "LATE_ONLY" in closure(output, "b.js"), policy
        assert only_own(output, "a.js", "HELPER_A", "HELPER_B"), policy
        assert only_own(output, "b.js", "HELPER_B", "HELPER_A"), policy
print("ok   what a library computes as it loads, marked pure, goes with what uses it, as functions do")

# What must not leave it: a value initialization changes before it is made; a value read before
# it stands; a class property initialization reads before it is written; a function that assigns
# the module's state, which stays with that state.
root = fixture("eager-fragments-ordered", {
    "package.json": '{"type":"module"}',
    "library.js": """export const settings = { mode: "start" };
function configure() { settings.mode = "configured"; }
configure();
function copy(o) { return { mode: o.mode }; }
export const snapshot = /*@__PURE__*/ copy(settings);
globalThis.__seen = typeof early === "undefined" ? "before" : early.tag;
var early = { tag: "EARLY_VALUE" };
export class Thing { label() { return Thing.LABEL; } }
globalThis.__label = Thing.LABEL;
Thing.LABEL = "THING_LABEL";
export const ahead = /*@__PURE__*/ peek();
var later = { tag: "LATER_VALUE" };
function peek() { return typeof later === "undefined" ? "not yet" : later.tag; }
let count = 0;
export function bump() { count += 1; return count; }
export function current() { return count; }
""",
    "a.js": 'import {snapshot, Thing, ahead} from "./library.js"; export const result = [snapshot.mode, new Thing().label(), globalThis.__label, globalThis.__seen, ahead];\n',
    "b.js": 'import {bump, current} from "./library.js"; bump(); bump(); export const result = [current(), globalThis.__seen];\n',
})
expected = original(root, "[m0.result,m1.result]")
for policy, fragments in MODES:
    output = build(root, ["a.js", "b.js"], policy, fragments)
    assert execute(root, output, ["a.js", "b.js"], "[m0.result,m1.result]") == expected, (policy, fragments)
print("ok   values initialization changes or reads first, and state with its writers, keep their order")

# A value placed apart that a module importing its library changes what it reads: it loads before
# that module's initialization, as it was computed before it, even when only an `import()` uses it.
root = fixture("eager-fragments-importer-changes", {
    "package.json": '{"type":"module"}',
    "library.js": """export const registry = { items: [] };
function count(r) { return r.items.length; }
export const view = /*@__PURE__*/ count(registry);
export function size() { return "SIZE_ONLY".length; }
""",
    "plugin.js": 'import {registry} from "./library.js"; registry.items.push("added");\nexport const plugged = true;\n',
    "lazy.js": 'import {view} from "./library.js"; export const seen = view;\n',
    "a.js": 'import {plugged} from "./plugin.js"; const lazy = await import("./lazy.js"); export const result = [plugged, lazy.seen];\n',
    "b.js": 'import {size} from "./library.js"; export const result = size();\n',
})
expected = original(root, "[m0.result,m1.result]")
for policy, fragments in MODES:
    output = build(root, ["a.js", "b.js"], policy, fragments)
    assert execute(root, output, ["a.js", "b.js"], "[m0.result,m1.result]") == expected, (policy, fragments)
print("ok   a value an importer of its library changes loads before that importer's initialization")

root=fixture("function-alias-order", {
    "library.js": 'export function fn(){return 1;} fn=()=>2; export const alias=fn; export function home(){return "HOME_ALIAS:"+alias();} export function admin(){return "ADMIN_ALIAS:"+alias();}\n',
    "a.js": 'import {home} from "./library.js"; export const result=home();\n',
    "b.js": 'import {admin} from "./library.js"; export const result=admin();\n',
})
expected=original(root,"[m0.result,m1.result]")
for policy,fragments in MODES:
    output=build(root,["a.js","b.js"],policy,fragments)
    assert execute(root,output,["a.js","b.js"],"[m0.result,m1.result]")==expected
    assert ("ADMIN_ALIAS:" not in closure(output,"a.js"))==fragments
print("ok   module-level hoisting proof does not move a fragment alias before a function-binding write")

root = fixture("invalid", {"main.js": "export const value = 1;\n"})
for flag in ("--chunk-policy=missing", "--chunk-min-size=-1"):
    result = subprocess.run([str(ESB), "main.js", flag, "--outfile=out.js"], cwd=root, capture_output=True, text=True)
    assert result.returncode != 0 and not (root / "out.js").exists(), result.stdout + result.stderr
print("ok   unknown policies and invalid limits are errors")


root = fixture("entry-facade-initialization", {
    "scheduler.cjs": 'module.exports = () => "scheduled";',
    "engine.cjs": 'const schedule=require("./scheduler.cjs");module.exports = () => schedule()+":engine";',
    "a.js": 'import engine from "./engine.cjs";export const value=engine();',
    "b.js": 'export const value="other";',
})
for fragments in (False, True):
    output = build(root, ["a.js", "b.js"], "balanced", fragments,
                   ["--chunk-min-size=0", "--chunk-max-size=1", "--minify"])
    assert execute(root, output, ["a.js", "b.js"], "[m0.value,m1.value]") == '["scheduled:engine","other"]'
    assert len([p.name for p in output.glob('*.js')]) == len(set(p.name for p in output.glob('*.js')))
print("ok   entry facade does not create a cycle through var-based implementation definitions")

root = fixture("direct-eval-bindings", {
    "library.js": 'var hidden=7;export function one(){return eval("hidden")}export function two(){return eval("hidden")}',
    "a.js": 'import {one} from "./library.js";export const value=one();',
    "b.js": 'import {two} from "./library.js";export const value=two();',
})
for policy, fragments in MODES:
    output = build(root, ["a.js", "b.js"], policy, fragments, ["--minify"])
    assert execute(root, output, ["a.js", "b.js"], "[m0.value,m1.value]") == '[7,7]'
print("ok   direct eval retains visible declarations and names without an explicit identifier read")

root = fixture("opaque-direct-entry-export", {
    "legacy.cjs": 'module.exports={value:3};',
    "bridge.js": 'export * from "./legacy.cjs";',
    "a.js": 'import {value} from "./bridge.js";export {value};',
    "b.js": 'export const other=4;',
})
for policy, fragments in MODES:
    output = build(root, ["a.js", "b.js"], policy, fragments, ["--minify"])
    assert execute(root, output, ["a.js", "b.js"], "[m0.value,m1.other]") == '[3,4]'
print("ok   an entry directly exporting a CommonJS star-reexport gets a declared export binding")

root = fixture("output-collision", {
    "one/a.js": 'export const value=1;',
    "two/a.js": 'export const value=2;',
})
result = subprocess.run([str(ESB), 'one/a.js', 'two/a.js', '--splitting', '--format=esm',
                         '--entry-names=[name]', '--outdir=built'], cwd=root, capture_output=True, text=True, timeout=30)
assert result.returncode != 0 and 'outputs collide' in result.stderr, result.stdout+result.stderr
assert not (root/'built/a.js').exists()
print('ok   conflicting entry paths fail before publishing any output')

print("all chunk policies check out")
