#!/usr/bin/env python3
"""The TanStack Start application (benchmarks/tanstack-start) built by us as Start's Vite plugin builds it.

- `esb --tanstack-start` on a copy of the application without its route tree: the tree comes back as
  Start's generator writes it, with its footer, byte for byte.
- It writes dist/client (assets under assets/, no page) and dist/server/server.js.
- The browser's build has none of the server-only module, and the server function ids are Vite's.
- The build runs as Start's server runs it, in a browser (tools/start-app-check.mjs).
- Its browser JavaScript is about the size of Vite's (when benchmarks/tanstack-start has Vite).

usage: start-check.py [ESB]
"""
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ESB = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(ROOT, "out/bin/esb")
APP = os.path.join(ROOT, "benchmarks/tanstack-start")
OUT = os.path.join(ROOT, "out/start-check")

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


def js_bytes(d):
    return sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fs in os.walk(d) for f in fs if f.endswith(".js"))


def main():
    shutil.rmtree(OUT, ignore_errors=True)
    app = os.path.join(OUT, "app")
    shutil.copytree(APP, app, symlinks=True, ignore=shutil.ignore_patterns("node_modules", "dist*", "START-SPEC.md"))
    os.symlink(os.path.join(APP, "node_modules"), os.path.join(app, "node_modules"))
    committed = open(os.path.join(APP, "src/routeTree.gen.ts")).read()
    os.remove(os.path.join(app, "src/routeTree.gen.ts"))

    p = subprocess.run([ESB, "--tanstack-start"], cwd=app, capture_output=True, text=True, timeout=600)
    check(p.returncode == 0, "the application builds" + ("" if p.returncode == 0 else ": " + (p.stdout + p.stderr)[-1200:]))
    if p.returncode != 0:
        return
    tree = os.path.join(app, "src/routeTree.gen.ts")
    check(os.path.exists(tree) and open(tree).read() == committed, "its route tree comes back as Start's generator wrote it, footer and all")
    client, server = os.path.join(app, "dist/client"), os.path.join(app, "dist/server")
    check(os.path.exists(os.path.join(server, "server.js")) and os.path.isdir(os.path.join(client, "assets"))
          and not os.path.exists(os.path.join(client, "index.html")), "dist/client/assets and dist/server/server.js, and no page")
    ids = set(re.findall(r'"([0-9a-f]{64})"', "".join(open(os.path.join(dp, f)).read() for dp, _, fs in os.walk(client) for f in fs if f.endswith(".js"))))
    check({"779065a854cd3c8a83fc1f6d279993fb0c1460e9882d64d8e4a9c5d1a7f37ab0", "4a6fc7c69795985fd86cb3abcfb13c573bafe2093c0f67aaee631bf215685906"} <= ids,
          "server functions have the ids Vite's build gives them")
    run = subprocess.run(["node", os.path.join(ROOT, "tools/start-app-check.mjs"), os.path.join(server, "server.js"), client],
                         capture_output=True, text=True, timeout=300)
    last = (run.stdout + run.stderr).strip().splitlines()[-1] if (run.stdout + run.stderr).strip() else ""
    check(run.returncode == 0, "it runs as Start's server runs it, in a browser: " + last + ("" if run.returncode == 0 else "\n" + run.stdout[-1500:]))

    vite = os.path.join(APP, "node_modules/.bin/vite")
    if os.path.exists(vite):
        v = subprocess.run([vite, "build", "--outDir", os.path.join(OUT, "vite")], cwd=app, capture_output=True, text=True, timeout=300)
        if v.returncode == 0:
            ours, theirs = js_bytes(client), js_bytes(os.path.join(OUT, "vite", "client"))
            check(theirs > 0 and ours < theirs * 1.15, "browser JavaScript: ours %d bytes, Vite's %d" % (ours, theirs))
    print("start-check: %d passed, %d failed" % (passed, len(failures)))


if __name__ == "__main__":
    main()
    sys.exit(1 if failures else 0)
