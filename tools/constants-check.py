#!/usr/bin/env python3
"""Constants written in across modules (bundle.modules' `imported-constants`), against esbuild.

tests/apps/consts imports constants every way there is: by name, renamed, off a namespace, through
`export *` and `export { } from`, from a module loaded by `import()`; and names that are not
constants: one assigned, one declared after other statements, one made of an imported constant, one
two `export *`s both have, one a module's own export hides. Each is built by us and by esbuild with
--minify-syntax, whole and split; both print the same, and every branch esbuild removes (`DEAD_…`)
is gone from ours too.

usage: constants-check.py [ESB]
"""
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ESB = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(ROOT, "out/bin/esb")
E = os.path.join(ROOT, "tests/node_modules/.bin/esbuild")
APP = os.path.join(ROOT, "tests/apps/consts")
OUT = os.path.join(ROOT, "out/constants-check")

failures, passed = [], 0


def check(ok, what):
    global passed
    if ok:
        passed += 1
        print("ok  ", what)
    else:
        failures.append(what)
        print("FAIL", what)


def text(d):
    return "".join(open(os.path.join(d, f)).read() for f in sorted(os.listdir(d)) if f.endswith(".js"))


shutil.rmtree(OUT, ignore_errors=True)
for name, extra in [("whole", []), ("split", ["--splitting"])]:
    ours, theirs = os.path.join(OUT, name, "ours"), os.path.join(OUT, name, "esbuild")
    built = subprocess.run([ESB, os.path.join(APP, "main.js"), "--bundle", "--minify-syntax", "--format=esm", "--outdir=" + ours] + extra,
                           capture_output=True, text=True)
    subprocess.run([E, os.path.join(APP, "main.js"), "--bundle", "--minify-syntax", "--format=esm", "--outdir=" + theirs, "--log-level=error"] + extra,
                   check=True)
    if built.returncode != 0:
        check(False, name + ": builds: " + (built.stdout + built.stderr)[-800:])
        continue
    ran = [subprocess.run(["node", os.path.join(d, "main.js")], capture_output=True, text=True, timeout=30) for d in (ours, theirs)]
    check(ran[0].returncode == 0 and ran[0].stdout == ran[1].stdout and "lazy srv" in ran[0].stdout,
          name + ": prints what esbuild's prints: " + repr(ran[0].stdout if ran[0].returncode == 0 else ran[0].stderr[-400:]))
    dead_ours, dead_theirs = set(re.findall(r"DEAD_\w+", text(ours))), set(re.findall(r"DEAD_\w+", text(theirs)))
    check(dead_ours <= dead_theirs and len(dead_theirs) == 0,
          name + ": every branch a constant decides is gone, as in esbuild's (left: ours %s, esbuild's %s)" % (sorted(dead_ours), sorted(dead_theirs)))
print("constants-check: %d passed, %d failed" % (passed, len(failures)))
sys.exit(1 if failures else 0)
