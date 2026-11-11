#!/usr/bin/env python3
"""`--analyze=DIR`: what a build says of itself, checked against what it wrote.
   usage: analyze-check.py [ESB-BINARY]

- The outputs are byte for byte those of the same build without `--analyze` (with and without
  source maps, minified, with fragments, split and single).
- Each output's bytes are its own (imports, exports) and its modules' shares, to the byte.
- What each route loads is its output and every output that imports, transitively, as the files
  themselves say.
- analysis.json and analysis.jsonl hold the same records; every module index is a module."""
import json, os, re, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ESB = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / "out/bin/esb"
WORK = ROOT / "out/analyze-check"
TESTS = ROOT / "tests"
shutil.rmtree(WORK, ignore_errors=True)
WORK.mkdir(parents=True)

STATIC = re.compile(r'(?:^|[;}\n])\s*(?:import|export)\s*(?:[\w$*{},\s]*?\bfrom\s*)?"(\.\.?/[^"]+)"')


def build(args, out, analyze=None):
    shutil.rmtree(out, ignore_errors=True)
    cmd = [str(ESB), *args] + ([f"--analyze={analyze}"] if analyze else [])
    result = subprocess.run(cmd, cwd=TESTS, capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, " ".join(cmd) + "\n" + result.stdout + result.stderr


def files(d):
    return {str(p.relative_to(d)): p.read_bytes() for p in sorted(Path(d).rglob("*")) if p.is_file()}


def closure(outdir, start):
    seen, todo = set(), [start]
    while todo:
        f = todo.pop()
        if f in seen:
            continue
        seen.add(f)
        text = (outdir / f).read_text()
        todo += [os.path.normpath(os.path.join(os.path.dirname(f), m)) for m in STATIC.findall(text)]
    return seen


SPLITS = [
    (["apps/split/real1.js", "apps/split/real2.js"], "lodash-es, rxjs and import()"),
    (["apps/split/a.js", "apps/split/sub/nested.js"], "nested directories and CommonJS"),
    (["apps/split/ts-entry.ts"], "TypeScript and import()"),
]
MODES = [["--minify"], [], ["--minify", "--fragments"], ["--minify", "--sourcemap"], ["--pretty"]]

count = 0
for entries, label in SPLITS:
    for mode in MODES:
        plain, out, report = WORK / "plain", WORK / "out", WORK / "report"
        args = entries + ["--splitting", "--format=esm"] + mode
        build(args + [f"--outdir={plain}"], plain)
        build(args + [f"--outdir={out}"], out, report)
        assert files(plain) == files(out), f"{label} {mode}: --analyze changed the outputs"
        data = json.loads((report / "analysis.json").read_text())
        lines = [json.loads(l) for l in (report / "analysis.jsonl").read_text().splitlines() if l]
        assert [l for l in lines if l["type"] == "output"] == [dict(type="output", **o) for o in data["outputs"]]
        assert [l for l in lines if l["type"] == "module"] == [dict(type="module", **m) for m in data["modules"]]
        assert [l for l in lines if l["type"] == "root"] == [dict(type="root", **r) for r in data["roots"]]
        modules, outputs = data["modules"], data["outputs"]
        names = [os.path.relpath(TESTS / o["path"], out) if not os.path.isabs(o["path"]) else os.path.relpath(o["path"], out) for o in outputs]
        for o, name in zip(outputs, names):
            on_disk = (out / name).read_bytes()
            assert o["own"] + sum(b for _, b in o["modules"]) == o["bytes"], f"{label} {mode}: {name} shares do not add up"
            # What the file holds beyond the text the analysis read: legal notes, a source map's comment.
            assert o["bytes"] <= len(on_disk), f"{label} {mode}: {name} is {len(on_disk)} bytes, analysed {o['bytes']}"
            if "--sourcemap" not in mode and o["kind"] == "js" and b"/*!" not in on_disk and b"LEGAL" not in on_disk:
                assert o["bytes"] == len(on_disk), f"{label} {mode}: {name} is {len(on_disk)} bytes, analysed {o['bytes']}"
            assert all(0 <= m < len(modules) for m, _ in o["modules"])
        for r in data["roots"]:
            expected = closure(out, names[r["output"]])
            assert {names[i] for i in r["loads"]} == expected, f"{label} {mode}: {r['path']} loads {r['loads']}, the files say {expected}"
        for m in modules:
            assert all(0 <= i < len(modules) for i in m["imports"] + m["dynamic"])
            assert all(0 <= u["module"] < len(modules) and u["names"] for u in m["usedBy"])
            assert sum(o["bytes"] for o in m["outputs"]) > 0
        count += 1
print(f"ok   {count} split builds: outputs unchanged, every byte attributed, routes load what the files import")

# A single output: one root, the entry; the same attribution.
for mode in [["--minify"], [], ["--minify", "--sourcemap"]]:
    plain, out, report = WORK / "single-plain", WORK / "single", WORK / "single-report"
    build(["apps/three.js", f"--outfile={plain}/app.js"] + mode, plain)
    build(["apps/three.js", f"--outfile={out}/app.js"] + mode, out, report)
    assert files(plain) == files(out), f"single {mode}: --analyze changed the output"
    data = json.loads((report / "analysis.json").read_text())
    [o] = [o for o in data["outputs"] if o["kind"] == "js"]
    assert o["own"] + sum(b for _, b in o["modules"]) == o["bytes"]
    assert len(data["roots"]) == 1 and data["roots"][0]["kind"] == "entry"
    core = [m for m in data["modules"] if m["path"].endswith("three.core.js")]
    assert core and core[0]["usedBy"], "three.core.js is used by the entry"
print("ok   single outputs: one entry, every byte attributed, three.core.js used by the app")

print("all analysis checks passed")
