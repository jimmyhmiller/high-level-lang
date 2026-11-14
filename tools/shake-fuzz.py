#!/usr/bin/env python3
"""Random programs against property shaking: each built three ways, all three run, all must print the same.

Each program is a few modules. Libraries declare objects (`export const O = {…}`, `export default
{…}`) whose properties are methods, arrows, values, shorthands of functions, getters, nested objects,
properties whose values do something as they load, and sometimes methods that use `this`; and a
library of functions read as a namespace. A middle module passes some on (`export { … } from`,
`export *`). The entry reads them every way there is: by name, through `const` aliases and
destructuring, through namespaces, and every way an object escapes: `Object.keys`, `for in`, spread,
`in`, `hasOwnProperty`, `?.`, `o[k]`, passed to a function, written, deleted, frozen, JSON. Some
programs are split into two entries.

Built with ours (property shaking on), ours with --property-shaking=false, and esbuild; each run in
Node. Shaking on and off must print the same: a program where they do not is kept under
out/shake-fuzz/fail-SEED and fails the run. One where ours (both) and esbuild disagree is kept under
esbuild-differs-SEED and counted apart: whatever it is, shaking did not do it.

usage: shake-fuzz.py [COUNT] [FIRST-SEED] [ESB]
"""
import os
import random
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COUNT = int(sys.argv[1]) if len(sys.argv) > 1 else 300
FIRST = int(sys.argv[2]) if len(sys.argv) > 2 else 1
ESB = os.path.abspath(sys.argv[3]) if len(sys.argv) > 3 else os.path.join(ROOT, "out/bin/esb")
ESBUILD = os.path.join(ROOT, "tests/node_modules/.bin/esbuild")
OUT = os.path.join(ROOT, "out/shake-fuzz")


def prop(r, o, k, helpers, selfish):
    """One property of object `o` named `k`, and any top-level declaration it needs."""
    kind = r.choice(["method", "arrow", "value", "number", "shorthand", "getter", "nested", "effect", "helper", "sibling", "other"]
                    + (["this"] if selfish else []))
    tag = f"{o}.{k}"
    if kind == "method":
        return f"  {k}(x) {{ return \"{tag}:\" + x; }}", ""
    if kind == "arrow":
        return f"  {k}: (x) => \"{tag}=>\" + x", ""
    if kind == "value":
        return f"  {k}: \"{tag}-value\"", ""
    if kind == "number":
        return f"  {k}: {r.randint(1, 999)}", ""
    if kind == "shorthand":
        name = f"{o}_{k}_fn"
        return f"  {k}: {name}", f"function {name}(x) {{ return \"{tag}-short:\" + x; }}\n"
    if kind == "getter":
        return f"  get {k}() {{ return \"{tag}-got\"; }}", ""
    if kind == "nested":
        return f"  {k}: {{ inner: \"{tag}-inner\", deep(x) {{ return \"{tag}-deep\" + x; }} }}", ""
    if kind == "effect":
        return f"  {k}: note(\"{tag}-loaded\")", ""
    if kind == "sibling" and not o.endswith("default"):
        # Another property of the same object, read through its name.
        return f"  {k}(x) {{ return \"{tag}>\" + show({o}.p0); }}", ""
    if kind == "other":
        # A property of another object of the module.
        other = "A1" if o != "A1" else "A0"
        return (f"  {k}(x) {{ return \"{tag}>\" + show({other}.p1); }}", "") if o.startswith("A") else (f"  {k}: \"{tag}-plain\"", "")
    if kind == "sibling":
        return f"  {k}: \"{tag}-plain\"", ""
    if kind == "helper":
        h = r.choice(helpers)
        return f"  {k}(x) {{ return {h}(\"{tag}\") + x; }}", ""
    return f"  {k}() {{ return \"{tag}-this:\" + typeof this; }}", ""


def library(r, name, objects):
    """A library module: helpers, `note`, its objects, maybe a default object."""
    helpers = [f"{name}_h{i}" for i in range(2)]
    text = "\n".join(f"export function {h}(s) {{ return \"[{h}]\" + s; }}" for h in helpers) + "\n"
    text += "function note(s) { (globalThis.__log ||= []).push(s); return s; }\n"
    text += "function show(v) { return typeof v === \"function\" ? \"fn\" : String(v); }\n"
    shapes = {}
    for o in objects:
        keys = [f"p{i}" for i in range(r.randint(2, 6))]
        selfish = r.random() < 0.15
        props, decls = [], ""
        for k in keys:
            p, d = prop(r, o, k, helpers, selfish)
            props.append(p)
            decls += d
        text += decls
        if o.endswith("default"):
            text += "export default {\n" + ",\n".join(props) + "\n};\n"
        else:
            text += f"export const {o} = {{\n" + ",\n".join(props) + "\n};\n"
        shapes[o] = keys
    return text, shapes


def value(o, k):
    """A read of property `k` of the object named `o`, as something printable."""
    return f"show({o}.{k})"


