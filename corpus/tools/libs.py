# Bundle each real library app with us and with esbuild: sizes, gzip, behaviour, time.
import gzip, os, subprocess, sys, time
S = sys.argv[1]
apps = sys.argv[2:] or "three zod rx datefns preact immer react d3".split()
def run(cmd, timeout=30):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout + r.stderr
    except subprocess.TimeoutExpired as e:
        return 124, ((e.stdout or b"").decode() + (e.stderr or b"").decode())
for a in apps:
    theirs, ours = f"out/esb/{a}.min.js", f"out/ours/{a}.min.js"
    if os.path.exists(ours): os.remove(ours)
    run(["node_modules/.bin/esbuild", f"app/{a}.js", "--bundle", "--minify", "--format=iife", f"--outfile={theirs}", "--log-level=silent"])
    expected = run(["node", theirs], 15)
    t = time.time(); code, out = run([S + "/esb", f"app/{a}.js", "--minify", f"--outfile={ours}"], 60); ms = (time.time() - t) * 1000
    if code != 0 or not os.path.exists(ours):
        msg = [l for l in out.splitlines() if not l[:2].strip().isdigit() and "stack trace" not in l][:2]
        print(f"{a:8} FAILED({code}): {' '.join(msg)[:190]}"); continue
    got = run(["node", ours], 15)
    verdict = "same-output" if got[1] == expected[1] else "OUTPUT DIFFERS: " + got[1][:170].replace("\n", " ")
    o, e = os.path.getsize(ours), os.path.getsize(theirs)
    print(f"{a:8} ours={o:8} esb={e:8} ({(o-e)*100/e:+5.1f}%) gz={len(gzip.compress(open(ours,'rb').read())):7}/{len(gzip.compress(open(theirs,'rb').read())):7} {ms:5.0f}ms {verdict}")
