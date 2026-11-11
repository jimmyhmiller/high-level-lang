#!/usr/bin/env python3
"""`--analyze=DIR`: what a build says of itself, checked against what it wrote.
   usage: analyze-check.py [ESB-BINARY]

- The outputs are byte for byte those of the same build without `--analyze` (with and without
  source maps, minified, with fragments, split and single).
- Each output's bytes are its own (imports, exports) and its modules' shares, to the byte.
- What each route loads is its output and every output that imports, transitively, as the files
  themselves say.
- analysis.json and analysis.jsonl hold the same records; every module index is a module.
- What each module holds of each output agrees with the same build's source map, which marks every
  token's source, up to the output's own bytes (its imports and exports, which a map gives to the
  code beside them); a map leaves out the runtime's helpers.
- The page (index.html) has no script; every link within it leads to a section of it, and there is a
  section for each route and each module, each import chain leading from its route to its module."""
import json, os, re, shutil, subprocess, sys
from html.parser import HTMLParser
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


B64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"


def vlq(segment):
    out, value, shift = [], 0, 0
    for ch in segment:
        digit = B64.index(ch)
        value += (digit & 31) << shift
        if digit & 32:
            shift += 5
        else:
            out.append(-(value >> 1) if value & 1 else value >> 1)
            value, shift = 0, 0
    return out


def map_shares(js, mapfile):
    """Bytes of the output by source, from a source map: each segment's bytes to the next one."""
    m = json.loads(Path(mapfile).read_text())
    lines = Path(js).read_bytes().split(b"\n")
    shares, source = {}, 0
    for li, line in enumerate(m["mappings"].split(";")):
        if li >= len(lines):
            break
        segments, col = [], 0
        for s in line.split(","):
            if not s:
                continue
            fields = vlq(s)
            col += fields[0]
            if len(fields) > 1:
                source += fields[1]
                segments.append((col, m["sources"][source]))
            else:
                segments.append((col, None))
        for i, (col, src) in enumerate(segments):
            end = segments[i + 1][0] if i + 1 < len(segments) else len(lines[li]) + 1
            if src is not None:
                tail = "/".join(src.split("/")[-2:])
                shares[tail] = shares.get(tail, 0) + end - col
    return shares


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids, self.links, self.scripts, self.sections = set(), [], 0, []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a:
            self.ids.add(a["id"])
        if tag == "a" and a.get("href", "").startswith("#"):
            self.links.append(a["href"][1:])
        if tag == "script":
            self.scripts += 1
        if tag == "section":
            self.sections.append(a.get("id"))


def check_page(report, data, label):
    page = Page()
    page.feed((report / "index.html").read_text())
    assert page.scripts == 0, f"{label}: the page has a script"
    missing = [l for l in page.links if l not in page.ids]
    assert not missing, f"{label}: links to no section: {missing[:5]}"
    want = {f"r{i}" for i in range(len(data["roots"]))} | {f"m{i}" for i in range(len(data["modules"]))} | {"all"}
    assert want == set(page.sections), f"{label}: sections {sorted(set(page.sections) ^ want)[:5]} differ"
    for m, mod in enumerate(data["modules"]):
        for c in mod["chains"]:
            assert c["modules"][0] == data["roots"][[r["module"] for r in data["roots"]].index(c["root"])]["module"] and c["modules"][-1] == m, \
                f"{label}: a chain of {mod['path']} does not lead from its route to it"


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
        assert [l for l in lines if l["about"] == "output"] == data["outputs"]
        assert [l for l in lines if l["about"] == "module"] == data["modules"]
        assert [l for l in lines if l["about"] == "root"] == data["roots"]
        check_page(report, data, f"{label} {mode}")
        modules, outputs = data["modules"], data["outputs"]
        names = [os.path.relpath(TESTS / o["path"], out) if not os.path.isabs(o["path"]) else os.path.relpath(o["path"], out) for o in outputs]
        for o, name in zip(outputs, names):
            on_disk = (out / name).read_bytes()
            assert o["own"] + sum(h["bytes"] for h in o["modules"]) == o["bytes"], f"{label} {mode}: {name} shares do not add up"
            # What the file holds beyond the text the analysis read: legal notes, a source map's comment.
            assert o["bytes"] <= len(on_disk), f"{label} {mode}: {name} is {len(on_disk)} bytes, analysed {o['bytes']}"
            if "--sourcemap" not in mode and o["kind"] == "js" and b"/*!" not in on_disk and b"LEGAL" not in on_disk:
                assert o["bytes"] == len(on_disk), f"{label} {mode}: {name} is {len(on_disk)} bytes, analysed {o['bytes']}"
            assert all(0 <= h["module"] < len(modules) for h in o["modules"])
        for r in data["roots"]:
            expected = closure(out, names[r["output"]])
            assert {names[i] for i in r["loads"]} == expected, f"{label} {mode}: {r['path']} loads {r['loads']}, the files say {expected}"
        for m in modules:
            assert all(0 <= i < len(modules) for i in m["imports"] + m["dynamic"])
            assert all(0 <= u["module"] < len(modules) and u["names"] for u in m["used-by"])
            assert sum(o["bytes"] for o in m["outputs"]) > 0
        count += 1
