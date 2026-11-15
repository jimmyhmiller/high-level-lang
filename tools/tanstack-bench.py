#!/usr/bin/env python3
"""Production builds of the TanStack apps, ours against every bundler that can build them: wall time,
peak memory and the JavaScript written, each build a fresh process, interleaved, and each output
checked in Chrome before it counts.

Router (benchmarks/tanstack-router), each with TanStack's own plugin for it where one exists:
  ours       esb index.html --tanstack-router (route tree, route splitting)
  ours-warm  the same, starting from what a previous run kept (--cache); not comparable to the others
  vite       vite build with @tanstack/router-plugin/vite and @vitejs/plugin-react (Rolldown)
  rspack     Rspack with @tanstack/router-plugin/rspack and its SWC loader
  esbuild    esbuild with @tanstack/router-plugin/esbuild: the route tree only, as the plugin refuses
             route splitting with esbuild
  turbopack  Turbopack's CLI on the app as written: no TanStack integration exists for it, so the
             committed route tree and no route splitting
Start (benchmarks/tanstack-start): ours (esb --tanstack-start) and vite (vite build with Start's
plugin), both builds, browser's and server's; checked by tools/start-app-check.mjs.

usage: tanstack-bench.py [--runs=N] [--apps=router,start] [ESB]
"""
import argparse
import os
import re
import shutil
import statistics
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN = os.path.join(ROOT, "../..") if "/.worktrees/" in ROOT else ROOT
parser = argparse.ArgumentParser()
parser.add_argument("--runs", type=int, default=5)
parser.add_argument("--apps", default="router,start")
parser.add_argument("esb", nargs="?", default=os.path.join(ROOT, "out/bin/esb"))
args = parser.parse_args()
ESB = os.path.abspath(args.esb)
WORK = os.path.join(ROOT, "out/tanstack-bench")
BENCH = os.path.join(ROOT, "benchmarks/tanstack-bench")
RSPACK = os.path.join(os.path.abspath(MAIN), "benchmarks/bundlers/node_modules/@rspack/core/dist/index.js")
TURBOPACK = os.path.join(os.path.abspath(MAIN), "out/bin/turbopack-cli-4ebb2b7-define")
PROD = '--define:process.env.NODE_ENV="production"'


def app_copy(name, fixture):
    """A copy of a fixture inside the repository (Turbopack reads nothing outside its root), its
    packages linked, with nothing built."""
    d = os.path.join(WORK, name)
    shutil.rmtree(d, ignore_errors=True)
    shutil.copytree(fixture, d, symlinks=True, ignore=shutil.ignore_patterns("node_modules", "dist*", "START-SPEC.md"))
    os.symlink(os.path.join(fixture, "node_modules"), os.path.join(d, "node_modules"))
    return d


def router_tools(app):
    out = lambda t: os.path.join(WORK, "router-out", t)
    return {
        "ours": dict(cmd=[ESB, "index.html", "--outdir=" + out("ours"), PROD, "--tanstack-router", "--minify", "--no-cache", "--strategy=once"],
                     out=out("ours"), js=out("ours"), page=None, split=True),
        "ours-warm": dict(cmd=[ESB, "index.html", "--outdir=" + out("ours-warm"), PROD, "--tanstack-router", "--minify", "--cache",
                               "--cache-dir=" + os.path.join(WORK, "router-cache")],
                          out=out("ours-warm"), js=out("ours-warm"), page=None, split=True),
        "vite": dict(cmd=[os.path.join(app, "node_modules/.bin/vite"), "build", "--minify", "--outDir", out("vite"), "--logLevel", "warn"],
                     out=out("vite"), js=out("vite"), page=None, split=True),
        "rspack": dict(cmd=["node", os.path.join(BENCH, "rspack.mjs"), app, out("rspack"), RSPACK], out=out("rspack"), js=out("rspack"),
                       page="rspack", split=True),
        "esbuild": dict(cmd=["node", os.path.join(BENCH, "esbuild.mjs"), app, out("esbuild")], out=out("esbuild"), js=out("esbuild"),
                        page="main.js", split=False),
        "turbopack": dict(cmd=[TURBOPACK, "build", "./" + os.path.relpath(os.path.join(app, "src/main.tsx"), ROOT), "--dir", app, "--root", ROOT,
                               "--target", "browser", "--no-sourcemap", '--define=process.env.NODE_ENV="production"'],
                          out=os.path.join(app, "dist"), js=os.path.join(app, "dist"), page="turbopack", split=False),
    }


