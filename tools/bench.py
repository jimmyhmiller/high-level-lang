#!/usr/bin/env python3
# Build times, every way a build is run, for several bundlers side by side. For each app, in a copy
# of the tests (apps and node_modules) under out/bench, so nothing it edits is the tests'.
#
#   one-shot                     a fresh process, no cache
#   one-shot --minify            the same, minified
#   --cache, cold                a fresh process, its persistent cache empty
#   --cache, warm, unchanged     a fresh process, the cache as the last run left it, nothing edited
#   --cache, warm, one edit      a fresh process, one module edited since the last run
#   watch, first build           a long-running process's first build, no cache
#   watch, first, warm cache     the same, from a cache that is up to date
#   watch, rebuild, one edit     the long-running process's build after one module is edited
#
# Tools, as NAME=KIND:PATH (KIND esb when left out):
#   esb        this bundler. Fresh processes measured from outside (/usr/bin/time -l: wall time,
#              instructions retired, peak memory). --watch: the build's own time and how many memo
#              answers it computed; the first build also from outside, up to when it is done. The
#              watcher looks for edits every 5 ms: after the default 100 ms of sleep the same
#              rebuild takes two to three times as long on a busy machine (a CPU gone cold), which
#              esbuild's rebuild(), called at once, and Turbopack's file events never wait out.
#   esbuild    PATH is the esbuild package's directory. One-shot runs its command line. Watch is
#              its incremental API: a context's first build, then ctx.rebuild() after each edit,
#              timed in the process (tools/bench-esbuild.mjs). It has no persistent cache.
#   turbopack  PATH is turbopack-cli. One-shot is `build --target browser` (--no-minify unless
#              minifying; never source maps). No cache rows: turbopack-cli takes
#              --persistent-caching but writes nothing (`build` leaks its engine rather than shut it
#              down; `dev` stopped by SIGINT leaves the cache empty too), so a second run starts
#              cold. Watch is `dev --eager-compile`: the first build is until every chunk its page
#              names is served; a rebuild, from the edit until the served chunk has it, which
#              includes noticing the edit and serving the chunk.
#   vite       PATH is the vite package's directory (Vite 8: Rolldown bundles, Oxc minifies).
#              One-shot is its build API in a fresh node process, timed from outside. Watch is
#              `build.watch` in one process (tools/bench-vite.mjs): the first build, then from an
#              edit's write until the bundle is written, noticing the edit included. No cache rows.
#
# Each cell is the median of the runs, with the least and most wall time beside it.
#   usage: bench.py [--runs=N] [--apps=zod,three,...] [--out=FILE.md] NAME=[KIND:]PATH...
#   apps: any of tests/apps (zod, three, datefns, rx, …), and manyzod: twelve copies of zod
import gzip, json, os, re, shutil, signal, socket, statistics, subprocess, sys, threading, time, urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS = os.path.join(REPO, "tests")
WORK = os.path.join(REPO, "out", "bench")
BUILD = re.compile(r"\[watch\] build (\d+): ([\d.]+) ms, (\d+) memo answers computed")
SAVED = ("[cache] saved in", "[cache] nothing new to save")
USAGE = "usage: bench.py [--runs=N] [--apps=zod,three,...] [--out=FILE.md] NAME=[KIND:]PATH..."

runs, apps, out_md, tools = 5, ["zod", "three", "datefns", "manyzod"], None, []
for a in sys.argv[1:]:
    if a.startswith("--runs="): runs = int(a[7:])
    elif a.startswith("--apps="): apps = a[7:].split(",")
    elif a.startswith("--out="): out_md = a[6:]
    elif "=" in a:
        name, spec = a.split("=", 1)
        kind, path = spec.split(":", 1) if spec.split(":", 1)[0] in ("esb", "esbuild", "turbopack", "vite") else ("esb", spec)
        # esb:PATH:FLAG,FLAG: flags every one of its runs is given, such as --pipeline=full.
        path, _, flags = path.partition(":")
        tools.append((name, kind, os.path.abspath(path), [f for f in flags.split(",") if f]))
    else: sys.exit(USAGE)
if not any(k == "esb" for _, k, _, _ in tools): sys.exit(USAGE + "\n(at least one esb, which finds the module to edit)")