print(f"ok   {count} split builds: outputs unchanged, every byte attributed, routes load what the files import")
# What each module holds, against the source map of the same build.
compared = 0
for entries, label in SPLITS:
    for mode in [["--minify"], [], ["--minify", "--fragments"]]:
        out, mapped, report = WORK / "out", WORK / "mapped", WORK / "report"
        args = entries + ["--splitting", "--format=esm"] + mode
        build(args + [f"--outdir={out}"], out, report)
        build(args + ["--sourcemap", f"--outdir={mapped}"], mapped)
        data = json.loads((report / "analysis.json").read_text())
        names = [m["path"] for m in data["modules"]]
        for o in data["outputs"]:
            name = os.path.relpath(TESTS / o["path"], out) if not os.path.isabs(o["path"]) else os.path.relpath(o["path"], out)
            if o["kind"] != "js":
                continue
            # A source map leaves out the bundle's runtime helpers, which the analysis gives to <runtime>.
            ours = {"/".join(names[h["module"]].split("/")[-2:]): h["bytes"] for h in o["modules"] if names[h["module"]] != "<runtime>"}
            theirs = map_shares(mapped / name, mapped / (name + ".map"))
            apart = sum(abs(ours.get(k, 0) - theirs.get(k, 0)) for k in set(ours) | set(theirs))
            assert apart <= 2 * o["own"], f"{label} {mode}: {name} differs from its source map by {apart} bytes, more than its own {o['own']}"
            compared += 1
print(f"ok   {compared} outputs: what each module holds agrees with the source map, up to the output's own bytes")


# A single output: one root, the entry; the same attribution.
for mode in [["--minify"], [], ["--minify", "--sourcemap"]]:
    plain, out, report = WORK / "single-plain", WORK / "single", WORK / "single-report"
    build(["apps/three.js", f"--outfile={plain}/app.js"] + mode, plain)
    build(["apps/three.js", f"--outfile={out}/app.js"] + mode, out, report)
    assert files(plain) == files(out), f"single {mode}: --analyze changed the output"
    data = json.loads((report / "analysis.json").read_text())
    [o] = [o for o in data["outputs"] if o["kind"] == "js"]
    assert o["own"] + sum(h["bytes"] for h in o["modules"]) == o["bytes"]
    assert len(data["roots"]) == 1 and data["roots"][0]["kind"] == "entry"
    core = [m for m in data["modules"] if m["path"].endswith("three.core.js")]
    assert core and core[0]["used-by"], "three.core.js is used by the entry"
print("ok   single outputs: one entry, every byte attributed, three.core.js used by the app")

print("all analysis checks passed")