USES = [
    lambda r, o, ks: f"out({value(o, r.choice(ks))});",
    lambda r, o, ks: f"out({value(o, r.choice(ks))}, {value(o, r.choice(ks))});",
    lambda r, o, ks: f"out(Object.keys({o}).join());",
    lambda r, o, ks: f"{{ const names = []; for (const k in {o}) names.push(k); out(names.join()); }}",
    lambda r, o, ks: f"out(Object.keys({{ ...{o} }}).length);",
    lambda r, o, ks: f"out(\"{r.choice(ks)}\" in {o});",
    lambda r, o, ks: f"out({o}.hasOwnProperty(\"{r.choice(ks)}\"));",
    lambda r, o, ks: f"out(show({o}?.{r.choice(ks)}));",
    lambda r, o, ks: f"out(show({o}[\"{r.choice(ks)}\"]));",
    lambda r, o, ks: f"out(pick({o}, \"{r.choice(ks)}\"));",
    lambda r, o, ks: f"{{ const alias = {o}; out({value('alias', r.choice(ks))}); }}",
    lambda r, o, ks: f"{{ const {{ {r.choice(ks)}: picked }} = {o}; out(show(picked)); }}",
    lambda r, o, ks: f"out(JSON.stringify(Object.keys({o}).sort()));",
    lambda r, o, ks: f"out(typeof {o}.{r.choice(ks)});",
    lambda r, o, ks: f"try {{ {o}.{r.choice(ks)} = \"written\"; out(show({o}.{r.choice(ks)})); }} catch (e) {{ out(e.constructor.name); }}",
    lambda r, o, ks: f"try {{ delete {o}.{r.choice(ks)}; out(Object.keys({o}).length); }} catch (e) {{ out(e.constructor.name); }}",
    lambda r, o, ks: f"out(Object.isFrozen(Object.freeze({o})));",
    lambda r, o, ks: f"out(show({o}.{r.choice(ks)}?.inner ?? \"none\"));",
    lambda r, o, ks: f"{{ const a1 = {o}; const a2 = a1; out({value('a2', r.choice(ks))}); }}",
    lambda r, o, ks: f"out(show({{ ...{o}, extra: 1 }}.{r.choice(ks)}));",
    lambda r, o, ks: f"{{ {o}.added = \"new\"; out(show({o}.added), show({o}.{r.choice(ks)})); }}",
]

NS_USES = [
    lambda r, ns, fs: f"out({ns}.{r.choice(fs)}(\"n\"));",
    lambda r, ns, fs: f"{{ const {{ {r.choice(fs)}: f }} = {ns}; out(f(\"d\")); }}",
    lambda r, ns, fs: f"{{ const api = {ns}; out(api.{r.choice(fs)}(\"a\")); }}",
    lambda r, ns, fs: f"out(Object.keys({ns}).sort().join());",
    lambda r, ns, fs: f"out(pick({ns}, \"{r.choice(fs)}\")(\"p\"));",
    lambda r, ns, fs: f"{{ const a1 = {ns}; const a2 = a1; out(a2.{r.choice(fs)}(\"chain\")); }}",
]

PRELUDE = """function show(v) { return typeof v === "function" ? v.call(undefined, "!") : typeof v === "object" && v ? JSON.stringify(v) + (v.deep ? v.deep("?") : "") : String(v); }
function out(...xs) { console.log(xs.map((x) => typeof x === "function" ? "fn" : String(x)).join(" | ")); }
function pick(o, k) { return o[k]; }
"""


def program(seed):
    r = random.Random(seed)
    files = {}
    shapes = {}
    text, s = library(r, "liba", ["A0", "A1", "Adefault"])
    files["liba.js"] = text
    shapes.update({("liba", k): v for k, v in s.items()})
    text, s = library(r, "libb", ["B0"])
    files["libb.js"] = text
    shapes.update({("libb", k): v for k, v in s.items()})
    files["fns.js"] = "".join(f"export function f{i}(s) {{ return \"f{i}:\" + s; }}\n" for i in range(5))
    # A middle module passing some on.
    files["mid.js"] = r.choice([
        'export { A0, A1 } from "./liba.js";\nexport * from "./libb.js";\n',
        'export * from "./liba.js";\nexport { B0 } from "./libb.js";\n',
        'import { A0 } from "./liba.js";\nexport const Again = A0;\nexport { A1 } from "./liba.js";\nexport * from "./libb.js";\n',
    ])
    mid_names = {"A0", "A1", "B0"}
    if "Again" in files["mid.js"]:
        mid_names = {"Again", "A1", "B0"}

    def entry():
        lines = [PRELUDE.strip()]
        imports = ['import * as fns from "./fns.js";', 'import * as liba from "./liba.js";']
        how = r.choice(["direct", "mid", "default"])
        if how == "direct":
            imports.append('import { A0, A1 } from "./liba.js";')
            imports.append('import { B0 } from "./libb.js";')
            names = {"A0": shapes[("liba", "A0")], "A1": shapes[("liba", "A1")], "B0": shapes[("libb", "B0")]}
        elif how == "mid":
            imports.append("import { " + ", ".join(sorted(mid_names)) + ' } from "./mid.js";')
            names = {("A0" if n == "Again" else n): None for n in mid_names}
            names = {n: shapes[("liba", "A0")] if n in ("Again",) else None for n in mid_names}
            names = {}
            for n in mid_names:
                names[n] = shapes[("liba", "A0")] if n == "Again" else shapes[("liba", n)] if n.startswith("A") else shapes[("libb", n)]
        else:
            imports.append('import dflt from "./liba.js";')
            names = {"dflt": shapes[("liba", "Adefault")]}
        for _ in range(r.randint(2, 6)):
            n = r.choice(sorted(names))
            lines.append(r.choice(USES)(r, n, names[n]))
        if r.random() < 0.5:
            o = r.choice(["A0", "A1"])
            lines.append(r.choice(USES)(r, f"liba.{o}", shapes[("liba", o)]))
        if r.random() < 0.15:
            k = r.choice(shapes[("liba", "Adefault")])
            imports.append('import dfl2 from "./liba.js";')
            lines.append(f"{{ const {{ {k}: got }} = dfl2; out(show(got)); }}")
        if r.random() < 0.1:
            k = r.choice(shapes[("libb", "B0")])
            lines.append(f"{{ const L = require(\"./libb.js\"); out(show(L.B0.{k})); }}")
        if r.random() < 0.15:
            k = r.choice(shapes[("libb", "B0")])
            lines.append(f"import(\"./libb.js\").then((m) => out(\"later\", show(m.B0.{k})));")
        for _ in range(r.randint(0, 2)):
            lines.append(r.choice(NS_USES)(r, "fns", [f"f{i}" for i in range(5)]))
        lines.append("out((globalThis.__log || []).join());")
        return "\n".join(imports + lines) + "\n"

    files["main.js"] = entry()
    split = r.random() < 0.2
    if split:
        files["second.js"] = entry()
    return files, split


