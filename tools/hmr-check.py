#!/usr/bin/env python3
# Hot module replacement, end to end. Copies tests/apps/hmr to out/hmr-check, runs ESB --hmr
# --serve=0 there, and runs the bundle in Node (oracles/hmr-client.cjs), connected to the server's
# event stream. Then edits, checking what the running app does after each:
#   a module that accepts its own updates: replaced in place, its dispose data passed on, and the
#     entry's state kept;
#   a module only it imports: it runs again with the new one;
#   the entry, and a CommonJS module only the entry imports: nothing accepts them, so a reload;
#   a write that changes nothing: no rebuild.
# After each rebuild the bundle written must be what a fresh process builds from the same files.
#   usage: hmr-check.py ESB
import os, queue, re, shutil, subprocess, sys, threading, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import guard

ESB, = guard.in_tests(sys.argv[1:2])
TESTS = os.getcwd()
WORK = os.path.abspath(os.path.join(TESTS, "..", "out", "hmr-check"))
CLIENT = os.path.join(TESTS, "oracles", "hmr-client.cjs")
if os.path.exists(WORK):
    shutil.rmtree(WORK)
shutil.copytree(os.path.join(TESTS, "apps", "hmr"), os.path.join(WORK, "apps", "hmr"))
# The output's directory is there already: making it would change a listing the first build read,
# which rebuilds once, sending nothing.
os.makedirs(os.path.join(WORK, "out"))

def lines_of(proc):
    q = queue.Queue()
    threading.Thread(target=lambda: [q.put(l.rstrip("\n")) for l in proc.stdout], daemon=True).start()
    return q

def wait_for(q, pattern, seconds, seen=None):
    end = time.time() + seconds
    while time.time() < end:
        try:
            line = q.get(timeout=max(0.01, end - time.time()))
        except queue.Empty:
            break
        if seen is not None:
            seen.append(line)
        m = re.search(pattern, line)
        if m:
            return m
    return None

def edit(rel, old, new):
    path = os.path.join(WORK, rel)
    text = open(path).read()
    assert old in text, f"{rel} has no {old!r}"
    open(path, "w").write(text.replace(old, new))

def fresh_matches():
    """The bundle the watcher wrote, against a fresh process's first development build."""
    p = subprocess.Popen([ESB, "apps/hmr/main.js", "--hmr", "--no-cache", "--outfile=out/fresh.js"], cwd=WORK,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, start_new_session=True)
    ok = wait_for(lines_of(p), r"\[watch\] build 1:", 30)
    os.killpg(p.pid, 9)
    p.wait()
    # The served bundle connects to its server's port, which the fresh one has none of.
    served = [l for l in open(os.path.join(WORK, "out/out.js")).read().split("\n") if not l.startswith("__hmr.connect(")]
    return ok and served == open(os.path.join(WORK, "out/fresh.js")).read().split("\n")

esb = subprocess.Popen([ESB, "apps/hmr/main.js", "--hmr", "--serve=0", "--outfile=out/out.js"], cwd=WORK,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, start_new_session=True)
built = lines_of(esb)
log = []
if not wait_for(built, r"\[watch\] build 1:", 30, log):
    sys.exit("no first build:\n" + "\n".join(log))
client = subprocess.Popen(["node", CLIENT, "out/out.js"], cwd=WORK, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, text=True, start_new_session=True)
said = lines_of(client)
failures = 0

def check(ok, label):
    global failures
    failures += not ok
    print(("  ok   " if ok else "  FAIL ") + label)

def ask(expr):
    client.stdin.write(expr + "\n")
    client.stdin.flush()
    m = wait_for(said, r"^(=>|!!) (.*)", 5)
    return m.group(2) if m else None

