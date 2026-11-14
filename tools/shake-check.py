#!/usr/bin/env python3
"""Checks shaking what an object holds (link.facts' `kept-prop` and namespace aliases).

Every case in tests/apps/shake is built by us and by esbuild, minified, and run in Node: both must
print the same. Then what the case was written to show: what nothing reads is gone (a namespace's
exports reached through `const { a } = ns` or `const api = ns`, an exported object literal's and a
default-export object's properties, and what only those read), and what reads an object any other
way keeps all of it (`Object.keys`, `for in`, spread, `hasOwnProperty`, passing it to a function,
reading it through a namespace, `this` in a method), and a property whose value does something as it
loads stays. A split build where two routes read different properties keeps both and runs each.

usage: shake-check.py [ESB]
"""
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ESB = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(ROOT, "out/bin/esb")
ESBUILD = os.path.join(ROOT, "tests/node_modules/.bin/esbuild")
CASES = os.path.join(ROOT, "tests/apps/shake")
OUT = os.path.join(ROOT, "out/shake-check")

# Each case: markers that must be gone from our output, and markers that must stay.
EXPECT = {
    "case-destructure": (["BETA_UNUSED", "GAMMA_UNUSED"], []),
    "case-alias": (["BETA_UNUSED", "GAMMA_UNUSED"], []),
    "case-member": (["LERP_UNUSED", "SMOOTH_UNUSED", "VERSION_UNUSED", "HEAVY_ONLY_IF_LERP"], []),
    "case-default": (["STRINGIFY_UNUSED"], []),
    "case-keys": ([], ["LERP_UNUSED", "SMOOTH_UNUSED", "VERSION_UNUSED"]),
    "case-forin": ([], ["LERP_UNUSED", "VERSION_UNUSED"]),
    "case-spread": ([], ["LERP_UNUSED", "VERSION_UNUSED"]),
    "case-reflect": ([], ["LERP_UNUSED"]),
    "case-passed": ([], ["LERP_UNUSED", "SMOOTH_UNUSED"]),
    "case-namespace": ([], ["SMOOTH_UNUSED", "HEAVY_ONLY_IF_LERP"]),
    "case-impure": (["DROPPED_UNUSED"], ["SIDE_EFFECT_RUNS", "C_KEPT_THIS"]),
    "case-reexported": (["BETA_UNUSED", "GAMMA_UNUSED"], []),
    "case-prop-import": (["SMOOTH_UNUSED", "VERSION_UNUSED"], ["HEAVY_ONLY_IF_LERP"]),
    "case-default-pattern": ([], ["BETA_UNUSED"]),
}

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


def node(path):
    p = subprocess.run(["node", path], capture_output=True, text=True)
    return p.stdout + p.stderr


def main():
    shutil.rmtree(OUT, ignore_errors=True)
    os.makedirs(OUT)
    for case, (gone, kept) in EXPECT.items():
        ours, theirs = os.path.join(OUT, case + ".js"), os.path.join(OUT, case + ".esbuild.js")
        a = subprocess.run([ESB, case + ".js", "--minify", "--outfile=" + ours], cwd=CASES, capture_output=True, text=True)
        b = subprocess.run([ESBUILD, case + ".js", "--bundle", "--minify", "--outfile=" + theirs], cwd=CASES, capture_output=True, text=True)
        if a.returncode != 0 or b.returncode != 0:
            check(False, "%s builds (%s%s)" % (case, a.stderr[-300:], b.stderr[-300:]))
            continue
        text = open(ours).read()
        check(node(ours) == node(theirs), "%s prints what esbuild's prints" % case)
        check(all(g not in text for g in gone) and all(k in text for k in kept),
              "%s: gone %s, kept %s" % (case, gone or "nothing", kept or "nothing"))
    # Two routes reading different properties of one object, split: both stay, each route runs.
    out = os.path.join(OUT, "split")
    p = subprocess.run([ESB, "route-a.js", "route-b.js", "--splitting", "--format=esm", "--minify", "--outdir=" + out],
                       cwd=CASES, capture_output=True, text=True)
    open(os.path.join(out, "package.json"), "w").write('{"type":"module"}') if p.returncode == 0 else None
    texts = "".join(open(os.path.join(out, f)).read() for f in os.listdir(out) if f.endswith(".js")) if p.returncode == 0 else ""
    check(p.returncode == 0 and node(os.path.join(out, "route-a.js")).strip() == "1" and node(os.path.join(out, "route-b.js")).strip() == "SMOOTH_UNUSED4"
          and "LERP_UNUSED" not in texts and "VERSION_UNUSED" not in texts,
          "split: each route's property stays, each route runs, and what neither reads is gone")
    print("shake-check: %d passed, %d failed" % (passed, len(failures)))
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
