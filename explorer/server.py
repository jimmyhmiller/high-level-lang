#!/usr/bin/env python3
"""The tower explorer: a local server for exploring the bundler while working on it.

    python3 explorer/server.py              serves http://127.0.0.1:8770
    python3 explorer/server.py --check      runs every rule example, exits 1 if one fails

It builds real bundles with out/bin/esb and `--record=DIR` (what each rewrite rule did, every
statement and the derivation that keeps it), keeps them under out/explorer/builds, and answers the
page's questions from them: what a build holds and why, every place a rule applied across the
builds made so far, and the examples kept for each rule in explorer/examples, which it runs.
"""
import http.server, json, os, re, shutil, subprocess, sys, threading, time, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import catalog  # noqa: E402

ESB = os.environ.get("EXPLORER_ESB") or os.path.join(ROOT, "out", "bin", "esb")
TESTS = os.path.join(ROOT, "tests")
BUILDS = os.path.join(ROOT, "out", "explorer", "builds")
RUNS = os.path.join(ROOT, "out", "explorer", "example-runs")
EXAMPLES = os.path.join(HERE, "examples")
APP = os.path.join(HERE, "app")
PORT = 8770
# Occurrences of one rule kept per build, at most: enough to read, not the whole build.
PER_RULE = 300


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def rel(path):
    return os.path.relpath(path, ROOT) if os.path.isabs(path) else path


# ---------------------------------------------------------------- the catalog, kept current

_catalog = {"stamp": None, "data": None}
_lock = threading.Lock()


def sources_stamp():
    newest = 0.0
    for d in (os.path.join(ROOT, "src"),):
        for base, _, names in os.walk(d):
            for n in names:
                newest = max(newest, os.path.getmtime(os.path.join(base, n)))
    return newest


def the_catalog():
    with _lock:
        stamp = sources_stamp()
        if _catalog["stamp"] != stamp:
            _catalog["data"] = catalog.build(ROOT)
            _catalog["stamp"] = stamp
        return _catalog["data"]


# ---------------------------------------------------------------- builds

def bundler_stamp():
    """Which bundler made a build: when out/bin/esb was built."""
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(os.path.getmtime(ESB))) if os.path.exists(ESB) else ""


def esb_ready():
    if not os.path.exists(ESB):
        raise RuntimeError("out/bin/esb is missing: build it with tools/build-tools.sh")


def line_of(text, at):
    if at < 0 or at > len(text):
        return None
    return text.count("\n", 0, at) + 1


def run_build(entry, flags, where, cwd):
    """Bundle `entry` with `flags`, recording into `where`. Answers the build's meta."""
    esb_ready()
    if os.path.exists(where):
        shutil.rmtree(where)
    os.makedirs(where)
    out = ["--outdir=" + os.path.join(where, "out")] if "--splitting" in flags else ["--outfile=" + os.path.join(where, "out", "out.js")]
    cmd = [ESB, entry, "--bundle", "--record=" + where] + out + flags
    started = time.time()
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=300)
    took = time.time() - started
    meta = {"entry": entry, "flags": flags, "ms": round(took * 1000), "ok": r.returncode == 0, "bundler": bundler_stamp(),
            "error": (r.stderr or r.stdout)[-4000:] if r.returncode else "", "made": time.strftime("%Y-%m-%d %H:%M:%S")}
    if meta["ok"]:
        meta.update(index_build(where))
    return meta


