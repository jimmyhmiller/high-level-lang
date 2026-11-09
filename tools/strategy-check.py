#!/usr/bin/env python3
# The strategies of src/app/build.pipeline, checked. Works in tests/.
#   1. What a run keeps changes nothing it makes: every app, in several modes, the same bytes under
#      each strategy as under the default.
#   2. What a strategy keeps is enough for one build: with HL_MEMO_AUDIT, each function some other
#      strategy keeps but this one does not may not spend more than LIMIT of a build's time on calls
#      whose arguments it was given before (`esb` reports them; see the memo audit in hl.rt). A
#      strategy that tracks is left out: a one-shot build with it keeps everything it names anyway.
#   3. With --base=ESB (main's, say): one-shot builds under the default strategy do at most 5% more
#      work than that binary's, or at most 2 M instructions more (a fixed cost a tiny build shows): instructions retired beyond the process's own launch (--repeat=0),
#      which is the system's and the binary size's, reported beside it.
#   usage: strategy-check.py ESB [--base=ESB] [APP...]
import os, re, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import guard

args = sys.argv[1:]
base = next((a.split("=", 1)[1] for a in args if a.startswith("--base=")), None)
args = [a for a in args if not a.startswith("--base=")]
ESB, = guard.in_tests(args[:1])
if base: base = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tests", base)) if not os.path.isabs(base) else base
APPS = args[1:] or ["zod", "rx", "datefns", "three", "cjs", "features"]
MODES = {"plain": [], "min": ["--minify"], "full": ["--pipeline=full"], "map": ["--sourcemap"]}
LIMIT = 0.03
OUT = "../out/strategy-check"
os.makedirs(OUT, exist_ok=True)
failures = 0

def strategies():
    """Each strategy the pipeline declares, and whether it tracks."""
    text = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src", "app", "build.pipeline")).read()
    found = []
    for m in re.finditer(r"^strategy\s+(\S+)(.*?)^end", text, re.S | re.M):
        found.append((m.group(1), re.search(r"^\s+tracks\s*$", m.group(2), re.M) is not None))
    return found

def build(app, flags, out, env=None):
    t0 = time.perf_counter()
    p = subprocess.run([ESB, f"apps/{app}.js", f"--outfile={out}"] + flags, capture_output=True, text=True, env=env, timeout=300)
    wall = time.perf_counter() - t0
    if p.returncode != 0: sys.exit(f"{app} {flags}: {(p.stdout + p.stderr)[-1500:]}")
    return wall, p.stderr

def check(ok, what):
    global failures
    failures += not ok
    print(f"  {'ok  ' if ok else 'FAIL'} {what}")

STRATEGIES = strategies()
print("== the same bytes under every strategy: " + ", ".join(n for n, _ in STRATEGIES))
for app in APPS:
    for mode, flags in MODES.items():
        default = f"{OUT}/{app}.{mode}.js"
        build(app, flags, default)
        want = open(default, "rb").read() + (open(default + ".map", "rb").read() if os.path.exists(default + ".map") else b"")
        same = []
        for name, _ in STRATEGIES:
            out = f"{OUT}/{app}.{mode}.{name}.js"
            build(app, flags + [f"--strategy={name}"], out)
            got = open(out, "rb").read() + (open(out + ".map", "rb").read() if os.path.exists(out + ".map") else b"")
            # A map names its own file: compare it with the file's name taken out.
            same.append(got.replace(os.path.basename(out).encode(), b"X") == want.replace(os.path.basename(default).encode(), b"X"))
        check(all(same), f"{app} {mode}")

print(f"== what each strategy keeps is enough for one build (repeats at most {LIMIT:.0%} of its time)")
AUDIT = re.compile(r"\[audit\] (\S+): (\d+), (\d+), ([\d.]+), ([\d.]+)")
for name, tracks in STRATEGIES:
    if tracks: continue
    # Serial, and on many threads, where stages make what the ones after them read.
    for plan in [[], ["--pipeline=full"]]:
        for app in APPS:
            wall, err = build(app, [f"--strategy={name}"] + plan, f"{OUT}/{app}.audit.js", env=dict(os.environ, HL_MEMO_AUDIT="1"))
            worst = [(float(m.group(4)), m.group(1), int(m.group(3))) for m in AUDIT.finditer(err)]
            over = [w for w in worst if w[0] / 1000 > LIMIT * wall]
            check(not over, f"{name}, {app} {' '.join(plan) or 'serial'}: " + ("nothing asked twice that costs" if not over else
                  "; ".join(f"{f} asked {n} times again, {ms:.1f} ms of {wall * 1000:.0f}" for ms, f, n in over[:3])))

if base:
    # A build's work is what it retires beyond the same process doing nothing (--repeat=0): how much
    # launching a binary costs depends on the system and the binary's size, not on what it builds.
    print("== one-shot work under the default strategy, against " + base)
    MAC = sys.platform == "darwin"
    def instructions(binary, app, extra):
        cmd = [binary, f"apps/{app}.js", f"--outfile={OUT}/{app}.instr.js"] + extra
        if MAC:
            p = subprocess.run(["/usr/bin/time", "-l"] + cmd, capture_output=True, text=True, timeout=300)
            return int(re.search(r"(\d+)\s+instructions retired", p.stderr).group(1))
        p = subprocess.run(["perf", "stat", "-x,", "-e", "instructions", "--"] + cmd, capture_output=True, text=True, timeout=300)
        return int(next(l for l in p.stderr.splitlines() if "instructions" in l).split(",")[0])
    def work(binary, app):
        launch = min(instructions(binary, app, ["--repeat=0"]) for _ in range(3))
        return min(instructions(binary, app, []) for _ in range(3)) - launch, launch
    for app in APPS:
        ours, ours_launch = work(ESB, app)
        theirs, theirs_launch = work(base, app)
        # A fixed cost under a millisecond (2 M instructions) fails no build that small.
        check(ours <= theirs * 1.05 or ours - theirs <= 2000000,
              f"{app}: {ours / 1e9:.3f} G against {theirs / 1e9:.3f} G ({ours / theirs - 1:+.1%}, {(ours - theirs) / 1e6:+.1f} M); "
              f"launch {ours_launch / 1e6:.1f} M against {theirs_launch / 1e6:.1f} M")

print("all strategies check out" if failures == 0 else f"{failures} failed")
sys.exit(1 if failures else 0)