def step(name, act, client_says, answer):
    """Make an edit, wait for the rebuild and what is sent, then what the client says and answers."""
    seen, heard = [], []
    act()
    m = wait_for(built, r"\[hmr\] (update|reload|no module changed)", 10, seen)
    timing = next((l for l in seen if "[watch] build" in l), "")
    if not m:
        check(False, f"{name}: no rebuild\n" + "\n".join(seen))
        return
    for pattern in client_says:
        if not wait_for(said, pattern, 5, heard):
            check(False, f"{name}: the client never said /{pattern}/; it said {heard}")
            return
    got = ask("click()") if answer else None
    ms = re.search(r"build \d+: ([\d.]+) ms", timing)
    fresh = fresh_matches()
    check((answer is None or got == answer) and fresh,
          f"{name}: {m.group(0)} in {ms.group(1) if ms else '?'} ms" + (f", then click() => {got}" if answer else "")
          + ("" if answer is None or got == answer else f" (wanted {answer})")
          + ("" if fresh else ", but the bundle differs from a fresh build"))

check(wait_for(said, r"main ran view v1 12 config", 5) is not None, "the bundle runs, connected to the server")
check(ask("click()") == "hello clicked 1", "it has state: click() => hello clicked 1")
step("edit the accepting module", lambda: edit("apps/hmr/view.js", '"view v1"', '"view v2"'),
     [r"view replaced, was view v1", r"\[hmr\] updated apps/hmr/view.js"], "hello clicked 2")
step("edit a module it imports", lambda: edit("apps/hmr/text.js", '"hello"', '"hi"'),
     [r"view replaced, was view v2", r"\[hmr\] updated apps/hmr/view.js"], "hi clicked 3")
step("edit the entry", lambda: edit("apps/hmr/main.js", '"main ran"', '"main ran again"'),
     [r"RELOAD apps/hmr/main.js changed"], None)
step("edit CommonJS only the entry imports", lambda: edit("apps/hmr/config.cjs", '"config"', '"config2"'),
     [r"RELOAD apps/hmr/main.js changed"], None)
seen = []
same = open(os.path.join(WORK, "apps/hmr/view.js")).read()
open(os.path.join(WORK, "apps/hmr/view.js"), "w").write(same)
check(wait_for(built, r"\[watch\] build", 1.5, seen) is None, "a write that changes nothing: no rebuild")
for p in (esb, client):
    os.killpg(p.pid, 9)
    p.wait()

# The development format runs as the bundle does: every app, built both ways, says the same in Node.
print("== the development format runs as the bundle does")
APPS = {"named": [], "all": [], "cjs": [], "features": [], "three": [], "zod": [], "rx": [], "datefns": [], "preact": [],
        "immer": [], "react": [], "d3": [], "lib": [], "excjs": [], "nodey": ["--platform=node"]}
OUT = os.path.join(WORK, "apps-out")
os.makedirs(OUT)
def run_node(path):
    try:
        p = subprocess.run(["node", path], cwd=OUT, capture_output=True, text=True, timeout=20)
        return p.stdout + p.stderr
    except subprocess.TimeoutExpired as e:
        return (e.stdout or b"").decode() + "<still running after 20 s>"
for app, flags in APPS.items():
    entry = next(os.path.join("apps", f) for f in sorted(os.listdir(os.path.join(TESTS, "apps"))) if f.split(".")[0] == app)
    subprocess.run([ESB, entry, f"--outfile={OUT}/{app}.cjs"] + flags, capture_output=True, timeout=120)
    p = subprocess.Popen([ESB, entry, "--hmr", "--no-cache", f"--outfile={OUT}/{app}.dev.cjs"] + flags, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, text=True, start_new_session=True)
    m = wait_for(lines_of(p), r"\[watch\] build 1: ([\d.]+) ms", 60)
    os.killpg(p.pid, 9)
    p.wait()
    bundled, dev = run_node(f"{app}.cjs"), run_node(f"{app}.dev.cjs")
    check(m is not None and bundled == dev,
          f"{app}: {len(dev.splitlines())} lines the same" if bundled == dev else
          f"{app}: bundle says {bundled[:200]!r}, development build says {dev[:200]!r}")
print("all checks passed" if failures == 0 else f"{failures} failed")
sys.exit(1 if failures else 0)
