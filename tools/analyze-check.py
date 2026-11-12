#!/usr/bin/env python3
"""`--analyze=DIR`: what a build says of itself, checked against what it wrote.
   usage: analyze-check.py [ESB-BINARY]

- The outputs are byte for byte those of the same build without `--analyze` (with and without
  source maps, minified, with fragments, split and single).
- Each output's bytes are its own (imports, exports) and its modules' shares, to the byte.
- What each route loads is its output and every output that imports, transitively, as the files
  themselves say; and its modules' bytes and its files' own add up to it.
- A module holds code, or passes names on to code that reads them through it.
- Every module index in analysis.json is a module.
- What each module holds of each output agrees with the same build's source map, which marks every
  token's source, up to what has no source: the output's own bytes (its imports and exports) and what
  the bundler wrote for a module (its wrapper, its namespace object), which a map gives to the code
  before them; a map leaves out the runtime's helpers.
- The page (index.html, made from the JSON by `esb --view=DIR`, not by the build) has no script; every link within it leads to a section of it and every button
  opens a drawer; there is a section for each route and a drawer for each module, each import chain
  leading from its route to its module;
  each treemap's boxes fill it, overlap nowhere, and are each as large as its bytes."""
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


VOID = {"meta", "br", "img", "input", "link", "hr"}


def size_of(title):
    """A size as a title gives it, and how far that may be from the bytes: B exact, KB to a tenth,
    MB to a hundredth, each cut, not rounded."""
    n, unit = title.rsplit(" · ", 1)[1].split(" ")
    scale = {"B": 1, "KB": 1024, "MB": 1048576}[unit]
    step = {"B": 0, "KB": 0.1, "MB": 0.01}[unit] * scale
    return float(n) * scale + step / 2, step / 2


class Page(HTMLParser):
    """The page's ids, links, scripts and sections; and each treemap box (the map, or a group's
    body) with the boxes in it, each its place (left, top, width, height in percent) and size."""
    def __init__(self):
        super().__init__()
        self.ids, self.links, self.scripts, self.sections = set(), [], 0, []
        self.targets, self.drawers = [], []
        self.stack, self.boxes = [], []
        # Each chain in a drawer: the drawer, the modules its first step names (the routes), and the rest.
        self.chains, self.drawer, self.chain, self.in_roots = [], None, None, False

    def handle_endtag(self, tag):
        if tag == "ol" and self.chain is not None:
            self.chains.append(self.chain)
            self.chain = None
        if tag == "li":
            self.in_roots = False
        if tag not in VOID:
            self.stack.pop()

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        classes = a.get("class", "").split()
        box = None
        if "map" in classes or "gb" in classes:
            box = []
            self.boxes.append(box)
        if ("g" in classes or "t" in classes) and self.stack:
            # The box this one is in: the nearest map or group body around it.
            outer = next(b for b in reversed(self.stack) if b is not None)
            place = dict(kv.split(":") for kv in a["style"].split(";"))
            outer.append(([float(place[k].rstrip("%")) for k in ("left", "top", "width", "height")], size_of(a["title"])))
        if tag not in VOID:
            self.stack.append(box)
        if "id" in a:
            self.ids.add(a["id"])
        if tag == "a" and a.get("href", "").startswith("#"):
            self.links.append(a["href"][1:])
        if tag == "script":
            self.scripts += 1
        if tag == "section":
            self.sections.append(a.get("id"))
        if "popovertarget" in a:
            self.targets.append(a["popovertarget"])
            if self.chain is not None and tag == "button" and "mod" in classes:
                (self.chain[1] if self.in_roots else self.chain[2]).append(a["popovertarget"])
        if "popover" in a:
            self.drawers.append(a.get("id"))
            self.drawer = a.get("id")
        if tag == "ol" and "chain" in classes:
            self.chain = (self.drawer, [], [])
        if tag == "li" and "roots" in classes:
            self.in_roots = True


def check_page(report, data, label):
    # The page is made from the JSON, apart from the build (`esb --view=DIR`).
    made = subprocess.run([str(ESB), f"--view={report}"], capture_output=True, text=True, timeout=120)
    assert made.returncode == 0, f"{label}: --view failed\n{made.stdout}{made.stderr}"
    page = Page()
    page.feed((report / "index.html").read_text())
    assert page.scripts == 0, f"{label}: the page has a script"
    missing = [l for l in page.links if l not in page.ids]
    assert not missing, f"{label}: links to no section: {missing[:5]}"
    assert {f"r{i}" for i in range(len(data["roots"]))} == set(page.sections), f"{label}: a route has no section, or a section no route"
    assert {f"m{i}" for i in range(len(data["modules"]))} == set(page.drawers), f"{label}: a module has no drawer, or a drawer no module"
    opens = [t for t in page.targets if t not in page.drawers]
    assert not opens, f"{label}: buttons open no drawer: {opens[:5]}"
    # A treemap's boxes fill it, overlap nowhere, and each is as large as its bytes, to rounding: places
    # are to a hundredth of a percent, and the sizes in titles to a tenth of a unit.
    for box in page.boxes:
        if not box:
            continue
        total, slack = sum(size for _, (size, _) in box), sum(e for _, (_, e) in box)
        assert abs(sum(w * h for (_, _, w, h), _ in box) - 10000) <= 2 * len(box) + 10, f"{label}: a treemap's boxes do not fill it"
        for i, ((x, y, w, h), (size, e)) in enumerate(box):
            assert x >= 0 and y >= 0 and x + w <= 100.01 and y + h <= 100.01, f"{label}: a treemap box is outside its box"
            # How far the share may be off: the sizes' cuts, and the layout's whole units (0.2% a side).
            off = 100 * (e / total + size * slack / total ** 2) + 0.5
            assert abs(w * h / 100 - 100 * size / total) <= off, f"{label}: a treemap box's area is {w * h / 100:.2f}%, its bytes {100 * size / total:.2f}%"
            for (x2, y2, w2, h2), _ in box[i + 1:]:
                assert max(0, min(x + w, x2 + w2) - max(x, x2)) * max(0, min(y + h, y2 + h2) - max(y, y2)) <= 0.05, f"{label}: treemap boxes overlap"
    routes = {f"m{r['module']}" for r in data["roots"]}
    assert page.chains, f"{label}: the page shows no chains"
    for drawer, roots, rest in page.chains:
        assert roots and set(roots) <= routes, f"{label}: a chain in {drawer} does not start at routes: {roots}"
        assert (rest[-1] if rest else roots[-1]) == drawer, f"{label}: a chain in {drawer} does not lead to its module"


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
            # A module holds code, or holds none and passes names on to code that reads them through it.
            assert sum(o["bytes"] for o in m["outputs"]) > 0 or m["passes"], f"{label} {mode}: {m['path']} holds nothing and passes nothing on"
        for r in data["roots"]:
            # What a route loads is its modules' code and its files' own bytes.
            assert sum(h["bytes"] for h in r["modules"]) + sum(outputs[o]["own"] for o in r["loads"]) == r["bytes"], f"{label} {mode}: {r['path']} does not add up"
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
            # A map gives what has no source (the output's own, and what the bundler wrote for a module) to
            # the code before it.
            sourceless = o["own"] + sum(w["written"] for m in data["modules"] for w in m["outputs"] if data["outputs"][w["output"]] is o)
            assert apart <= 2 * sourceless, f"{label} {mode}: {name} differs from its source map by {apart} bytes, more than twice the {sourceless} with no source"
            compared += 1
print(f"ok   {compared} outputs: what each module holds agrees with the source map, up to what has no source")


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