def start_tools(apps):
    return {
        "ours": dict(cmd=[ESB, "--tanstack-start", "--no-cache", "--strategy=once"], cwd=apps["ours"],
                     out=os.path.join(apps["ours"], "dist"), js=os.path.join(apps["ours"], "dist/client")),
        "vite": dict(cmd=[os.path.join(apps["vite"], "node_modules/.bin/vite"), "build", "--logLevel", "warn"], cwd=apps["vite"],
                     out=os.path.join(apps["vite"], "dist"), js=os.path.join(apps["vite"], "dist/client")),
    }


def measured(cmd, cwd):
    """Wall seconds, peak resident megabytes and instructions retired of one build, by /usr/bin/time."""
    p = subprocess.run(["/usr/bin/time", "-l"] + cmd, cwd=cwd, capture_output=True, text=True, timeout=600)
    if p.returncode != 0:
        raise SystemExit("failed: " + " ".join(cmd) + "\n" + (p.stdout + p.stderr)[-2000:])
    wall = float(re.search(r"([\d.]+) real", p.stderr).group(1))
    rss = int(re.search(r"(\d+)\s+maximum resident set size", p.stderr).group(1)) / 1e6
    ins = re.search(r"(\d+)\s+instructions retired", p.stderr)
    return wall, rss, int(ins.group(1)) if ins else 0


def js_bytes(d):
    return sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fs in os.walk(d) for f in fs if f.endswith(".js"))


def report(title, rows):
    print("\n" + title)
    print("  %-10s %9s %9s %10s %9s %11s   %s" % ("", "median s", "min s", "peak MB", "Ginstr", "JS bytes", "checked"))
    for name, r in rows.items():
        print("  %-10s %9.3f %9.3f %10.0f %9.2f %11d   %s" % (name, statistics.median(r["wall"]), min(r["wall"]), statistics.median(r["rss"]),
                                                       statistics.median(r["ins"]) / 1e9, r["bytes"], r["checked"]))


def router():
    app = app_copy("router", os.path.join(ROOT, "benchmarks/tanstack-router"))
    for d in ["router-out", "router-cache"]:
        shutil.rmtree(os.path.join(WORK, d), ignore_errors=True)
    tools = router_tools(app)
    if not os.path.exists(TURBOPACK):
        raise SystemExit("Turbopack's CLI is not built: " + TURBOPACK)
    rows = {t: dict(wall=[], rss=[], ins=[], bytes=0, checked="") for t in tools}
    # The warm row starts from a cache one build made.
    subprocess.run(tools["ours-warm"]["cmd"], cwd=app, capture_output=True, check=True)
    for run in range(args.runs):
        for name, t in tools.items():
            if name != "ours-warm":
                shutil.rmtree(t["out"], ignore_errors=True)
            w, r, i = measured(t["cmd"], app)
            rows[name]["wall"].append(w); rows[name]["rss"].append(r); rows[name]["ins"].append(i)
    for name, t in tools.items():
        if t["page"]:
            subprocess.run(["node", os.path.join(BENCH, "page.mjs"), t["out"],
                            t["page"] if t["page"] != "rspack" else next(f for f in os.listdir(t["out"]) if f.startswith("index-") and f.endswith(".js"))],
                           check=True)
        rows[name]["bytes"] = js_bytes(t["js"])
        c = subprocess.run(["node", os.path.join(ROOT, "tools/router-app-check.mjs"), t["out"]] + (["--split"] if t["split"] else []),
                           capture_output=True, text=True, timeout=300)
        rows[name]["checked"] = (c.stdout.strip().splitlines() or ["?"])[-1].replace("router-app-check: ", "")
    report("TanStack Router app, production build (%d runs each, interleaved)" % args.runs, rows)


def start():
    apps = {t: app_copy("start-" + t, os.path.join(ROOT, "benchmarks/tanstack-start")) for t in ["ours", "vite"]}
    tools = start_tools(apps)
    rows = {t: dict(wall=[], rss=[], ins=[], bytes=0, checked="") for t in tools}
    for run in range(args.runs):
        for name, t in tools.items():
            shutil.rmtree(t["out"], ignore_errors=True)
            w, r, i = measured(t["cmd"], t["cwd"])
            rows[name]["wall"].append(w); rows[name]["rss"].append(r); rows[name]["ins"].append(i)
    for name, t in tools.items():
        rows[name]["bytes"] = js_bytes(t["js"])
        c = subprocess.run(["node", os.path.join(ROOT, "tools/start-app-check.mjs"), os.path.join(t["out"], "server/server.js"), t["js"]],
                           capture_output=True, text=True, timeout=300)
        rows[name]["checked"] = (c.stdout.strip().splitlines() or ["?"])[-1].replace("start-app-check: ", "")
    report("TanStack Start app, production build, browser's and server's (%d runs each, interleaved)" % args.runs, rows)


print("load average %.1f" % os.getloadavg()[0])
if "router" in args.apps:
    router()
if "start" in args.apps:
    start()
