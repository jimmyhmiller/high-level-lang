#!/usr/bin/env python3
# A watcher's memory over many edits: after the first builds what it holds stays what it holds.
# Copies the tests (apps and node_modules) to out/memory-check, and for each app starts ESB APP
# --watch there twice, each through EDITS edits one after another:
#   statements   a module the bundle uses gets a new first statement each time, so each rebuild
#                makes answers it never made before (new keys, new trees)
#   exports      the entry exports a new name each time (ES module output), so linking's facts
#                change and its database is brought up to date from the last one (`update by`)
#   hot updates  the statements edits with --hmr: each build's development state, kept for the next
# After build WARM and after the last, it reads what the watcher's regions hold (HL_REGION_TRACE:
# regions alive, and their bytes), and its memory over the five builds to each, the middle reading. The regions must hold no more than
# they did after build WARM, give or take 2%; the process's memory (its footprint on macOS, its
# resident set elsewhere) may grow by at most 3% or 4 MB.
#   usage: memory-check.py ESB [APP...] [--edits=N] [--warm=N] [--case=statements|exports|hot-updates]   (APP: zod, rx, datefns, three, …, manyzod: twelve zods)
import json, os, re, shutil, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import guard

args = [a for a in sys.argv[1:] if not a.startswith("--")]
EDITS = next((int(a.split("=")[1]) for a in sys.argv[1:] if a.startswith("--edits=")), 200)
WARM = next((int(a.split("=")[1]) for a in sys.argv[1:] if a.startswith("--warm=")), 20)
CASE = next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--case=")), None)
if CASE not in (None, "statements", "exports", "hot-updates"):
    sys.exit("--case must be statements, exports, or hot-updates")
ESB, = guard.in_tests(args[:1])
APPS = args[1:] or ["zod"]
TESTS = os.getcwd()
WORK = os.path.abspath(os.path.join(TESTS, "..", "out", "memory-check"))
STAGE = WORK + "-stage"
BUILD = re.compile(r"\[watch\] build (\d+):")
REGIONS = re.compile(r"\[regions\] let go \d+ regions, \d+ KB; (\d+) alive, (\d+) KB")
failures = 0

def write(rel, text):
    """A whole file, moved into place, so the watcher never reads half of it."""
    with open(STAGE, "w") as f: f.write(text)
    os.replace(STAGE, os.path.join(WORK, rel))

def resident(pid):
    """The memory the process uses: on macOS its physical footprint (what it has written and not
    given back), including dirty pages retained by malloc; elsewhere its resident set."""
    if sys.platform == "darwin":
        out = subprocess.run(["footprint", "-f", "bytes", str(pid)], capture_output=True, text=True).stdout
        # Whole-MB formatted output is too coarse for a four-MB growth limit. Keep the same
        # limit and sample schedule, but measure bytes. Optional snapshots help diagnose growth.
        profile = os.environ.get("MEMORY_PROFILE")
        if profile:
            os.makedirs(profile, exist_ok=True)
            with open(os.path.join(profile, f"{pid}-{time.time_ns()}.txt"), "w") as file: file.write(out)
        m = re.search(r"Footprint:\s+(\d+)\s+B\b", out)
        if m: return int(m.group(1))
    out = subprocess.run(["ps", "-o", "rss=", "-p", str(pid)], capture_output=True, text=True).stdout.strip()
    return int(out) * 1024 if out else None

