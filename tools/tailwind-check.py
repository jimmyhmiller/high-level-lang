#!/usr/bin/env python3
"""Tailwind CSS v4 as our build makes it, against Tailwind's own (installed in each app).

For each app (a copy of it without build outputs, its node_modules linked), each stylesheet under
src/ is given to Tailwind's own Node API exactly as @tailwindcss/vite gives it (tools/tailwind-oracle.mjs:
the same sources, oxide's scanner, compile and build)
and to ours (out/bin/twc, the same Tailwind functions the bundler's stylesheet hook calls):
  - whether Tailwind treats it as its own (a root),
  - the candidates the scanner extracts, as a set,
  - the compiled stylesheet (before CSS lowering), byte for byte.
Production and development output are exercised in tools/tailwind-build-check.mjs.
Then the compiler alone over the stylesheets in tests/apps/tailwind (every class and variant Tailwind's
design system lists, and directives: @theme options, @utility, @custom-variant, @variant, @apply,
theme functions, @source inline, prefix, important, @reference), with fixed candidates.

usage: tailwind-check.py [TWC]    (apps in out/real/apps; prepare them with out/real/prepare.py NAME…)
"""
import json, os, shutil, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TWC = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(ROOT, "out/bin/twc")
APPS = ["start-tailwind-v4", "start-basic-react-query", "start-basic-static", "basic-file-based", "kitchen-sink-file-based",
        "quickstart-file-based"]
OUT = os.path.join(ROOT, "out/tailwind-check")
passed, failures = 0, []


def check(ok, what):
    global passed
    if ok:
        passed += 1
        print("ok  ", what)
    else:
        failures.append(what)
        print("FAIL", what)


def first_difference(want, ours):
    a, b = want.split("\n"), ours.split("\n")
    i = next((i for i in range(min(len(a), len(b))) if a[i] != b[i]), min(len(a), len(b)))
    return f"first difference at line {i + 1}: want {a[i] if i < len(a) else '<end>'!r}, ours {b[i] if i < len(b) else '<end>'!r}"


def twc(*args):
    p = subprocess.run([TWC, *args], capture_output=True, text=True, timeout=600)
    return p.returncode, p.stdout, p.stderr


def copied(app):
    src = os.path.join(ROOT, "out/real/apps", app)
    dst = os.path.join(OUT, app)
    shutil.rmtree(dst, ignore_errors=True)
    shutil.copytree(src, dst, symlinks=True, ignore=shutil.ignore_patterns("node_modules", "dist", "dist-*", ".output", ".tanstack", "coverage"))
    os.symlink(os.path.join(src, "node_modules"), os.path.join(dst, "node_modules"))
    return dst


def check_app(app):
    src = os.path.join(ROOT, "out/real/apps", app)
    if not os.path.exists(os.path.join(src, "node_modules/@tailwindcss/oxide")):
        check(False, f"{app}: not installed in out/real/apps (python3 out/real/prepare.py {app}, which copies TanStack's example and installs it)")
        return
    dst = copied(app)
    sheets = sorted(os.path.relpath(os.path.join(d, f), dst) for d, _, fs in os.walk(os.path.join(dst, "src")) for f in fs if f.endswith(".css"))
    p = subprocess.run(["node", os.path.join(ROOT, "tools/tailwind-oracle.mjs"), dst, *sheets], capture_output=True, text=True, timeout=600)
    if p.returncode != 0:
        check(False, f"{app}: Tailwind's own compiler failed: {p.stderr[-800:]}")
        return
    for line in p.stdout.splitlines():
        want = json.loads(line)
        sheet = os.path.join(dst, want["file"])
        name = f"{app} {want['file']}"
        code, out, err = twc("root", sheet)
        ours_root = out.strip() == "true"
        check(code == 0 and ours_root == want["root"], f"{name}: {'a' if want['root'] else 'not a'} Tailwind stylesheet" + ("" if code == 0 else ": " + err[-600:]))
        if not want["root"]:
            continue
        code, out, err = twc("candidates", sheet)
        ours = set(x for x in out.split("\n") if x)
        theirs = set(want["candidates"])
        check(code == 0 and ours == theirs, f"{name}: the scanner's {len(theirs)} candidates" + ("" if code == 0 and ours == theirs else
              f": {len(ours - theirs)} extra {sorted(ours - theirs)[:8]}, {len(theirs - ours)} missing {sorted(theirs - ours)[:8]}" + (" " + err[-600:] if code else "")))
        code, out, err = twc("compiled", sheet)
        check(code == 0 and out == want["compiled"], f"{name}: compiled, {len(want['compiled'])} bytes" + ("" if code == 0 and out == want["compiled"] else
              ": " + (first_difference(want["compiled"], out) if code == 0 else err[-600:])))


def check_compiler():
    app = "start-tailwind-v4"
    src = os.path.join(ROOT, "out/real/apps", app)
    if not os.path.exists(os.path.join(src, "node_modules/tailwindcss")):
        check(False, f"the compiler's coverage needs out/real/apps/{app} (python3 out/real/prepare.py {app})")
        return
    dst = os.path.join(OUT, "coverage")
    shutil.rmtree(dst, ignore_errors=True)
    os.makedirs(dst)
    shutil.copy(os.path.join(src, "package.json"), dst)
    os.symlink(os.path.join(src, "node_modules"), os.path.join(dst, "node_modules"))
    fixtures = os.path.join(ROOT, "tests/apps/tailwind")
    for f in os.listdir(fixtures):
        shutil.copy(os.path.join(fixtures, f), dst)
    every = os.path.join(dst, "every.candidates")
    for sheet, extra in [("plain.css", None), ("features.css", "features.candidates"), ("prefixed.css", "prefixed.candidates")]:
        path = os.path.join(dst, sheet)
        if extra is None or sheet == "features.css":
            # Every class and variant the design system lists, and hand-written shapes (tools/tailwind-coverage.mjs).
            args = ["node", os.path.join(ROOT, "tools/tailwind-coverage.mjs"), dst, path] + ([os.path.join(dst, extra)] if extra else [])
        else:
            args = ["node", os.path.join(ROOT, "tools/tailwind-compile.mjs"), dst, path, os.path.join(dst, extra)]
        p = subprocess.run(args, capture_output=True, text=True, timeout=900)
        if p.returncode != 0:
            check(False, f"compiler {sheet}: Tailwind's own failed: {p.stderr[-600:]}")
            continue
        want = json.loads(p.stdout)
        open(every, "w").write("\n".join(want["candidates"]) + "\n")
        code, out, err = twc("build", path, every)
        same = code == 0 and out == want.get("compiled")
        check(same, f"compiler {sheet}: {len(want['candidates'])} candidates, {len(want.get('compiled', ''))} bytes"
              + ("" if same else ": " + (first_difference(want.get("compiled", ""), out) if code == 0 else err[-600:])))


def main():
    shutil.rmtree(OUT, ignore_errors=True)
    os.makedirs(OUT)
    if not os.path.exists(TWC):
        check(False, f"{TWC} is not built (tools/build-tools.sh)")
    else:
        for app in APPS:
            check_app(app)
        check_compiler()
    print(f"tailwind-check: {passed} passed, {len(failures)} failed")
    sys.exit(1 if failures else 0)


main()
