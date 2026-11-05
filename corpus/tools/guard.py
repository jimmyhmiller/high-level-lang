#!/usr/bin/env python3
# Run a command under a memory and time cap, killing its whole process group past either.
# macOS does not enforce `ulimit -v`, so this polls resident memory. Prints the peak it saw.
#   usage: guard.py MEGABYTES SECONDS COMMAND...
# Exit status is the command's, or 137 when the guard killed it.
import os, signal, subprocess, sys, time

def group_rss_mb(pgid):
    out = subprocess.run(["ps", "-axo", "pgid=,rss="], capture_output=True, text=True).stdout
    total = 0
    for line in out.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[0] == str(pgid):
            total += int(parts[1])
    return total / 1024

def run(cmd, limit_mb, limit_s, quiet=False, **kw):
    """Returns (returncode, stdout, stderr, peak_mb, reason). reason is None unless killed."""
    p = subprocess.Popen(cmd, start_new_session=True, text=True,
                         stdout=subprocess.PIPE if quiet else None,
                         stderr=subprocess.PIPE if quiet else None, **kw)
    start, peak, reason, interval = time.time(), 0, None, 0.02
    outs = {"o": "", "e": ""}
    import threading
    def drain(stream, key):
        outs[key] = stream.read()
    threads = []
    if quiet:
        threads = [threading.Thread(target=drain, args=(p.stdout, "o")),
                   threading.Thread(target=drain, args=(p.stderr, "e"))]
        for t in threads: t.start()
    while p.poll() is None:
        peak = max(peak, group_rss_mb(p.pid))
        if peak > limit_mb: reason = f"memory: {peak:.0f} MB over the {limit_mb} MB cap"
        elif time.time() - start > limit_s: reason = f"time: over {limit_s} s"
        if reason:
            os.killpg(p.pid, signal.SIGKILL)
            break
        time.sleep(interval)
        interval = min(interval * 1.5, 0.2)
    p.wait()
    for t in threads: t.join()
    # A process that left children behind must not outlive this.
    try: os.killpg(p.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError): pass
    return (137 if reason else p.returncode), outs["o"], outs["e"], peak, reason

if __name__ == "__main__":
    mb, secs, cmd = int(sys.argv[1]), float(sys.argv[2]), sys.argv[3:]
    code, _, _, peak, reason = run(cmd, mb, secs)
    print(f"[guard] peak {peak:.0f} MB" + (f"; KILLED, {reason}" if reason else f"; exit {code}"), file=sys.stderr)
    sys.exit(code)
