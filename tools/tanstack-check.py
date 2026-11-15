#!/usr/bin/env python3
"""The TanStack Router application (benchmarks/tanstack-router) built as Vite builds it, by us.

- `esb index.html --outdir=… --tanstack-router` on a copy of the application without its route tree:
  the tree comes back as TanStack's generator writes it, byte for byte.
- The page is written as Vite writes one: the entry chunk loaded from the head, what it imports
  preloaded, its stylesheet linked, and the source's module script gone.
- Each route's component is in a chunk of its own, and the entry's chunks have none of them.
- The built application, unminified and minified, runs in a browser: every route by link and by
  address, search validation, a loader's error, the not-found page, and scripts loaded only when a
  route is visited (tools/router-app-check.mjs).
- Its split build is about the size of Vite's (when benchmarks/tanstack-router has Vite installed).

usage: tanstack-check.py [ESB]
"""
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ESB = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(ROOT, "out/bin/esb")
APP = os.path.join(ROOT, "benchmarks/tanstack-router")
OUT = os.path.join(ROOT, "out/tanstack-check")

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


def build(app, out, extra):
    return subprocess.run([ESB, "index.html", "--outdir=" + out, '--define:process.env.NODE_ENV="production"', "--tanstack-router"] + extra,
                          cwd=app, capture_output=True, text=True, timeout=300)


def browser(dist):
    p = subprocess.run(["node", os.path.join(ROOT, "tools/router-app-check.mjs"), dist, "--split"], capture_output=True, text=True, timeout=300)
    return p.returncode == 0, (p.stdout + p.stderr).strip().splitlines()[-1] if (p.stdout + p.stderr).strip() else ""


def main():
    shutil.rmtree(OUT, ignore_errors=True)
    app = os.path.join(OUT, "app")
    shutil.copytree(APP, app, symlinks=True, ignore=shutil.ignore_patterns("node_modules", "dist*"))
    os.symlink(os.path.join(APP, "node_modules"), os.path.join(app, "node_modules"))
    committed = open(os.path.join(APP, "src/routeTree.gen.ts")).read()
    os.remove(os.path.join(app, "src/routeTree.gen.ts"))

    p = build(app, "dist", [])
    check(p.returncode == 0, "the application builds from its page" + ("" if p.returncode == 0 else ": " + (p.stdout + p.stderr)[-800:]))
    if p.returncode != 0:
        return
    tree = os.path.join(app, "src/routeTree.gen.ts")
    check(os.path.exists(tree) and open(tree).read() == committed, "its route tree comes back as TanStack's generator wrote it")

    dist = os.path.join(app, "dist")
    page = open(os.path.join(dist, "index.html")).read()
    scripts = re.findall(r'<script type="module" crossorigin src="/(assets/[^"]+\.js)"></script>', page)
    preloads = re.findall(r'<link rel="modulepreload" crossorigin href="/(assets/[^"]+)">', page)
    styles = re.findall(r'<link rel="stylesheet" crossorigin href="/(assets/[^"]+\.css)">', page)
    check(len(scripts) == 1 and "/src/main.tsx" not in page and all(os.path.exists(os.path.join(dist, f)) for f in scripts + preloads + styles)
          and len(styles) == 1 and page.index(scripts[0]) < page.index("</head>"),
          "the page loads the entry's chunk from its head, preloads %d chunk(s), links its stylesheet" % len(preloads))

    initial = "\n".join(open(os.path.join(dist, f)).read() for f in scripts + preloads)
    lazy = [f for f in os.listdir(os.path.join(dist, "assets")) if f.endswith(".js") and "assets/" + f not in scripts + preloads]
    marks = {"about": "routes are files", "pricing": "Pricing: ", "dashboard": "function Dashboard(", "post": "post-title"}
    check(all(m not in initial for m in marks.values()), "no route component's code loads with the page")
    check(all(any(m in open(os.path.join(dist, "assets", f)).read() for f in lazy) for m in marks.values()),
          "each is in a chunk of its own: %d chunks the page loads later" % len(lazy))

    ok, last = browser(dist)
    check(ok, "the build runs in a browser: " + last)
    p = build(app, "dist-min", ["--minify"])
    ok, last = browser(os.path.join(app, "dist-min")) if p.returncode == 0 else (False, (p.stdout + p.stderr)[-400:])
    check(ok, "minified, too: " + last)

    vite = os.path.join(APP, "node_modules/.bin/vite")
    if os.path.exists(vite):
        v = subprocess.run([vite, "build", "--minify", "--outDir", os.path.join(OUT, "vite")], cwd=app, capture_output=True, text=True, timeout=300)
        if v.returncode == 0:
            ours = sum(os.path.getsize(os.path.join(app, "dist-min/assets", f)) for f in os.listdir(os.path.join(app, "dist-min/assets")) if f.endswith(".js"))
            theirs = sum(os.path.getsize(os.path.join(OUT, "vite/assets", f)) for f in os.listdir(os.path.join(OUT, "vite/assets")) if f.endswith(".js"))
            check(ours < theirs * 1.1, "minified JavaScript %d bytes, Vite's %d" % (ours, theirs))
    print("tanstack-check: %d passed, %d failed" % (passed, len(failures)))


if __name__ == "__main__":
    main()
    sys.exit(1 if failures else 0)