def index_build(where):
    """What the page asks of a build, worked out once: per module, its statements and the rewrites
    that fired in it; per rule, where it applied."""
    explained = json.loads(read(os.path.join(where, "explain.json")))
    analysis = json.loads(read(os.path.join(where, "analysis.json")))
    modules = {m["id"]: m for m in explained["modules"]}
    by_path = {}
    rules = {}

    def occur(key, item):
        entry = rules.setdefault(key, {"count": 0, "items": []})
        entry["count"] += 1
        if len(entry["items"]) < PER_RULE:
            entry["items"].append(item)

    # Each module's statements by place, to find the statement a rewrite fired in.
    spans = {m["id"]: sorted((st["lo"], st["hi"], st["key"]) for st in m["statements"]) for m in explained["modules"]}

    def statement_at(mid, lo):
        for a, b, key in spans.get(mid, []):
            if a <= lo < b:
                return key
        return None

    rewrites = {}
    path = os.path.join(where, "rewrites.jsonl")
    total_rewrites = 0
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            r = json.loads(line)
            total_rewrites += 1
            mod = modules.get(r["where"])
            mpath = mod["path"] if mod else None
            item = {"rule": r["rule"], "module": mpath, "lo": r["lo"], "hi": r["hi"],
                    "statement": statement_at(r["where"], r["lo"]) if mod and r["lo"] >= 0 else None,
                    "line": line_of(mod["source"], r["lo"]) if mod and r["lo"] >= 0 else None,
                    "before": r["before"], "after": r["after"]}
            occur("%s:%d" % (rel(r["file"]), r["line"]), dict(item, kind="rewrite"))
            if mpath:
                rewrites.setdefault(mpath, []).append(dict(item, file=rel(r["file"]), ruleline=r["line"]))
    rules_file = explained["rules-file"]
    statements_kept = 0
    statements_total = 0
    # Where each statement is, by its key, for the statement a fact is about.
    by_key = {}
    for m in explained["modules"]:
        for st in m["statements"]:
            by_key[st["key"]] = (m, st)
    # A Datalog rule's occurrences are the facts it derived, each once: what it is about, and how many
    # kept statements' derivations rest on it.
    derived = {}
    for m in explained["modules"]:
        for st in m["statements"]:
            statements_total += 1
            if st["kept"]:
                statements_kept += 1
            for step in st["why"]:
                if step["line"] <= 0:
                    continue
                fact = step["relation"] + "(" + ", ".join(step["args"]) + ")"
                d = derived.setdefault((step["line"], fact), {"line": step["line"], "fact": fact, "args": step["args"], "uses": 0})
                d["uses"] += 1
    for (line, fact), d in sorted(derived.items(), key=lambda kv: -kv[1]["uses"]):
        about = next((a[2:] for a in d["args"] if a.startswith("p:")), None)
        item = {"kind": "derived", "fact": fact, "uses": d["uses"], "module": None, "statement": None, "lo": -1, "line": None, "text": ""}
        if about and about in by_key:
            m, st = by_key[about]
            item.update(module=m["path"], statement=about, lo=st["lo"], line=line_of(m["source"], st["lo"]),
                        text=m["source"][st["lo"]:min(st["hi"], st["lo"] + 400)])
        else:
            mod = next((a[2:] for a in d["args"] if a.startswith("m:")), None)
            item.update(module=mod)
        occur("%s:%d" % (rules_file, line), item)
    bytes_of = {}
    for i, am in enumerate(analysis.get("modules", [])):
        bytes_of[am["path"]] = sum(o.get("bytes", 0) for o in am.get("outputs", []))
    summary = []
    for m in explained["modules"]:
        summary.append({"id": m["id"], "path": m["path"], "kind": m["kind"],
                        "statements": len(m["statements"]), "kept": sum(1 for s in m["statements"] if s["kept"]),
                        "rewrites": len(rewrites.get(m["path"], [])),
                        "bytes": bytes_of.get(m["path"], 0), "source": len(m["source"])})
    write(os.path.join(where, "index.json"), json.dumps({"rules": rules, "rewrites": rewrites}))
    out_bytes = sum(o.get("bytes", 0) for o in analysis.get("outputs", []))
    return {"modules": summary, "outputBytes": out_bytes, "rewrites": total_rewrites,
            "statementsKept": statements_kept, "statementsTotal": statements_total,
            "rulesFired": {k: v["count"] for k, v in rules.items()}}


def builds():
    out = []
    if os.path.isdir(BUILDS):
        for d in sorted(os.listdir(BUILDS), reverse=True):
            p = os.path.join(BUILDS, d, "meta.json")
            if os.path.exists(p):
                meta = json.loads(read(p))
                meta["id"] = d
                out.append(meta)
    return out


def new_build(entry, flags):
    if not re.match(r"^[\w./@-]+$", entry) or ".." in entry:
        raise ValueError("an entry is a path under tests/")
    if not os.path.exists(os.path.join(TESTS, entry)):
        raise ValueError("tests/%s does not exist" % entry)
    bid = time.strftime("%Y%m%d-%H%M%S") + "-" + re.sub(r"[^\w]+", "-", os.path.splitext(os.path.basename(entry))[0])
    where = os.path.join(BUILDS, bid)
    meta = run_build(entry, flags, where, TESTS)
    write(os.path.join(where, "meta.json"), json.dumps(meta))
    meta["id"] = bid
    return meta


def build_module(bid, path):
    where = os.path.join(BUILDS, bid)
    explained = json.loads(read(os.path.join(where, "explain.json")))
    index = json.loads(read(os.path.join(where, "index.json")))
    for m in explained["modules"]:
        if m["path"] == path:
            return {"path": path, "kind": m["kind"], "source": m["source"], "statements": m["statements"],
                    "rulesFile": explained["rules-file"], "rewrites": index["rewrites"].get(path, [])}
    raise ValueError("no module %s in build %s" % (path, bid))


