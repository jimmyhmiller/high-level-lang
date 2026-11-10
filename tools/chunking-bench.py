#!/usr/bin/env python3
"""Compare chunk-policy and fragment overhead on real imports and generated module shapes."""
import argparse
import json
from pathlib import Path
import re
import shutil
import statistics
import subprocess
import time

ROOT = Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--binary", type=Path, default=ROOT / "out/bin/esb")
parser.add_argument("--baseline", type=Path, default=ROOT / "out/chunking-baseline/esb")
parser.add_argument("--baseline-fragments", action="store_true", help="enable fragments in a baseline that supports them")
parser.add_argument("--runs", type=int, default=7)
parser.add_argument("--iterations", type=int, default=1, help="builds per process; amortizes launch and CPU timer resolution")
args = parser.parse_args()
if args.runs < 1 or args.iterations < 1:
    parser.error("runs and iterations must be positive")
WORK = ROOT / "out/chunking-bench"
WORK.mkdir(parents=True, exist_ok=True)


def put(root, name, text):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


monolith = WORK / "monolith"
monolith.mkdir(exist_ok=True)
put(monolith, "package.json", '{"type":"module"}')
put(monolith, "library.js", "\n".join(f"export function f{i}(x) {{ return x + {i}; }}" for i in range(2000)))
for entry, parity in [("a", 0), ("b", 1)]:
    names = [f"f{i}" for i in range(parity, 2000, 2)]
    put(monolith, entry + ".js", "import {" + ",".join(names) + '} from "./library.js";\nconsole.log('
        + "+".join(f"{name}(1)" for name in names) + ");\n")

many = WORK / "many-modules"
many.mkdir(exist_ok=True)
put(many, "package.json", '{"type":"module"}')
for i in range(300):
    put(many, f"lib/m{i}.js", f"export function a{i}(x) {{ return x + {i}; }}\nexport function b{i}(x) {{ return x - {i}; }}\n")
for entry in ("a", "b"):
    put(many, entry + ".js", "\n".join(f'import {{ {entry}{i} }} from "./lib/m{i}.js";' for i in range(300))
        + "\nconsole.log(" + "+".join(f"{entry}{i}(1)" for i in range(300)) + ");\n")

mixed = WORK / "mixed-initialization"
mixed.mkdir(exist_ok=True)
put(mixed, "package.json", '{"type":"module"}')
put(mixed, "library.js", 'globalThis.__mixed_init = (globalThis.__mixed_init || 0) + 1;\n' + "\n".join(
    f'const config{i} = {{name:"CONFIG_{i}",values:[{i},{i+1}]}}; '
    f'export class C{i} {{ value = {i}; get() {{return this.value;}} }} '
    f'export function f{i}(x) {{return x + config{i}.values[0] + new C{i}().get();}}' for i in range(300)))
for entry, parity in [("a", 0), ("b", 1)]:
    names = [f"f{i}" for i in range(parity, 300, 2)]
    put(mixed, entry + ".js", "import {" + ",".join(names) + '} from "./library.js";\nconsole.log('
        + "+".join(f"{name}(1)" for name in names) + ");\n")

CASES = [
    ("real-libraries", ROOT / "tests", ["apps/split/real1.js", "apps/split/real2.js"]),
    ("many-modules", many, ["a.js", "b.js"]),
    ("monolith", monolith, ["a.js", "b.js"]),
    ("mixed-initialization", mixed, ["a.js", "b.js"]),
]
MODES = [
    ("baseline", args.baseline, ["--fragments"] if args.baseline_fragments else []),
    ("exact-modules", args.binary, []),
    ("exact-fragments", args.binary, ["--fragments"]),
    ("package-modules", args.binary, ["--chunk-policy=package"]),
    ("package-fragments", args.binary, ["--chunk-policy=package", "--fragments"]),
    ("balanced-modules", args.binary, ["--chunk-policy=balanced"]),
    ("balanced-fragments", args.binary, ["--chunk-policy=balanced", "--fragments"]),
]
rows = []


def round_value(value):
    return float(f"{value:.2f}")


def entry_bytes(output, filename):
    pending = [filename]
    seen = set()
    while pending:
        name = pending.pop()
        if name in seen:
            continue
        seen.add(name)
        source = (output / name).read_text()
        for path in re.findall(r'(?:from\s*|import\s*)["\'](\./[^"\']+)["\']', source):
            pending.append(path[2:])
    return sum((output / name).stat().st_size for name in seen)


for case, cwd, entries in CASES:
    commands = []
    for mode, binary, flags in MODES:
        out = WORK / "outputs" / case / mode
        shutil.rmtree(out, ignore_errors=True)
        out.mkdir(parents=True, exist_ok=True)
        command = [str(binary.resolve()), *entries, "--splitting", "--format=esm", f"--outdir={out}", f"--repeat={args.iterations}", *flags]
        commands.append((mode, out, command))
        subprocess.run(command, cwd=cwd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=120)
    measurements = {mode: [] for mode, _, _ in commands}
    cpu = {mode: [] for mode, _, _ in commands}
    peaks = {mode: [] for mode, _, _ in commands}
    instructions = {mode: [] for mode, _, _ in commands}
    # Rotate order each round so CPU warmth and other activity do not favor one mode.
    for round in range(args.runs):
        ordered = commands[round % len(commands):] + commands[:round % len(commands)]
        for mode, out, command in ordered:
            start = time.perf_counter()
            result = subprocess.run(["/usr/bin/time", "-l", *command], cwd=cwd,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, timeout=120)
            elapsed = (time.perf_counter() - start) * 1000
            assert result.returncode == 0, result.stderr
            measurements[mode].append(elapsed / args.iterations)
            times = re.search(r"([\d.]+) real\s+([\d.]+) user\s+([\d.]+) sys", result.stderr)
            if times:
                cpu[mode].append((float(times.group(2)) + float(times.group(3))) * 1000 / args.iterations)
            peak = re.search(r"(\d+)\s+maximum resident set size", result.stderr)
            if peak:
                peaks[mode].append(int(peak.group(1)))
            retired = re.search(r"(\d+)\s+instructions retired", result.stderr)
            if retired:
                instructions[mode].append(int(retired.group(1)) / args.iterations)
    for mode, out, _ in commands:
        files = list(out.glob("*.js"))
        row = {"case": case, "mode": mode, "median_ms": round_value(statistics.median(measurements[mode])),
               "min_ms": round_value(min(measurements[mode])), "max_ms": round_value(max(measurements[mode])),
               "cpu_ms": round_value(statistics.median(cpu[mode])) if cpu[mode] else None,
               "iterations": args.iterations, "runs": args.runs,
               "rss_mb": round_value(statistics.median(peaks[mode]) / 1024**2) if peaks[mode] else None,
               "instructions_m": round_value(statistics.median(instructions[mode]) / 1e6) if instructions[mode] else None,
               "chunks": len(files), "bytes": sum(p.stat().st_size for p in files),
               "entry_bytes": {Path(entry).stem: entry_bytes(out, Path(entry).stem + ".js") for entry in entries}}
        rows.append(row)
        print(json.dumps(row), flush=True)
(WORK / "results.json").write_text(json.dumps(rows, indent=2) + "\n")
