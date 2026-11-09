#!/usr/bin/env python3
# What a strategy leaves out that a build asks the same of again and again. Builds the tools with
# HL_AUDIT_ALL (every plain function that could be kept counts its calls by their arguments; see
# the memo audit in hl.rt) into out/audit, then builds each app under each strategy that does not
# track, serial and on many threads, with HL_MEMO_AUDIT, and reports every function whose calls
# with arguments seen before took more than LIMIT of the build, each of them on average more than
# EACH microseconds (a kept answer costs about one to look up, so a cheaper call is better made
# again): one the strategy should keep.
#   usage: keep-audit.py [--no-build] [--limit=0.02] [--each=5] [APP...]      (works from anywhere)
import os, re, subprocess, sys, time
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS = os.path.join(REPO, "tests")
OUT = os.path.join(REPO, "out", "audit")
args = sys.argv[1:]
build = "--no-build" not in args
limit = float(next((a.split("=", 1)[1] for a in args if a.startswith("--limit=")), "0.02"))
each = float(next((a.split("=", 1)[1] for a in args if a.startswith("--each=")), "5"))
apps = [a for a in args if not a.startswith("--")] or ["zod", "rx", "datefns", "three", "cjs", "features"]
if build:
    p = subprocess.run(["python3", "tools/guard.py", "12000", "1500", "tools/build-tools.sh"], cwd=REPO,
                       env=dict(os.environ, HL_AUDIT_ALL="1", HL_TOOLS_OUT=OUT), capture_output=True, text=True)
    if p.returncode != 0 or not os.path.exists(os.path.join(OUT, "esb")):
        sys.exit("the audit build failed:\n" + (p.stdout + p.stderr)[-2000:])
esb = os.path.join(OUT, "esb")
text = open(os.path.join(REPO, "src", "app", "build.pipeline")).read()
strategies = [m.group(1) for m in re.finditer(r"^strategy\s+(\S+)(.*?)^end", text, re.S | re.M)
              if not re.search(r"^\s+tracks\s*$", m.group(2), re.M)]
AUDIT = re.compile(r"\[audit\] (\S+): (\d+), (\d+), ([\d.]+), ([\d.]+)")
found = 0
for strategy in strategies:
    for plan in [[], ["--pipeline=full"]]:
        for app in apps:
            # How long the build takes, from the program as it is built for use: the audited one's
            # own time is longer.
            walls = []
            for _ in range(3):
                t0 = time.perf_counter()
                subprocess.run([os.path.join(REPO, "out", "bin", "esb"), f"apps/{app}.js", "--outfile=../out/audit/out.js",
                                f"--strategy={strategy}"] + plan, cwd=TESTS, capture_output=True, timeout=600)
                walls.append((time.perf_counter() - t0) * 1000)
            wall = min(walls)
            p = subprocess.run([esb, f"apps/{app}.js", "--outfile=../out/audit/out.js", f"--strategy={strategy}"] + plan,
                               cwd=TESTS, capture_output=True, text=True, env=dict(os.environ, HL_MEMO_AUDIT="1"), timeout=600)
            if p.returncode != 0: sys.exit(f"{app}: {p.stderr[-1500:]}")
            rows = [(float(m.group(4)), m.group(1), int(m.group(2)), int(m.group(3))) for m in AUDIT.finditer(p.stderr)]
            over = [r for r in rows if r[0] > limit * wall and r[3] > 0 and r[0] * 1000 / r[3] >= each]
            for ms, f, calls, again in over:
                found += 1
                print(f"{strategy} {app} {' '.join(plan) or 'serial'}: {f} asked {again} of {calls} times again, "
                      f"{ms:.1f} ms of {wall:.0f} ({ms * 1000 / again:.1f} us each)")
print("nothing a strategy leaves out is asked again at a cost" if found == 0 else f"{found} to look at")
sys.exit(1 if found else 0)