def compare(a, b):
    """What changed from build `a` to build `b`: statements kept now and not before, and the
    reverse; each rule's count; each module's bytes."""
    ma = json.loads(read(os.path.join(BUILDS, a, "meta.json")))
    mb = json.loads(read(os.path.join(BUILDS, b, "meta.json")))

    def kept(bid):
        ex = json.loads(read(os.path.join(BUILDS, bid, "explain.json")))
        return {st["key"]: (m["path"], st, m["source"]) for m in ex["modules"] for st in m["statements"] if st["kept"]}
    ka, kb = kept(a), kept(b)

    def said(found, keys):
        out = []
        for k in sorted(keys)[:300]:
            path, st, src = found[k]
            out.append({"key": k, "module": path, "line": line_of(src, st["lo"]), "text": src[st["lo"]:min(st["hi"], st["lo"] + 300)]})
        return out
    rules = sorted({*ma.get("rulesFired", {}), *mb.get("rulesFired", {})})
    rule_deltas = [{"key": k, "before": ma["rulesFired"].get(k, 0), "after": mb["rulesFired"].get(k, 0)} for k in rules
                   if ma["rulesFired"].get(k, 0) != mb["rulesFired"].get(k, 0)]
    bytes_a = {m["path"]: m["bytes"] for m in ma.get("modules", [])}
    bytes_b = {m["path"]: m["bytes"] for m in mb.get("modules", [])}
    module_deltas = [{"path": p, "before": bytes_a.get(p, 0), "after": bytes_b.get(p, 0)} for p in sorted({*bytes_a, *bytes_b})
                     if bytes_a.get(p, 0) != bytes_b.get(p, 0)]
    return {"a": dict(ma, id=a), "b": dict(mb, id=b), "gained": said(kb, kb.keys() - ka.keys()), "lost": said(ka, ka.keys() - kb.keys()),
            "rules": sorted(rule_deltas, key=lambda d: -abs(d["after"] - d["before"])), "modules": module_deltas}


def rule_occurrences(key):
    out = []
    for meta in builds():
        p = os.path.join(BUILDS, meta["id"], "index.json")
        if not meta.get("ok") or not os.path.exists(p):
            continue
        entry = json.loads(read(p))["rules"].get(key)
        if entry:
            out.append({"build": {k: meta[k] for k in ("id", "entry", "flags", "made")}, "count": entry["count"], "items": entry["items"]})
    return out


def rule_counts():
    counts = {}
    for meta in builds():
        for k, n in (meta.get("rulesFired") or {}).items():
            counts[k] = counts.get(k, 0) + n
    return counts


# ---------------------------------------------------------------- examples

def examples():
    out = []
    if os.path.isdir(EXAMPLES):
        for n in sorted(os.listdir(EXAMPLES)):
            if n.endswith(".json"):
                ex = json.loads(read(os.path.join(EXAMPLES, n)))
                ex["id"] = n[:-5]
                last = os.path.join(RUNS, ex["id"], "result.json")
                ex["last"] = json.loads(read(last)) if os.path.exists(last) else None
                out.append(ex)
    return out


def save_example(ex):
    for k in ("rule", "title", "source", "flags"):
        if k not in ex:
            raise ValueError("an example needs " + k)
    rule = ex["rule"]
    base = ex.get("id") or re.sub(r"[^\w]+", "-", "%s-%s-%s" % (os.path.basename(rule["file"]), rule["name"], ex["title"])).strip("-").lower()[:80]
    kept = {"rule": rule, "title": ex["title"], "note": ex.get("note", ""), "source": ex["source"],
            "flags": ex["flags"], "expect": ex.get("expect", {"fires": True})}
    write(os.path.join(EXAMPLES, base + ".json"), json.dumps(kept, indent=2) + "\n")
    return base


