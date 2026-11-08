#!/usr/bin/env python3
# Build times, every way a build is run, for several binaries side by side. For each app, in a
# copy of the tests (apps and node_modules) under out/bench, so nothing it edits is the tests':
#   one-shot                     a fresh process, no cache (as main builds)
#   one-shot --minify            the same, minified
#   --cache, cold                a fresh process, the cache empty
#   --cache, warm, unchanged     a fresh process, the cache as the last run left it, nothing edited
#   --cache, warm, one edit      a fresh process, one module edited since the last run
#   --watch, first, no cache     a watcher's first build, the cache off
#   --watch, first, warm cache   a watcher's first build, from a cache that is up to date
#   --watch, rebuild, one edit   a watcher's build after one module is edited while it runs
# A fresh process is measured from outside: wall time, instructions retired (which the machine's
# load does not change) and peak memory, from /usr/bin/time -l. A watcher's first build is measured
# the same way, up to the moment its first build is done; a rebuild by what the watcher says it
# took, and how many memo answers it computed. Each is the median of the runs, with the least and
# most wall time beside it. A binary with no --watch (main) gets the one-shot rows only.
#   usage: bench.py [--runs=N] [--apps=zod,three,...] [--out=FILE.md] NAME=ESB...
#   apps: any of tests/apps (zod, three, datefns, rx, …), and manyzod: twelve copies of zod
import json, os, re, shutil, signal, statistics, subprocess, sys, time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS = os.path.join(REPO, "tests")
WORK = os.path.join(REPO, "out", "bench")
BUILD = re.compile(r"\[watch\] build (\d+): ([\d.]+) ms, (\d+) memo answers computed")
SAVED = ("[cache] saved in", "[cache] nothing new to save")

runs, apps, out_md, bins = 5, ["zod", "three", "datefns", "manyzod"], None, []
for a in sys.argv[1:]:
    if a.startswith("--runs="): runs = int(a[7:])
    elif a.startswith("--apps="): apps = a[7:].split(",")
    elif a.startswith("--out="): out_md = a[6:]
    elif "=" in a:
        name, path = a.split("=", 1)
        bins.append((name, os.path.abspath(path)))
    else: sys.exit(__doc__ or "usage: bench.py [--runs=N] [--apps=...] [--out=FILE.md] NAME=ESB...")
if not bins: sys.exit("usage: bench.py [--runs=N] [--apps=...] [--out=FILE.md] NAME=ESB...")

def write(root, rel, text):
    """A whole file, moved into place, so a watcher never reads half of it."""
    path = os.path.join(root, rel)
    staged = os.path.join(WORK, ".staged")
    with open(staged, "w") as f: f.write(text)
    os.replace(staged, path)