def write(root, rel, text):
    """A whole file, moved into place, so a watcher never reads half of it."""
    staged = os.path.join(WORK, ".staged")
    with open(staged, "w") as f: f.write(text)
    os.replace(staged, os.path.join(root, rel))

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
    esb = next(p for _, k, p, _ in tools if k == "esb")
    p = subprocess.run([esb, entry, "--sourcemap", "--outfile=out/map.js"], cwd=root, capture_output=True, text=True)
    if p.returncode != 0: sys.exit(f"{app}: the build for its source map failed: {p.stderr[-1000:]}")
    sources = [s for s in json.load(open(os.path.join(root, "out", "map.js.map")))["sources"] if "node_modules/" in s]
    module = os.path.relpath(os.path.normpath(os.path.join(root, "out", sources[len(sources) // 2])), root)
    return root, entry, module

edits = 0
def edit(root, module, original):
    """The module with one new statement at its top, never the same twice: what it says."""
    global edits
    edits += 1
    marker = f"bench edit {edits}"
    write(root, module, f'console.log("{marker}");\n' + original)
    return marker

MAC = sys.platform == "darwin"
PERF_OUT = os.path.join(WORK, ".perf")

PEAK_OUT = os.path.join(WORK, ".peak")

def measuring(cmd):
    """`cmd` run so that its instructions and peak memory can be read when it ends: under
    /usr/bin/time -l on macOS; on Linux under perf stat, and under GNU time inside it for its peak
    memory (perf's own, about 60 MB, is in the peak wait4 gives for perf)."""
    if MAC: return ["/usr/bin/time", "-l"] + cmd
    return ["perf", "stat", "-x,", "-e", "instructions", "-o", PERF_OUT, "--", "/usr/bin/time", "-f", "%M", "-o", PEAK_OUT] + cmd

def usage_of(err):
    """Instructions and peak bytes: from /usr/bin/time -l's report on macOS, from perf stat's and
    GNU time's on Linux."""
    if MAC:
        instr = re.search(r"(\d+)\s+instructions retired", err)
        peak = re.search(r"(\d+)\s+peak memory footprint", err)
        return (int(instr.group(1)) if instr else None), (int(peak.group(1)) if peak else None)
    instr = None
    for line in open(PERF_OUT).read().splitlines():
        f = line.split(",")
        if len(f) > 2 and f[2].startswith("instructions") and f[0].isdigit(): instr = int(f[0])
    kb = [l for l in open(PEAK_OUT).read().splitlines() if l.strip().isdigit()]
    os.remove(PEAK_OUT)
    return instr, (int(kb[-1]) * 1024 if kb else None)


def finished(p, err):
    """Wait for a process started with `measuring`, whose stderr has been read: its exit code,
    instructions, peak bytes."""
    p.wait()
    instr, peak = usage_of(err)
    return p.returncode, instr, peak

def timed(cmd, root):
    """A fresh process, from outside: wall seconds, instructions, peak bytes."""
    t0 = time.perf_counter()
    with open(os.path.join(WORK, ".out"), "w") as o, open(os.path.join(WORK, ".err"), "w") as e:
        p = subprocess.Popen(measuring(cmd), cwd=root, stdout=o, stderr=e)
        p.wait()
    wall = time.perf_counter() - t0
    out, err = open(os.path.join(WORK, ".out")).read(), open(os.path.join(WORK, ".err")).read()
    if p.returncode != 0: raise RuntimeError(f"{cmd}: {(out + err)[-1500:]}")
    instr, peak = usage_of(err)
    return {"wall": wall, "instr": instr, "peak": peak}

def kill_child(pid, depth=1 if MAC else 2):
    """The command a `measuring` wrapper runs, stopped, so the wrappers report and end: the
    wrapper's child on macOS; on Linux its grandchild, with GNU time between perf and it."""
    for c in subprocess.run(["pgrep", "-P", str(pid)], capture_output=True, text=True).stdout.split():
        if depth > 1: kill_child(int(c), depth - 1)
        else: os.kill(int(c), signal.SIGKILL)

# ---------------------------------------------------------------- this bundler

def esb_clear(root): shutil.rmtree(os.path.join(root, "node_modules", ".cache"), ignore_errors=True)

def esb_watch_first(esb, root, entry, flags, extra):
    """A watcher up to its first build (and its save, when it saves): wall seconds to the build,
    the build's own ms, the answers it computed, the process's instructions and peak memory."""
    t0 = time.perf_counter()
    p = subprocess.Popen(measuring([esb, entry, "--watch", "--timing", "--watch-interval=5", "--outfile=out/out.js"] + flags + extra), cwd=root,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    wall, ms, answers, said = None, None, None, []
    deadline = time.time() + 300
    for line in p.stdout:
        said.append(line)
        m = BUILD.search(line)
        if m and m.group(1) == "1":
            wall, ms, answers = time.perf_counter() - t0, float(m.group(2)), int(m.group(3))
        if ms is not None and (any(s in line for s in SAVED) or "--no-cache" in flags): break
        if time.time() > deadline: break
    kill_child(p.pid)
    err = p.stderr.read()
    _, instr, peak = finished(p, err)
    if ms is None: raise RuntimeError(f"{esb}: no first build:\n" + "".join(said)[-1500:] + err[-1500:])
    return {"wall": wall, "ms": ms, "answers": answers, "instr": instr, "peak": peak}

def esb_watch_edits(esb, root, entry, module, original, count, extra):
    """One watcher, `count` edits one after another: each rebuild's own ms and answers."""
    p = subprocess.Popen([esb, entry, "--watch", "--timing", "--watch-interval=5", "--outfile=out/out.js"] + extra, cwd=root, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, text=True, start_new_session=True)
    results, builds, said = [], 0, []
    # A watcher that never builds again after an edit (a strategy that trusts the edited path never
    # sees it) is stopped, not waited on: reading its output blocks, so the deadline is a thread's.
    heard = [time.time()]
    stop = threading.Event()
    def watchdog():
        while not stop.wait(0.5):
            if time.time() - heard[0] > 60:
                said.append("[bench] no build for 60 s after the last edit: stopped\n")
                os.killpg(p.pid, signal.SIGKILL)
                return
    threading.Thread(target=watchdog, daemon=True).start()
    for line in p.stdout:
        said.append(line)
        m = BUILD.search(line)
        if m:
            heard[0] = time.time()
            builds = int(m.group(1))
            if builds > 1: results.append({"ms": float(m.group(2)), "answers": int(m.group(3))})
        if any(s in line for s in SAVED) and builds >= 1:
            if len(results) >= count: break
            edit(root, module, original)
            heard[0] = time.time()
    stop.set()
    try: os.killpg(p.pid, signal.SIGKILL)
    except ProcessLookupError: pass
    p.wait()
    if len(results) < count: raise RuntimeError(f"{esb}: {len(results)} of {count} rebuilds:\n" + "".join(said)[-2000:])
    return results

def bench_esb(r, name, esb, extra, root, entry, module, original):
    once = lambda flags: timed([esb, entry, "--outfile=out/out.js"] + flags + extra, root)
    esb_clear(root)
    r["one-shot"][name] = [once([]) for _ in range(runs)]
    r["one-shot --minify"][name] = [once(["--minify"]) for _ in range(runs)]
    if subprocess.run([esb, entry, "--no-cache", "--outfile=out/out.js"], cwd=root, capture_output=True).returncode != 0:
        return "one-shot only"
    cold = []
    for _ in range(runs):
        esb_clear(root)
        cold.append(once(["--cache"]))
    r["--cache, cold"][name] = cold
    r["--cache, warm, unchanged"][name] = [once(["--cache"]) for _ in range(runs)]
    warm_edit = []
    for _ in range(runs):
        edit(root, module, original)
        warm_edit.append(once(["--cache"]))
    r["--cache, warm, one edit"][name] = warm_edit
    r["watch, first build"][name] = [esb_watch_first(esb, root, entry, ["--no-cache"], extra) for _ in range(runs)]
    once(["--cache"])  # the cache up to date with the files
    r["watch, first, warm cache"][name] = [esb_watch_first(esb, root, entry, [], extra) for _ in range(runs)]
    r["watch, rebuild, one edit"][name] = esb_watch_edits(esb, root, entry, module, original, runs, extra)
    return "done"

# ---------------------------------------------------------------- esbuild

def bench_esbuild(r, name, pkg, extra, root, entry, module, original):
    cli = os.path.join(pkg, "bin", "esbuild")
    once = lambda flags: timed([cli, entry, "--bundle", "--outfile=out/esbuild.js", "--log-level=warning"] + flags, root)
    r["one-shot"][name] = [once([]) for _ in range(runs)]
    r["one-shot --minify"][name] = [once(["--minify"]) for _ in range(runs)]
    p = subprocess.run(["node", os.path.join(REPO, "tools", "bench-esbuild.mjs"), pkg, root, entry, module, str(runs)],
                       capture_output=True, text=True)
    if p.returncode != 0: raise RuntimeError(f"esbuild's context: {p.stderr[-1500:]}")
    got = json.loads(p.stdout)
    # First builds, each in a context of its own.
    firsts = [got["first"]]
    for _ in range(runs - 1):
        q = subprocess.run(["node", os.path.join(REPO, "tools", "bench-esbuild.mjs"), pkg, root, entry, module, "0"],
                           capture_output=True, text=True)
        firsts.append(json.loads(q.stdout)["first"])
    r["watch, first build"][name] = [{"ms": ms} for ms in firsts]
    r["watch, rebuild, one edit"][name] = [{"ms": ms} for ms in got["rebuilds"]]
    return "done"

# ---------------------------------------------------------------- Turbopack

def tp_clear(root):
    shutil.rmtree(os.path.join(root, ".bench-tp-cache"), ignore_errors=True)
    shutil.rmtree(os.path.join(root, "dist"), ignore_errors=True)

def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    return port

def fetch(url):
    req = urllib.request.Request(url, headers={"Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        body = resp.read()
        if resp.headers.get("Content-Encoding") == "gzip": body = gzip.decompress(body)
        return body.decode("utf-8", "replace")

def chunks_of(port):
    return re.findall(r'src="([^"]+)"', fetch(f"http://127.0.0.1:{port}/"))

def tp_dev(tp, root, entry, flags):
    port = free_port()
    p = subprocess.Popen(measuring([tp, "dev", entry, "--eager-compile", "--no-open", "-p", str(port),
                                    "-H", "127.0.0.1"] + flags), cwd=root, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    return p, port

def tp_ready(port, deadline):
    """Once the page and every chunk it names are served: what each chunk says."""
    while time.time() < deadline:
        try:
            texts = {c: fetch(f"http://127.0.0.1:{port}{c}") for c in chunks_of(port)}
            if texts and all(len(t) > 0 for t in texts.values()): return texts
        except Exception:
            time.sleep(0.005)
    raise RuntimeError("turbopack dev never served its chunks")

def tp_dev_first(tp, root, entry, flags):
    t0 = time.perf_counter()
    p, port = tp_dev(tp, root, entry, flags)
    tp_ready(port, time.time() + 300)
    wall = time.perf_counter() - t0
    kill_child(p.pid)
    err = p.stderr.read()
    _, instr, peak = finished(p, err)
    return {"wall": wall, "instr": instr, "peak": peak}

def tp_dev_edits(tp, root, entry, module, original, count):
    p, port = tp_dev(tp, root, entry, [])
    try:
        tp_ready(port, time.time() + 300)
        results, where = [], None
        for _ in range(count):
            marker = edit(root, module, original)
            t0 = time.perf_counter()
            deadline = time.time() + 30
            while True:
                if time.time() > deadline: raise Unserved()
                try:
                    # Once it is known which chunk holds the module, only that one is asked for.
                    if where is not None and marker in fetch(f"http://127.0.0.1:{port}{where}"): break
                    if where is None:
                        hit = [c for c in chunks_of(port) if marker in fetch(f"http://127.0.0.1:{port}{c}")]
                        if hit:
                            where = hit[0]
                            break
                except Exception:
                    pass
            results.append({"ms": (time.perf_counter() - t0) * 1000})
        return results
    finally:
        kill_child(p.pid); p.stderr.read(); finished(p, "")

def bench_turbopack(r, name, tp, extra, root, entry, module, original):
    base = [tp, "build", entry, "--target", "browser", "--no-sourcemap"]
    plain = base + ["--no-minify"]
    def once(cmd):
        shutil.rmtree(os.path.join(root, "dist"), ignore_errors=True)
        return timed(cmd, root)
    tp_clear(root)
    r["one-shot"][name] = [once(plain) for _ in range(runs)]
    r["one-shot --minify"][name] = [once(base) for _ in range(runs)]
    r["watch, first build"][name] = [tp_dev_first(tp, root, entry, []) for _ in range(runs)]
    try:
        r["watch, rebuild, one edit"][name] = tp_dev_edits(tp, root, entry, module, original, runs)
    except Unserved:
        # A package that says it has no side effects lets Turbopack drop a statement made only for
        # its effect: an edit it never serves.
        return "rebuild not measured: dev never served the edit (the package says it has no side effects)"
    return "done"

class Unserved(Exception):
    pass

# ---------------------------------------------------------------- Vite

def bench_vite(r, name, pkg, extra, root, entry, module, original):
    script = os.path.join(REPO, "tools", "bench-vite.mjs")
    once = lambda flags: timed(["node", script, pkg, root, entry, module, "once", "0"] + flags, root)
    r["one-shot"][name] = [once([]) for _ in range(runs)]
    r["one-shot --minify"][name] = [once(["--minify"]) for _ in range(runs)]
    def watch(count):
        p = subprocess.run(["node", script, pkg, root, entry, module, "watch", str(count)], capture_output=True, text=True)
        if p.returncode != 0: raise RuntimeError(f"vite's watch: {p.stderr[-1500:]}")
        return json.loads(p.stdout.strip().splitlines()[-1])
    got = watch(runs)
    # First builds, each in a watcher of its own.
    r["watch, first build"][name] = [{"ms": got["first"]}] + [{"ms": watch(0)["first"]} for _ in range(runs - 1)]
    r["watch, rebuild, one edit"][name] = [{"ms": ms} for ms in got["rebuilds"]]
    return "done" if not got["missing"] else f"done; {got['missing']} of {runs} rebuilds left the edit out (the package says it has no side effects)"

# ---------------------------------------------------------------- the runs and the tables

SCENARIOS = ["one-shot", "one-shot --minify", "--cache, cold", "--cache, warm, unchanged", "--cache, warm, one edit",
             "watch, first build", "watch, first, warm cache", "watch, rebuild, one edit"]
BENCH = {"esb": bench_esb, "esbuild": bench_esbuild, "turbopack": bench_turbopack, "vite": bench_vite}

results = {}  # app -> scenario -> tool -> [samples]
os.makedirs(WORK, exist_ok=True)
for app in apps:
    root, entry, module = prepare(app)
    original = open(os.path.join(root, module)).read()
    print(f"== {app}: {entry}, editing {module}", flush=True)
    results[app] = {s: {} for s in SCENARIOS}
    for name, kind, path, extra in tools:
        write(root, module, original)
        try:
            said = BENCH[kind](results[app], name, path, extra, root, entry, module, original)
        except Exception as e:
            said = f"FAILED: {str(e)[:400]}"
        write(root, module, original)
        print(f"  {name}: {said}", flush=True)

def med(xs): return statistics.median(xs)

def cell(samples):
    if not samples: return "–"
    s0 = samples[0]
    parts = []
    if "wall" in s0:
        walls = [s["wall"] * 1000 for s in samples]
        if "ms" in s0: parts.append(f"{med([s['ms'] for s in samples]):.0f} ms build")
        parts.append(f"{med(walls):.0f} ms ({min(walls):.0f}–{max(walls):.0f})")
    else:
        ms = [s["ms"] for s in samples]
        parts.append(f"{med(ms):.1f} ms ({min(ms):.1f}–{max(ms):.1f})")
    if s0.get("instr") is not None: parts.append(f"{med([s['instr'] for s in samples]) / 1e9:.2f} G")
    if s0.get("peak") is not None: parts.append(f"{med([s['peak'] for s in samples]) / 2**20:.0f} MB")
    if "answers" in s0: parts.append(f"{med([s['answers'] for s in samples]):.0f} answers")
    return " · ".join(parts)

load = (subprocess.run(["sysctl", "-n", "vm.loadavg"], capture_output=True, text=True).stdout.strip() if MAC
        else open("/proc/loadavg").read().split(" ")[:3])
lines = [f"# Build times, {time.strftime('%Y-%m-%d %H:%M')}", "",
         f"Median of {runs} runs; least–most in brackets. G: instructions retired, all threads (load-independent). "
         f"MB: peak memory. Load average at the end: {load}.", ""]
for name, kind, path, extra in tools: lines.append(f"- **{name}** ({kind}): `{path}` {' '.join(extra)}")
for app in apps:
    lines += ["", f"## {app}", "", "| | " + " | ".join(n for n, _, _, _ in tools) + " |", "|---" * (len(tools) + 1) + "|"]
    for s in SCENARIOS:
        lines.append(f"| {s} | " + " | ".join(cell(results[app][s].get(n, [])) for n, _, _, _ in tools) + " |")
text = "\n".join(lines) + "\n"
print(text)
with open(os.path.join(WORK, "results.json"), "w") as f: json.dump(results, f, indent=1)
if out_md:
    with open(out_md, "w") as f: f.write(text)