def run_example(eid):
    ex = json.loads(read(os.path.join(EXAMPLES, eid + ".json")))
    where = os.path.join(RUNS, eid)
    src_dir = os.path.join(where, "src")
    if os.path.exists(where):
        shutil.rmtree(where)
    write(os.path.join(src_dir, "entry.js"), ex["source"])
    meta = run_build("entry.js", ex["flags"], os.path.join(where, "build"), src_dir)
    key = "%s:%d" % (ex["rule"]["file"], ex["rule"]["line"])
    result = {"ok": meta["ok"], "error": meta.get("error", ""), "fired": 0, "items": [], "output": ""}
    if meta["ok"]:
        index = json.loads(read(os.path.join(where, "build", "index.json")))
        entry = index["rules"].get(key) or {"count": 0, "items": []}
        result["fired"] = entry["count"]
        result["items"] = entry["items"][:20]
        outs = []
        for base, _, names in os.walk(os.path.join(where, "build", "out")):
            for n in sorted(names):
                if n.endswith(".js"):
                    outs.append(read(os.path.join(base, n)))
        result["output"] = "\n".join(outs)
    expect = ex.get("expect", {"fires": True})
    passed = result["ok"] and ((result["fired"] > 0) == bool(expect.get("fires", True)))
    if passed and expect.get("output_contains"):
        passed = expect["output_contains"] in result["output"]
    result["passed"] = passed
    result["ran"] = time.strftime("%Y-%m-%d %H:%M:%S")
    write(os.path.join(where, "result.json"), json.dumps(result))
    return result


# ---------------------------------------------------------------- the server

def repo_file(path):
    full = os.path.abspath(os.path.join(ROOT, path))
    if not full.startswith(ROOT + os.sep) or "/out/" in full or "/node_modules/" in full:
        raise ValueError("not a file of the repository")
    return read(full)


def apps():
    out = []
    apps_dir = os.path.join(TESTS, "apps")
    for n in sorted(os.listdir(apps_dir)):
        if re.search(r"\.(m?js|cjs|ts|tsx|jsx)$", n) and os.path.isfile(os.path.join(apps_dir, n)):
            out.append({"entry": "apps/" + n, "bytes": os.path.getsize(os.path.join(apps_dir, n))})
    return out


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else (body if isinstance(body, str) else json.dumps(body)).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")

    def do_GET(self):
        self.handle_any("GET")

    def do_POST(self):
        self.handle_any("POST")

    def handle_any(self, method):
        url = urllib.parse.urlparse(self.path)
        q = {k: v[0] for k, v in urllib.parse.parse_qs(url.query).items()}
        try:
            if url.path.startswith("/api/"):
                return self.send(200, self.api(method, url.path[5:], q))
            name = "index.html" if url.path in ("/", "") else url.path.lstrip("/")
            full = os.path.abspath(os.path.join(APP, name))
            if not full.startswith(APP) or not os.path.isfile(full):
                return self.send(404, {"error": "no such page"})
            ctype = {"html": "text/html", "js": "text/javascript", "css": "text/css"}.get(full.rsplit(".", 1)[-1], "text/plain")
            return self.send(200, open(full, "rb").read(), ctype)
        except (ValueError, RuntimeError, catalog.CatalogError, FileNotFoundError) as e:
            return self.send(400, {"error": str(e)})

    def api(self, method, path, q):
        if path == "catalog":
            return the_catalog()
        if path == "apps":
            return apps()
        if path == "builds" and method == "GET":
            return builds()
        if path == "builds" and method == "POST":
            b = self.body()
            return new_build(b["entry"], [f for f in b.get("flags", []) if re.match(r"^--[\w-]+(=[\w.:/@-]+)?$", f)])
        if path == "build/module":
            return build_module(q["id"], q["path"])
        if path == "build/output":
            where = os.path.join(BUILDS, q["id"], "out")
            return {"files": [{"path": os.path.relpath(os.path.join(b, n), where), "text": read(os.path.join(b, n))}
                              for b, _, ns in os.walk(where) for n in sorted(ns) if n.endswith(".js")]}
        if path == "rule":
            return rule_occurrences(q["key"])
        if path == "compare":
            return compare(q["a"], q["b"])
        if path == "status":
            return {"bundler": bundler_stamp()}
        if path == "rule-counts":
            return rule_counts()
        if path == "file":
            return {"path": q["path"], "text": repo_file(q["path"])}
        if path == "examples" and method == "GET":
            return examples()
        if path == "examples" and method == "POST":
            return {"id": save_example(self.body())}
        if path == "examples/run":
            b = self.body()
            ids = [e["id"] for e in examples()] if b.get("all") else [b["id"]]
            return {i: run_example(i) for i in ids}
        raise ValueError("no such question: " + path)


def check():
    failed = 0
    for ex in examples():
        r = run_example(ex["id"])
        print(("ok    " if r["passed"] else "FAIL  ") + ex["id"] + ("" if r["passed"] else "  (fired %d; %s)" % (r["fired"], r["error"][:200])))
        failed += 0 if r["passed"] else 1
    print("%d examples, %d failed" % (len(examples()), failed))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    if "--check" in sys.argv:
        check()
    server = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print("the tower explorer: http://127.0.0.1:%d" % PORT)
    server.serve_forever()