def prepare(app):
    """A fresh copy to build in: its root, its entry, and a module the bundle uses, to edit."""
    root = os.path.join(WORK, app)
    if os.path.exists(root): shutil.rmtree(root)
    os.makedirs(os.path.join(root, "out"))
    if app == "manyzod":
        os.makedirs(os.path.join(root, "node_modules"))
        for i in range(1, 13):
            shutil.copytree(os.path.join(TESTS, "node_modules", "zod"), os.path.join(root, "node_modules", f"zod{i}"), symlinks=True)
        with open(os.path.join(root, "main.js"), "w") as f:
            for i in range(1, 13):
                f.write(f'import {{ z as z{i} }} from "zod{i}"; console.log(z{i}.string().parse("a{i}"));\n')
        entry = "main.js"
    else:
        shutil.copytree(os.path.join(TESTS, "apps"), os.path.join(root, "apps"), symlinks=True)
        shutil.copytree(os.path.join(TESTS, "node_modules"), os.path.join(root, "node_modules"), symlinks=True)
        entry = next(os.path.join("apps", f) for f in sorted(os.listdir(os.path.join(root, "apps"))) if f.split(".")[0] == app)
    # A module from the middle of the bundle's sources.
    p = subprocess.run([bins[0][1], entry, "--sourcemap", "--outfile=out/map.js"], cwd=root, capture_output=True, text=True)
    if p.returncode != 0: sys.exit(f"{app}: the build for its source map failed: {p.stderr[-1000:]}")
    sources = [s for s in json.load(open(os.path.join(root, "out", "map.js.map")))["sources"] if "node_modules/" in s]
    module = os.path.relpath(os.path.normpath(os.path.join(root, "out", sources[len(sources) // 2])), root)
    return root, entry, module

edits = 0
def edit(root, module, original):
    """The module with one new statement at its top, never the same twice."""
    global edits
    edits += 1
    write(root, module, f'console.log("bench edit {edits}");\n' + original)

def clear_cache(root):
    shutil.rmtree(os.path.join(root, "node_modules", ".cache"), ignore_errors=True)

def usage(err):
    instr = re.search(r"(\d+)\s+instructions retired", err)
    peak = re.search(r"(\d+)\s+peak memory footprint", err)
    return (int(instr.group(1)) if instr else None), (int(peak.group(1)) if peak else None)

def once(esb, root, entry, flags):
    """A fresh process: wall seconds, instructions, peak bytes."""
    t0 = time.perf_counter()
    p = subprocess.run(["/usr/bin/time", "-l", esb, entry, "--outfile=out/out.js"] + flags, cwd=root, capture_output=True, text=True)
    wall = time.perf_counter() - t0
    if p.returncode != 0: raise RuntimeError(f"{esb} {entry} {flags}: {(p.stdout + p.stderr)[-1500:]}")
    instr, peak = usage(p.stderr)
    return {"wall": wall, "instr": instr, "peak": peak}

def kill_child(time_pid):
    for c in subprocess.run(["pgrep", "-P", str(time_pid)], capture_output=True, text=True).stdout.split():
        os.kill(int(c), signal.SIGKILL)

def watch_first(esb, root, entry, flags):
    """A watcher up to its first build, and its save: wall seconds to the build, the build's own ms,
    the answers it computed, and the process's instructions and peak memory up to then."""
    t0 = time.perf_counter()
    p = subprocess.Popen(["/usr/bin/time", "-l", esb, entry, "--watch", "--timing", "--outfile=out/out.js"] + flags, cwd=root,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    wall, ms, answers, said = None, None, None, []
    deadline = time.time() + 300
    for line in p.stdout:
        said.append(line)
        m = BUILD.search(line)
        if m and m.group(1) == "1":
            wall, ms, answers = time.perf_counter() - t0, float(m.group(2)), int(m.group(3))
        if ms is not None and any(s in line for s in SAVED): break
        if ms is not None and "--no-cache" in flags: break
        if time.time() > deadline: break
    kill_child(p.pid)
    err = p.stderr.read(); p.wait()
    if ms is None: raise RuntimeError(f"{esb}: no first build:\n" + "".join(said)[-1500:] + err[-1500:])
    instr, peak = usage(err)
    return {"wall": wall, "ms": ms, "answers": answers, "instr": instr, "peak": peak}

def watch_edits(esb, root, entry, module, original, count):
    """One watcher, `count` edits one after another: each rebuild's own ms and answers."""
    p = subprocess.Popen([esb, entry, "--watch", "--timing", "--outfile=out/out.js"], cwd=root, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, text=True, start_new_session=True)
    results, builds, said = [], 0, []
    deadline = time.time() + 600
    for line in p.stdout:
        said.append(line)
        m = BUILD.search(line)
        if m:
            builds = int(m.group(1))
            if builds > 1: results.append({"ms": float(m.group(2)), "answers": int(m.group(3))})
        if any(s in line for s in SAVED) and builds >= 1:
            if len(results) >= count: break
            edit(root, module, original)
        if time.time() > deadline: break
    os.killpg(p.pid, signal.SIGKILL); p.wait()
    if len(results) < count: raise RuntimeError(f"{esb}: {len(results)} of {count} rebuilds:\n" + "".join(said)[-2000:])
    return results

def watches(esb, root, entry):
    p = subprocess.run([esb, entry, "--no-cache", "--outfile=out/out.js"], cwd=root, capture_output=True, text=True)
    return p.returncode == 0

SCENARIOS = ["one-shot", "one-shot --minify", "--cache, cold", "--cache, warm, unchanged", "--cache, warm, one edit",
             "--watch, first, no cache", "--watch, first, warm cache", "--watch, rebuild, one edit"]

results = {}  # app -> scenario -> binary -> [samples]
os.makedirs(WORK, exist_ok=True)
for app in apps:
    root, entry, module = prepare(app)
    original = open(os.path.join(root, module)).read()
    print(f"== {app}: {entry}, editing {module}", flush=True)
    results[app] = {s: {} for s in SCENARIOS}
    for name, esb in bins:
        r = results[app]
        write(root, module, original)
        clear_cache(root)
        r["one-shot"][name] = [once(esb, root, entry, []) for _ in range(runs)]
        r["one-shot --minify"][name] = [once(esb, root, entry, ["--minify"]) for _ in range(runs)]
        if not watches(esb, root, entry):
            print(f"  {name}: one-shot only", flush=True)
            continue
        cold = []
        for _ in range(runs):
            clear_cache(root)
            cold.append(once(esb, root, entry, ["--cache"]))
        r["--cache, cold"][name] = cold
        r["--cache, warm, unchanged"][name] = [once(esb, root, entry, ["--cache"]) for _ in range(runs)]
        warm_edit = []
        for _ in range(runs):
            edit(root, module, original)
            warm_edit.append(once(esb, root, entry, ["--cache"]))
        r["--cache, warm, one edit"][name] = warm_edit
        r["--watch, first, no cache"][name] = [watch_first(esb, root, entry, ["--no-cache"]) for _ in range(runs)]
        once(esb, root, entry, ["--cache"])  # the cache up to date with the files
        r["--watch, first, warm cache"][name] = [watch_first(esb, root, entry, []) for _ in range(runs)]
        r["--watch, rebuild, one edit"][name] = watch_edits(esb, root, entry, module, original, runs)
        write(root, module, original)
        print(f"  {name}: done", flush=True)

def med(xs): return statistics.median(xs)

def cell(samples):
    if not samples: return "–"
    if "instr" in samples[0] and samples[0].get("instr") is not None and "ms" not in samples[0]:
        walls = [s["wall"] * 1000 for s in samples]
        return (f"{med(walls):.0f} ms ({min(walls):.0f}–{max(walls):.0f}) · {med([s['instr'] for s in samples]) / 1e9:.2f} G · "
                f"{med([s['peak'] for s in samples]) / 2**20:.0f} MB")
    if "wall" in samples[0]:  # a watcher's first build
        walls = [s["wall"] * 1000 for s in samples]
        return (f"{med([s['ms'] for s in samples]):.0f} ms build, {med(walls):.0f} ms to it ({min(walls):.0f}–{max(walls):.0f}) · "
                f"{med([s['instr'] for s in samples]) / 1e9:.2f} G · {med([s['peak'] for s in samples]) / 2**20:.0f} MB · "
                f"{med([s['answers'] for s in samples]):.0f} answers")
    ms = [s["ms"] for s in samples]
    return f"{med(ms):.1f} ms ({min(ms):.1f}–{max(ms):.1f}) · {med([s['answers'] for s in samples]):.0f} answers"

load = subprocess.run(["sysctl", "-n", "vm.loadavg"], capture_output=True, text=True).stdout.strip()
lines = [f"# Build times, {time.strftime('%Y-%m-%d %H:%M')}", "",
         f"Median of {runs} runs; wall time's least–most in brackets. G: instructions retired (load-independent). "
         f"MB: peak memory. Load average at the end: {load}.", ""]
for name, esb in bins: lines.append(f"- **{name}**: `{esb}`")
for app in apps:
    lines += ["", f"## {app}", "", "| | " + " | ".join(n for n, _ in bins) + " |", "|---" * (len(bins) + 1) + "|"]
    for s in SCENARIOS:
        lines.append(f"| {s} | " + " | ".join(cell(results[app][s].get(n, [])) for n, _ in bins) + " |")
text = "\n".join(lines) + "\n"
print(text)
with open(os.path.join(WORK, "results.json"), "w") as f: json.dump(results, f, indent=1)
if out_md:
    with open(out_md, "w") as f: f.write(text)