def prepare(app):
    if os.path.exists(WORK): shutil.rmtree(WORK)
    os.makedirs(os.path.join(WORK, "out"))
    if app == "manyzod":
        # Twelve copies of zod, each its own package.
        os.makedirs(os.path.join(WORK, "node_modules"))
        for i in range(1, 13):
            shutil.copytree(os.path.join(TESTS, "node_modules", "zod"), os.path.join(WORK, "node_modules", f"zod{i}"), symlinks=True)
        os.makedirs(os.path.join(WORK, "apps"))
        with open(os.path.join(WORK, "apps", "manyzod.js"), "w") as f:
            for i in range(1, 13):
                f.write(f'import {{ z as z{i} }} from "zod{i}"; console.log(z{i}.string().parse("a{i}"));\n')
        entry = "apps/manyzod.js"
    else:
        shutil.copytree(os.path.join(TESTS, "apps"), os.path.join(WORK, "apps"), symlinks=True)
        shutil.copytree(os.path.join(TESTS, "node_modules"), os.path.join(WORK, "node_modules"), symlinks=True)
        entry = next(os.path.join("apps", f) for f in sorted(os.listdir(os.path.join(WORK, "apps"))) if f.split(".")[0] == app)
    p = subprocess.run([ESB, entry, "--sourcemap", "--outfile=out/map.js"], cwd=WORK, capture_output=True, text=True)
    if p.returncode != 0: sys.exit(f"{app}: the build for its source map failed: {p.stderr[-1000:]}")
    sources = [s for s in json.load(open(os.path.join(WORK, "out", "map.js.map")))["sources"] if "node_modules/" in s]
    module = os.path.relpath(os.path.normpath(os.path.join(WORK, "out", sources[len(sources) // 2])), WORK)
    return entry, module

def session(entry, rel, change, flags):
    """A watcher through EDITS edits of `rel` (each `change(original, i)`): what its regions held and
    its memory over the five builds to WARM and over the last five, the middle reading of each: one
    reading may be high (malloc gives back what is freed when it will) or low (the first after a
    run of builds with no pause between them, before what they made has settled), and a leak
    raises them all."""
    original = open(os.path.join(WORK, rel)).read()
    env = dict(os.environ, HL_REGION_TRACE="1")
    p = subprocess.Popen([ESB, entry, "--watch", "--no-cache", "--watch-interval=5", "--outfile=out/out.js"] + flags,
                         cwd=WORK, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env, start_new_session=True)
    builds, held, seen, said = 0, {}, {}, []
    deadline = time.time() + 1800
    try:
        for line in p.stdout:
            said.append(line)
            m = BUILD.search(line)
            if m: builds = int(m.group(1))
            r = REGIONS.search(line)
            if r:
                # The regions as the build's end left them, after what nothing held was let go.
                held[builds] = (int(r.group(1)), int(r.group(2)) * 1024)
                # The process's memory over the five builds that end at WARM and the five last.
                if WARM - 4 <= builds <= WARM or builds > EDITS - 4 or (os.environ.get("MEMORY_PROFILE") and builds % 20 == 0):
                    # Once what the build was doing has settled (it may still be giving memory back).
                    time.sleep(0.3)
                    seen[builds] = resident(p.pid)
                if builds > EDITS: break
                write(rel, change(original, builds))
            if time.time() > deadline: break
    finally:
        os.killpg(p.pid, 9); p.wait()
        write(rel, original)
        profile = os.environ.get("MEMORY_PROFILE")
        if profile:
            os.makedirs(profile, exist_ok=True)
            with open(os.path.join(profile, f"{p.pid}-watch.log"), "w") as file:
                file.write("".join(said))
            with open(os.path.join(profile, f"{p.pid}-measurements.json"), "w") as file:
                json.dump({"held": held, "footprint": seen}, file, indent=2)
    if builds <= EDITS or WARM not in held:
        sys.exit("the watcher stopped early:\n" + "".join(said)[-2000:])
    early = [v for b, v in seen.items() if WARM - 4 <= b <= WARM and v is not None]
    late = [v for b, v in seen.items() if b > EDITS - 4 and v is not None]
    middle = lambda xs: sorted(xs)[len(xs) // 2] if xs else None
    return held[WARM], held[EDITS + 1], middle(early), middle(late)

def check(ok, what):
    global failures
    failures += not ok
    print(f"  {'ok  ' if ok else 'FAIL'} {what}", flush=True)

MB = lambda b: f"{b / 2**20:.1f} MB"
for app in APPS:
    entry, module = prepare(app)
    print(f"== {app}: {EDITS} edits, held after build {WARM} and after build {EDITS + 1}", flush=True)
    sessions = [
        ("statements", module, lambda text, i: f'console.log("memory edit {i}");\n' + text, []),
        ("exports", entry, lambda text, i: text + f"\nexport const memory_edit_{i} = {i};\n", ["--format=esm"]),
        # Hot module replacement: what each build keeps for the next (its development state, copied
        # out of the build's region) and sends must not stay behind either.
        ("hot updates", module, lambda text, i: f'console.log("memory edit {i}");\n' + text, ["--hmr"]),
    ]
    for name, rel, change, flags in sessions:
        if CASE is not None and name.replace(" ", "-") != CASE: continue
        (n0, b0), (n1, b1), r0, r1 = session(entry, rel, change, flags)
        check(b1 <= b0 * 1.02 + 2**20,
              f"{name}: regions {n0} → {n1}, holding {MB(b0)} → {MB(b1)}")
        check(r0 is not None and r1 is not None and r1 - r0 <= max(4 * 2**20, r0 * 0.03),
              f"{name}: memory {MB(r0 or 0)} → {MB(r1 or 0)}")

print("memory holds steady" if failures == 0 else f"{failures} failed")
sys.exit(1 if failures else 0)
