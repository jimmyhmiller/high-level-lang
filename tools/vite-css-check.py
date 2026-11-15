#!/usr/bin/env python3
"""A stylesheet's `@import`s as Vite resolves them, against Vite itself.

A page whose stylesheet imports a package by name (its `exports` with the `style` condition, its
`style` field, its `main`), a package's subpath, a file beside it without `.css` (Vite tries the
name relative first), and a relative file, is built by us (`esb index.html`, a Vite-compatible
build) and by Vite 8 (installed in out/real/apps/start-tailwind-v4); both stylesheets are minified
again by esbuild, so the minifiers' spelling does not matter, and must be the same. Plain esbuild
builds keep esbuild's rule: a bare `@import` is a relative URL.

usage: vite-css-check.py [ESB]
"""
import glob, os, shutil, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ESB = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(ROOT, "out/bin/esb")
VITE_APP = os.path.join(ROOT, "out/real/apps/start-tailwind-v4")
ESBUILD = os.path.join(ROOT, "tests/node_modules/.bin/esbuild")
OUT = os.path.join(ROOT, "out/vite-css-check")
passed, failures = 0, []

FILES = {
    "index.html": '<!doctype html><html><head></head><body><script type="module" src="./src/main.js"></script></body></html>\n',
    "package.json": '{ "name": "vite-css-fixture", "private": true, "type": "module" }\n',
    "src/main.js": 'import "./styles.css"\ndocument.body.dataset.ready = "yes"\n',
    "src/styles.css": '@import "by-exports";\n@import "by-style";\n@import "by-main";\n@import "by-exports/extra.css";\n@import "beside";\n@import "./local.css";\n.own { color: red }\n',
    "src/beside.css": ".beside { color: teal }\n",
    "src/local.css": ".local { color: olive }\n",
    "node_modules/by-exports/package.json": '{ "name": "by-exports", "exports": { ".": { "style": "./styles/index.css", "import": "./index.js" }, "./extra.css": "./styles/extra.css" } }\n',
    "node_modules/by-exports/index.js": "export default 1\n",
    "node_modules/by-exports/styles/index.css": ".by-exports { color: blue }\n",
    "node_modules/by-exports/styles/extra.css": ".by-exports-extra { color: navy }\n",
    "node_modules/by-style/package.json": '{ "name": "by-style", "style": "dist/style.css", "main": "index.js" }\n',
    "node_modules/by-style/index.js": "export default 1\n",
    "node_modules/by-style/dist/style.css": ".by-style { color: green }\n",
    "node_modules/by-main/package.json": '{ "name": "by-main", "main": "main.css" }\n',
    "node_modules/by-main/main.css": ".by-main { color: purple }\n",
}


def check(ok, what):
    global passed
    if ok:
        passed += 1
        print("ok  ", what)
    else:
        failures.append(what)
        print("FAIL", what)


def minified(css):
    p = subprocess.run([ESBUILD, "--loader=css", "--minify"], input=css, capture_output=True, text=True)
    return p.stdout if p.returncode == 0 else "esbuild could not read it: " + p.stderr


def main():
    shutil.rmtree(OUT, ignore_errors=True)
    for rel, text in FILES.items():
        path = os.path.join(OUT, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "w").write(text)
    p = subprocess.run([ESB, "index.html", "--outdir=dist"], cwd=OUT, capture_output=True, text=True, timeout=300)
    check(p.returncode == 0, "the page builds" + ("" if p.returncode == 0 else ": " + (p.stdout + p.stderr)[-1200:]))
    ours = "".join(open(f).read() for f in sorted(glob.glob(os.path.join(OUT, "dist/assets/*.css"))))
    for name in ["by-exports", "by-style", "by-main", "by-exports-extra", "beside", "local", "own"]:
        check(f".{name}" in ours, f"the stylesheet holds .{name}")
    if not os.path.exists(os.path.join(VITE_APP, "node_modules/.bin/vite")):
        check(False, "Vite is not installed in out/real/apps/start-tailwind-v4 (python3 out/real/prepare.py start-tailwind-v4)")
    else:
        v = subprocess.run([os.path.join(VITE_APP, "node_modules/.bin/vite"), "build", "--outDir", "dist-vite", "--logLevel", "error"],
                           cwd=OUT, capture_output=True, text=True, timeout=300)
        check(v.returncode == 0, "Vite builds the page" + ("" if v.returncode == 0 else ": " + (v.stdout + v.stderr)[-1200:]))
        theirs = "".join(open(f).read() for f in sorted(glob.glob(os.path.join(OUT, "dist-vite/assets/*.css"))))
        check(minified(ours) == minified(theirs), "the stylesheet is Vite's, rule for rule"
              + ("" if minified(ours) == minified(theirs) else f": ours {minified(ours)!r}, Vite's {minified(theirs)!r}"))
    plain = subprocess.run([ESB, "src/styles.css", "--bundle", "--outfile=plain.css"], cwd=OUT, capture_output=True, text=True, timeout=300)
    check(plain.returncode != 0 and "by-exports" in plain.stdout + plain.stderr,
          "a plain (esbuild-compatible) build still reads a bare @import as a relative URL")
    print(f"vite-css-check: {passed} passed, {len(failures)} failed")
    sys.exit(1 if failures else 0)


main()
