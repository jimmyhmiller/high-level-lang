#!/usr/bin/env python3
"""Checks rewrites (`--rewrite=FILE`, bundle.rewrites) and lint fixes (`--lint=FILE --fix`).

- tests/apps/rewrite with its rules: `get` imported from a package becomes `o?.[k]` and the package
  goes; a parameter that is also called `get` is left; `assert` calls go with their module; a flag
  rewritten `false` takes its branch, and what only it read, before tree shaking. The program prints
  what it printed, but for the branch turned off.
- A source map still says where rewritten code came from.
- A rewrite that cannot mean anything is an error at its place.
- The rewrite file is watched: editing it rebuilds.
- A build spec's `rewrite "FILE"`.
- `--fix`: the fixes of what lints found are made to the sources (a whole line, when the statement
  was all of it; a template filled in), a package's files are not touched, nothing else is written,
  and linted again the findings fixed are gone.

usage: rewrite-check.py [ESB] [SPEC]
"""
import json
import os
import re
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ESB = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(ROOT, "out/bin/esb")
SPEC = os.path.abspath(sys.argv[2]) if len(sys.argv) > 2 else os.path.join(ROOT, "out/bin/spec")
FIXTURE = os.path.join(ROOT, "tests/apps/rewrite")
LINT_FIXTURE = os.path.join(ROOT, "tests/apps/lint")
OUT = os.path.join(ROOT, "out/rewrite-check")

failures = []
passed = 0


def check(ok, what):
    global passed
    if ok:
        passed += 1
        print("ok  ", what)
    else:
        failures.append(what)
        print("FAIL", what)


def esb(args, cwd=FIXTURE):
    return subprocess.run([ESB] + args, cwd=cwd, capture_output=True, text=True)


def run_node(path):
    return subprocess.run(["node", path], capture_output=True, text=True).stdout