def run(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=60)


def outputs(d, kind, split):
    """What each entry of a build prints."""
    out = os.path.join(d, kind)
    entries = ["main.js"] + (["second.js"] if split else [])
    if kind == "esbuild":
        args = [ESBUILD] + entries + ["--bundle", "--minify", "--log-level=error"] + (["--splitting", "--format=esm", "--outdir=" + out] if split else ["--outfile=" + out + "/main.js"])
    else:
        args = [ESB] + entries + ["--minify"] + (["--property-shaking=false"] if kind == "off" else []) \
               + (["--splitting", "--format=esm", "--outdir=" + out] if split else ["--outfile=" + out + "/main.js"])
    p = run(args, d)
    if p.returncode != 0:
        return "BUILD FAILED: " + (p.stderr or p.stdout)[-400:]
    if split:
        open(os.path.join(out, "package.json"), "w").write('{"type":"module"}')
    texts = []
    for e in entries:
        q = run(["node", os.path.join(out, e)], d)
        # What it printed, and the error it stopped with, if any: its kind and message, not where.
        error = [l for l in q.stderr.splitlines() if l.split(":")[0].endswith("Error")]
        texts.append(q.stdout + (error[0] if error else ""))
    return "\n--\n".join(texts)


def main():
    shutil.rmtree(OUT, ignore_errors=True)
    os.makedirs(OUT)
    bad = []
    others = []
    shaken = 0
    for seed in range(FIRST, FIRST + COUNT):
        files, split = program(seed)
        d = os.path.join(OUT, "case")
        shutil.rmtree(d, ignore_errors=True)
        os.makedirs(d)
        for name, text in files.items():
            open(os.path.join(d, name), "w").write(text)
        on, off, theirs = outputs(d, "on", split), outputs(d, "off", split), outputs(d, "esbuild", split)
        size_on = sum(os.path.getsize(os.path.join(d, "on", f)) for f in os.listdir(os.path.join(d, "on")) if f.endswith(".js")) if os.path.isdir(os.path.join(d, "on")) else 0
        size_off = sum(os.path.getsize(os.path.join(d, "off", f)) for f in os.listdir(os.path.join(d, "off")) if f.endswith(".js")) if os.path.isdir(os.path.join(d, "off")) else 0
        if size_on < size_off:
            shaken += 1
        if on == off and on != theirs:
            # Ours, shaking or not, and esbuild disagree: not shaking's doing.
            others.append(seed)
            keep = os.path.join(OUT, "esbuild-differs-%d" % seed)
            shutil.copytree(d, keep)
            open(os.path.join(keep, "outputs.txt"), "w").write("OURS\n" + on + "\n\nESBUILD\n" + theirs + "\n")
        elif on != off:
            keep = os.path.join(OUT, "fail-%d" % seed)
            shutil.copytree(d, keep)
            open(os.path.join(keep, "outputs.txt"), "w").write("ON\n" + on + "\n\nOFF\n" + off + "\n\nESBUILD\n" + theirs + "\n")
            bad.append(seed)
            print("DIFFERS seed %d (split %s): kept in %s" % (seed, split, keep))
    print("shake-fuzz: %d programs, %d where shaking made the output smaller, %d where shaking changed what runs%s; %d where ours and esbuild differ, shaking or not%s"
          % (COUNT, shaken, len(bad), (": " + " ".join(map(str, bad))) if bad else "", len(others), (": " + " ".join(map(str, others))) if others else ""))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
