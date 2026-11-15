#!/usr/bin/env python3
"""TanStack Router's code splitting (--tanstack-router) against the program unsplit.

Each program is a few route files of `createFileRoute(id)({ … })` with a stand-in router package:
`createFileRoute`, `lazyRouteComponent` and `lazyFn` as small functions that log. Route options are
names (declared functions, consts, exported or imported ones, shorthands), arrows, calls that log as
they run, constants, and route-wide groupings; what they run counts in module state the loader and
the components share, reads `Route`, and calls into a shared module. `main.js` calls every option of
every route in turn and prints what each said, and the log.

Each program is run three ways: by Node from its source; built by us without the plugin; and built
by us with it, split into chunks. All three must print the same. A program whose split build loads
a component in a chunk of its own counts as split.

usage: split-fuzz.py [COUNT] [SEED] [ESB]
"""
import json
import os
import random
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COUNT = int(sys.argv[1]) if len(sys.argv) > 1 else 200
SEED = int(sys.argv[2]) if len(sys.argv) > 2 else 1
ESB = os.path.abspath(sys.argv[3]) if len(sys.argv) > 3 else os.path.join(ROOT, "out/bin/esb")
OUT = os.path.join(ROOT, "out/split-fuzz")

ROUTER = """export function log(s) { (globalThis.__log ??= []).push(String(s)); }
export const createFileRoute = (id) => (options) => { log("create " + id); return { id, options }; };
export const createRootRoute = (options) => ({ id: "__root__", options });
export const lazyRouteComponent = (importer, name) => (...a) => importer().then((m) => m[name](...a));
export const lazyFn = (importer, name) => (...a) => importer().then((m) => m[name](...a));
"""

KEYS = ["loader", "component", "pendingComponent", "errorComponent", "notFoundComponent", "beforeLoad"]

SHARED = """import { log } from "@tanstack/react-router";
let total = 0;
export function bump(by) { total += by; return total; }
export function Shared(a) { return "shared(" + a + "," + bump(1) + ")"; }
export const named = (a) => "named:" + a;
log("shared loaded");
"""


def route_file(rng, k):
    lines = ['import { createFileRoute, log } from "@tanstack/react-router";',
             'import { bump, Shared, named } from "../shared.js";']
    state = rng.choice(["let count = 0;", "let count = 10;"])
    lines.append(state)
    if rng.random() < 0.5:
        lines.append("const cache = new Map();")
        cache = True
    else:
        cache = False
    lines.append(f'log("r{k} init");')
    decls = []
    values = {}
    for key in KEYS:
        roll = rng.random()
        body = rng.choice([
            f'"{key}:" + a + ":" + (count += 1)',
            f'"{key}:" + Route.id + ":" + count',
            f'"{key}:" + bump(2) + ":" + a',
            f'"{key}:" + (cache ? cache.size : 0)' if cache else f'"{key}:" + a',
        ]).replace("(cache ? cache.size : 0)", "cache.size")
        if key == "loader" and cache and rng.random() < 0.5:
            body = f'(cache.set(a, count), "{key}:" + cache.size + ":" + (count += 5))'
        name = f"{key[0].upper()}{key[1:]}{k}"
        if roll < 0.25:
            decls.append(f"function {name}(a) {{ return {body}; }}")
            values[key] = name
        elif roll < 0.35:
            decls.append(f"export function {name}(a) {{ return {body}; }}")
            values[key] = name
        elif roll < 0.45:
            decls.append(f"const {name} = (a) => {body};")
            values[key] = name
        elif roll < 0.55:
            values[key] = f"(a) => {body}"
        elif roll < 0.62:
            values[key] = rng.choice(["Shared", "named"])
        elif roll < 0.70:
            # A call that runs as the route is made: it must run once, where it did.
            decls.append(f"function wrap{k}{key}(f) {{ log(\"wrap r{k} {key}\"); return (a) => \"wrapped(\" + f(a) + \")\"; }}")
            values[key] = f"wrap{k}{key}((a) => {body})"
        elif roll < 0.76:
            decls.append(f"function {key}(a) {{ return {body}; }}")
            values[key] = "shorthand"
        elif roll < 0.82:
            values[key] = rng.choice(["undefined", "null", "true", "false"])
        else:
            continue
    # Declarations go before or after the route: a function is hoisted, a const after it is not read
    # before the route's options are called.
    before = [d for d in decls if not d.startswith("const ")]
    after = [d for d in decls if d.startswith("const ")]
    rng.shuffle(before)
    lines.extend(before)
    for d in after:
        lines.append(d)
    props = []
    for key, v in values.items():
        props.append(key if v == "shorthand" else f"{key}: {v}")
    if rng.random() < 0.2:
        props.append('codeSplitGroupings: [["loader", "component"], ["errorComponent", "notFoundComponent"], ["pendingComponent"]]')
    rng.shuffle(props)
    lines.append(f'export const Route = createFileRoute("/r{k}")({{ {", ".join(props)} }});')
    if rng.random() < 0.3:
        lines.append(f'export function readCount() {{ return count; }}')
    lines.append(f'log("r{k} done " + count);')
    return "\n".join(lines) + "\n"