B64 = {c: i for i, c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/")}


def vlq(segment):
    values, value, shift = [], 0, 0
    for ch in segment:
        digit = B64[ch]
        value += (digit & 31) << shift
        if digit & 32:
            shift += 5
        else:
            values.append(-(value >> 1) if value & 1 else value >> 1)
            value, shift = 0, 0
    return values


def original_line(map_path, line, column):
    """The source line (from 1) a source map gives the generated place, by its last mapping at or before it."""
    m = json.load(open(map_path))
    src_line, best = 0, None
    for gen, group in enumerate(m["mappings"].split(";")):
        col = 0
        for seg in filter(None, group.split(",")):
            v = vlq(seg)
            col += v[0]
            if len(v) >= 4:
                src_line += v[2]
                if gen == line and col <= column:
                    best = src_line + 1
    return best


def main():
    shutil.rmtree(OUT, ignore_errors=True)
    os.makedirs(OUT)
    rules = os.path.join(FIXTURE, "rewrite.lint")

    plain = esb(["src/main.js", "--minify-syntax", "--outfile=" + OUT + "/plain.js"])
    done = esb(["src/main.js", "--minify-syntax", "--sourcemap", "--outfile=" + OUT + "/rewritten.js", "--rewrite=" + rules])
    text = open(OUT + "/rewritten.js").read() if done.returncode == 0 else ""
    check(plain.returncode == 0 and done.returncode == 0, "the fixture builds, with its rewrites and without")
    check('user?.["profile"]' in text and "object == null" not in text, "get imported from tiny-get is o?.[k], and the package does not ship")
    check('return get("x",1)' in text, "a parameter also called get is not the import, and is left as it is")
    check("assertion failed" not in text and "user has a profile" not in text, "assert calls are taken out, and the module with them")
    check("beta feature" not in text and "flags" not in text, "the flag made false takes its branch, and what only it read, before tree shaking")
    check(run_node(OUT + "/rewritten.js") == "ada x1\n" and run_node(OUT + "/plain.js") == "ada x1\nthe beta feature, which is long enough to see whether it ships\n",
          "the program prints what it printed, but for the branch turned off")
    check(len(text) < len(open(OUT + "/plain.js").read()) / 2, "the rewritten build is less than half the size")
    lines = text.split("\n")
    at = [(i, l.index('user?.[')) for i, l in enumerate(lines) if 'user?.[' in l]
    check(len(at) == 1 and original_line(OUT + "/rewritten.js.map", at[0][0], at[0][1]) == 12,
          "a source map puts what a rewrite made where the code it replaced was (src/main.js:12)")

    # Rewrites that cannot mean anything.
    bad = OUT + "/bad.lint"
    for source, message in [
        ('rewrite a `f($X)` => `g($Y)` ;\n', "bad.lint:1:1: the template's $Y is bound by nothing in the pattern"),
        ('rewrite a `f($X)` => `g($X)` :- ships(R, X) ;\n', "bad.lint:1:33: ships is not a rewrite's to read"),
        ('rewrite a `f($X)` => `g($X)` :- imported(X, "y") ;\n', "bad.lint:1:33: imported has 3 columns, not 2"),
        ('rewrite a `f(` => `g($X)` ;\n', "bad.lint:1 `f(`:1:3: expected"),
        ('fix nolint `f($X)` => `g($X)` ;\n', "bad.lint:1:1: no lint named nolint to fix"),
    ]:
        open(bad, "w").write(source)
        p = esb(["src/main.js", "--outfile=" + OUT + "/bad.js", "--rewrite=" + bad])
        check(p.returncode != 0 and message in p.stdout + p.stderr, "an error at its place: " + message)

    # Watching: the rewrite file is an input.
    dest = OUT + "/watch"
    shutil.copytree(FIXTURE, dest, symlinks=True)
    open(dest + "/rules.lint", "w").write("")
    log = open(OUT + "/watch.log", "w")
    w = subprocess.Popen([ESB, "src/main.js", "--minify-syntax", "--outfile=out/main.js", "--rewrite=rules.lint", "--watch", "--no-cache"],
                         cwd=dest, stdout=log, stderr=subprocess.STDOUT)
    try:
        time.sleep(1.5)
        before = open(dest + "/out/main.js").read()
        shutil.copy(rules, dest + "/rules.lint")
        time.sleep(1.5)
        after = open(dest + "/out/main.js").read()
    finally:
        w.terminate()
        w.wait()
        log.close()
    check("beta feature" in before and "beta feature" not in after and "[watch] build 2" in open(OUT + "/watch.log").read(),
          "watching: editing the rewrites rebuilds with them")

    # A spec's rewrite.
    spec = OUT + "/rewrite.bundler"
    open(spec, "w").write('bundler\ntarget app\n  entry "src/main.js"\n  outfile "%s"\n  minify syntax\n  rewrite "%s"\nend\n' % (OUT + "/spec.js", rules))
    p = subprocess.run([SPEC, spec], cwd=FIXTURE, capture_output=True, text=True)
    check(p.returncode == 0 and os.path.exists(OUT + "/spec.js") and "beta feature" not in open(OUT + "/spec.js").read(),
          "a build spec names rewrites with `rewrite`")

    # Fixes.
    dest = OUT + "/fix"
    shutil.copytree(LINT_FIXTURE, dest, symlinks=True)
    fixes = OUT + "/fixes.lint"
    open(fixes, "w").write(open(os.path.join(ROOT, "examples/ship.lint")).read()
                           + 'lint loose-equality warning at P "{P} compares with ==" :- ships(_, P), code(P, `$A == $B`) ;\n'
                           + 'fix loose-equality `$A == $B` => `$A === $B` ;\n'
                           + 'lint package-pad warning at P "pad" :- ships(_, P), code(P, `($S).slice($$X)`) ;\n'
                           + 'fix package-pad `($S).slice($$X)` => `$S` ;\n')
    with open(dest + "/src/ui/format.js", "a") as f:
        f.write("export function same(a, b) {\n  return a == b;\n}\n")
    with open(dest + "/src/main.js", "a") as f:
        f.write('import { same } from "./ui/format.js";\nconsole.warn(same(1, 1));\n')
    before = {p: open(os.path.join(dest, p)).read() for p in ["src/admin/panel.js", "src/ui/view.js", "src/ui/format.js", "node_modules/tiny-dup/index.js"]}
    p = esb(["src/main.js", "--splitting", "--format=esm", "--outdir=out", "--lint=" + fixes, "--fix"], cwd=dest)
    after = {k: open(os.path.join(dest, k)).read() for k in before}
    check(p.returncode == 0 and not os.path.exists(dest + "/out"), "--fix writes the fixes and nothing else")
    check(after["src/admin/panel.js"] == before["src/admin/panel.js"].replace("  debugger;\n", ""), "a debugger statement taken out, with its line")
    check(after["src/ui/view.js"] == before["src/ui/view.js"].replace('  console.log("render", title);\n', ""), "a console.log statement taken out, with its line")
    check(after["src/ui/format.js"] == before["src/ui/format.js"].replace("return a == b;", "return a === b;"), "a template filled in with the code its variables matched")
    check(after["node_modules/tiny-dup/index.js"] == before["node_modules/tiny-dup/index.js"], "a package's files are not the project's to fix")
    again = esb(["src/main.js", "--splitting", "--format=esm", "--outdir=out", "--lint=" + fixes], cwd=dest)
    found = again.stdout + again.stderr
    check("[debugger-shipped]" not in found and "[console-shipped]" not in found and "[loose-equality]" not in found and "[secret-shipped]" in found,
          "linted again, what was fixed is not found, and the rest still is")

    print("rewrite-check: %d passed, %d failed" % (passed, len(failures)))
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
