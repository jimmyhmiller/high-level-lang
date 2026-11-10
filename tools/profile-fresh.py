#!/usr/bin/env python3
"""A fresh process profiled from its first instruction.

usage: profile-fresh.py [--top=N] [--under=FUNCTION] [--runs=N] -- BINARY ARGS...   (run where the build runs)

`sample NAME -wait` attaches after a short build's first phase is over, so loading never shows.
Here a library put into the process stops it before `main`; `sample` attaches, then it goes on.
Prints thread time by function, inclusive and self, leaving out waiting. With --under, only
the stacks that pass through that function. macOS only.
"""
import collections, os, re, signal, subprocess, sys, tempfile, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHIM_SOURCE = """#include <signal.h>
#include <stdlib.h>
__attribute__((constructor)) static void stop_at_start(void){ if(getenv("HL_STOP_AT_START")) raise(SIGSTOP); }
"""
WAITING = ("__psynch_cvwait", "__ulock_wait", "__pthread_kill")


def shim():
    path = os.path.join(ROOT, "out", "stop-at-start.dylib")
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with tempfile.NamedTemporaryFile("w", suffix=".c", delete=False) as source:
            source.write(SHIM_SOURCE)
        subprocess.run(["cc", "-dynamiclib", "-o", path, source.name], check=True)
        os.unlink(source.name)
    return path


def sampled(command):
    out = tempfile.mktemp(suffix=".sample.txt")
    env = {**os.environ, "HL_STOP_AT_START": "1", "DYLD_INSERT_LIBRARIES": shim()}
    process = subprocess.Popen(command, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.3)
    sampler = subprocess.Popen(["sample", str(process.pid), "30", "1", "-mayDie", "-file", out],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.2)
    process.send_signal(signal.SIGCONT)
    code = process.wait()
    sampler.wait()
    if code != 0:
        raise SystemExit(f"the profiled command failed with status {code}")
    text = open(out, errors="replace").read()
    os.unlink(out)
    return text


def rows_of(text):
    lines = text.split("\n")
    start = next(i for i, line in enumerate(lines) if line.startswith("Call graph:"))
    end = next(i for i, line in enumerate(lines) if line.startswith("Total number in stack"))
    rows = []
    for line in lines[start + 1:end]:
        found = re.match(r"^([ +!:|]*)(\d+) (.+?)  \(in ([^)]+)\)", line)
        if found:
            rows.append((len(found[1]), int(found[2]), found[3]))
    return rows


def add(rows, under, inclusive, own):
    stack, total = [], 0
    for i, (depth, count, name) in enumerate(rows):
        while stack and stack[-1][0] >= depth:
            stack.pop()
        stack.append((depth, name))
        children, j = 0, i + 1
        while j < len(rows) and rows[j][0] > depth:
            if rows[j][0] == depth + 2:
                children += rows[j][1]
            j += 1
        here = count - children
        names = [frame[1] for frame in stack]
        if here <= 0 or any(w in name for w in WAITING) or (under and under not in names):
            continue
        total += here
        own[name] += here
        for frame in set(names[names.index(under):] if under else names):
            inclusive[frame] += here
    return total


def main():
    if "--" not in sys.argv:
        raise SystemExit(__doc__)
    cut = sys.argv.index("--")
    options = dict(o.lstrip("-").split("=", 1) for o in sys.argv[1:cut])
    command = sys.argv[cut + 1:]
    top, under, runs = int(options.get("top", 50)), options.get("under", ""), int(options.get("runs", 1))
    inclusive, own, total = collections.Counter(), collections.Counter(), 0
    for _ in range(runs):
        total += add(rows_of(sampled(command)), under, inclusive, own)
    if total == 0:
        raise SystemExit("no samples: is the function name exact, and the run long enough?")
    print(f"{total / runs:.0f} ms of thread time per run, not waiting" + (f", under {under}" if under else ""))
    print("--- inclusive, ms per run")
    for name, count in inclusive.most_common(top):
        print(f"{count / runs:8.1f} {100 * count / total:5.1f}%  {name[:110]}")
    print("--- self, ms per run")
    for name, count in own.most_common(top // 2):
        print(f"{count / runs:8.1f} {100 * count / total:5.1f}%  {name[:110]}")


if __name__ == "__main__":
    main()
