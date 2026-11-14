#!/usr/bin/env python3
"""Builds from a fresh process, two binaries interleaved, round by round: what a cold build costs
and what a restart from the persistent cache costs.

  one-shot      no cache at all (the default strategy): the cold build that must not regress
  cache cold    --cache, the cache empty
  warm          --cache, nothing edited since the last run
  warm edit     --cache, one module edited since the last run (a module from the middle of the
                bundle's sources, given one new statement at its top, as tools/bench.py edits)

Each app is built in a directory of its own under out/restart-bench: the tests' apps, and their
node_modules as links, but for the package of the edited module, which is a copy. Cells are
medians: wall ms, M instructions retired, peak MB; and the cache's size on disk.

usage: restart-bench.py [--runs=N] [--apps=zod,three,...] [--flags=...] NAME=PATH NAME=PATH
"""
import json, os, re, shutil, statistics, subprocess, sys, time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS = os.path.join(REPO, "tests")
WORK = os.path.join(REPO, "out", "restart-bench")

runs, apps, flags, tools = 5, ["zod", "three", "d3", "rx", "datefns", "react", "all"], ["--minify"], []
for a in sys.argv[1:]:
    if a.startswith("--runs="): runs = int(a[7:])
    elif a.startswith("--apps="): apps = a[7:].split(",")
    elif a.startswith("--flags="): flags = a[8:].split()
    else:
        name, path = a.split("=", 1)
        tools.append((name, os.path.abspath(path)))


def real(p):
    return os.path.realpath(p)


def prepare(app):
    root = os.path.join(WORK, app)
    if os.path.exists(root): shutil.rmtree(root)
    os.makedirs(os.path.join(root, "node_modules"))
    shutil.copytree(os.path.join(TESTS, "apps"), os.path.join(root, "apps"), symlinks=True)
    entry = next(os.path.join("apps", f) for f in sorted(os.listdir(os.path.join(root, "apps"))) if f.split(".")[0] == app)
    nm = os.path.join(TESTS, "node_modules")
    for pkg in os.listdir(nm):
        os.symlink(os.path.join(nm, pkg), os.path.join(root, "node_modules", pkg))
    p = subprocess.run([tools[0][1], entry, "--sourcemap", "--outfile=out/map.js"], cwd=root, capture_output=True, text=True)
    if p.returncode != 0: sys.exit(f"{app}: {p.stderr[-800:]}")
    sources = [s for s in json.load(open(os.path.join(root, "out", "map.js.map")))["sources"] if "node_modules/" in s]
    rest = sources[len(sources) // 2].split("node_modules/", 1)[1].split("/")
    pkg = "/".join(rest[:2]) if rest[0].startswith("@") else rest[0]
    # The edited module's package, copied, so the tests' own is never written.
    link = os.path.join(root, "node_modules", pkg)
    os.remove(link)
    shutil.copytree(os.path.join(nm, pkg), link, symlinks=True)
    module = os.path.join("node_modules", *rest)
    if not real(os.path.join(root, module)).startswith(real(root) + os.sep):
        sys.exit(f"{app}: {module} is not in the bench's own copy")
    return root, entry, module


edits = 0
def edit(root, module, original):
    global edits
    edits += 1
    staged = os.path.join(root, ".staged")
    with open(staged, "w") as f: f.write(f'console.log("restart bench edit {edits}");\n' + original)
    os.replace(staged, os.path.join(root, module))


def measured(cmd, cwd):
    start = time.perf_counter()
    p = subprocess.run(["/usr/bin/time", "-l"] + cmd, cwd=cwd, capture_output=True, text=True)
    wall = (time.perf_counter() - start) * 1000
    if p.returncode != 0: sys.exit(f"{' '.join(cmd)}: {p.stderr[-1500:]}")
    ins = int(re.search(r"(\d+)\s+instructions retired", p.stderr).group(1)) / 1e6
    peak = int(re.search(r"(\d+)\s+maximum resident set size", p.stderr).group(1)) / 1e6
    return wall, ins, peak


def cache_size(d):
    return sum(os.path.getsize(os.path.join(d, f)) for f in os.listdir(d)) / 1e6 if os.path.isdir(d) else 0


ROWS = ["one-shot", "cache cold", "warm", "warm edit"]
results = {}
for app in apps:
    root, entry, module = prepare(app)
    original = open(os.path.join(root, module)).read()
    cells = {(t, r): [] for t, _ in tools for r in ROWS}
    sizes = {t: 0 for t, _ in tools}
    for i in range(runs):
        for name, path in tools:
            cache = os.path.join(root, "cache-" + name)
            base = [path, entry, "--outfile=out/" + name + ".js"] + flags
            with open(os.path.join(root, module), "w") as f: f.write(original)
            cells[(name, "one-shot")].append(measured(base, root))
            shutil.rmtree(cache, ignore_errors=True)
            cached = base + ["--cache", "--cache-dir=" + cache]
            cells[(name, "cache cold")].append(measured(cached, root))
            cells[(name, "warm")].append(measured(cached, root))
            edit(root, module, original)
            cells[(name, "warm edit")].append(measured(cached, root))
            sizes[name] = cache_size(cache)
        with open(os.path.join(root, module), "w") as f: f.write(original)
    for n, path in tools:
        measured([path, entry, "--outfile=out/" + n + ".js"] + flags, root)
    outs = [open(os.path.join(root, "out", n + ".js"), "rb").read() for n, _ in tools]
    same = all(o == outs[0] for o in outs)
    print(f"\n{app} ({module}){'' if same else '  OUTPUTS DIFFER'}")
    print("  " + "".ljust(11) + "".join(f"{n:>34}" for n, _ in tools))
    for r in ROWS:
        line = "  " + r.ljust(11)
        for n, _ in tools:
            xs = cells[(n, r)]
            line += f"{statistics.median(x[0] for x in xs):>10.1f} ms {statistics.median(x[1] for x in xs):>8.0f} M {statistics.median(x[2] for x in xs):>6.0f} MB"
        print(line)
    print("  cache MB   " + "".join(f"{sizes[n]:>34.1f}" for n, _ in tools))
    sys.stdout.flush()