def program(rng, folder):
    n = rng.randint(1, 4)
    files = {
        "package.json": '{"type":"module"}',
        "node_modules/@tanstack/react-router/package.json": '{"name":"@tanstack/react-router","type":"module","main":"index.js","sideEffects":false}',
        "node_modules/@tanstack/react-router/index.js": ROUTER,
        "shared.js": SHARED,
        "tsr.config.json": json.dumps({"routesDirectory": "./routes", "generatedRouteTree": "./routeTree.gen.js", "disableTypes": True}),
        "routes/__root.js": 'import { createRootRoute } from "@tanstack/react-router";\nexport const Route = createRootRoute({});\n',
    }
    for k in range(n):
        files[f"routes/r{k}.js"] = route_file(rng, k)
    imports = "\n".join(f'import {{ Route as R{k} }} from "./routes/r{k}.js";' for k in range(n))
    files["main.js"] = imports + f"""
import {{ log }} from "@tanstack/react-router";
const routes = [{", ".join(f"R{k}" for k in range(n))}];
const keys = {json.dumps(KEYS)};
for (const r of routes) {{
  for (const k of keys) {{
    const v = r.options[k];
    if (typeof v === "function") log(r.id + " " + k + " -> " + await v(k[0]));
    else log(r.id + " " + k + " = " + JSON.stringify(v));
  }}
}}
for (const r of routes) {{ for (const k of keys) {{ if (typeof r.options[k] === "function") log(r.id + " again " + await r.options[k]("x")); }} }}
console.log(globalThis.__log.join("\\n"));
"""
    for path, text in files.items():
        full = os.path.join(folder, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        open(full, "w").write(text)


def run(path):
    p = subprocess.run(["node", path], capture_output=True, text=True, timeout=30)
    return p.stdout + ("\nERROR " + p.stderr.strip().split("\n")[-1] if p.returncode else "")


def build(folder, out, extra):
    shutil.rmtree(os.path.join(folder, out), ignore_errors=True)
    p = subprocess.run([ESB, "main.js", "--splitting", "--format=esm", "--outdir=" + out] + extra,
                       cwd=folder, capture_output=True, text=True, timeout=120)
    if p.returncode != 0:
        return None, p.stdout + p.stderr
    return os.path.join(folder, out, "main.js"), ""


def main():
    rng = random.Random(SEED)
    shutil.rmtree(OUT, ignore_errors=True)
    failures, split, same = [], 0, 0
    for i in range(COUNT):
        folder = os.path.join(OUT, "p%d" % i)
        program(rng, folder)
        want = run(os.path.join(folder, "main.js"))
        plain, err1 = build(folder, "plain", [])
        cut, err2 = build(folder, "split", ["--tanstack-router=" + folder])
        if plain is None or cut is None:
            failures.append((i, "build failed: " + (err1 or err2)[:400]))
            continue
        got_plain, got_split = run(plain), run(cut)
        if got_plain != want or got_split != want:
            which = "unsplit" if got_plain != want else "split"
            failures.append((i, which + " differs from Node:\n--- node\n" + want[:1500] + "\n--- " + which + "\n" + (got_plain if which == "unsplit" else got_split)[:1500]))
            continue
        same += 1
        lazy = [f for f in os.listdir(os.path.join(folder, "split")) if "tsr-split" in f or f.startswith("r")]
        if any(f != "main.js" and not f.startswith("chunk-") for f in os.listdir(os.path.join(folder, "split"))):
            split += 1
        else:
            shutil.rmtree(folder, ignore_errors=True)
    for i, why in failures[:5]:
        print("FAIL p%d: %s" % (i, why))
    print("split-fuzz: %d programs, %d run the same three ways, %d split into chunks of their own, %d differ"
          % (COUNT, same, split, len(failures)))
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
