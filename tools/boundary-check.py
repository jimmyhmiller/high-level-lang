#!/usr/bin/env python3
"""Check paired client/server builds, references, environment resolution and boundary errors."""
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
SPEC = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / "out/bin/spec"
WORK = ROOT / "out/boundary-check"
if WORK.exists():
    shutil.rmtree(WORK)
WORK.mkdir(parents=True)


def write(root, name, text):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def fixture(name, files):
    root = WORK / name
    root.mkdir()
    for path, text in files.items():
        write(root, path, text)
    write(root, "build.bundler", '''bundler
target app
  entry "src/server.js"
  outfile "dist/server.cjs"
  client-outfile "dist/client.mjs"
  client-manifest "dist/manifest.json"
end
''')
    return root


def build(root, error=None):
    result = subprocess.run([str(SPEC), "build.bundler"], cwd=root, capture_output=True, text=True, timeout=120)
    if error is None:
        assert result.returncode == 0, result.stdout + result.stderr
    else:
        assert result.returncode != 0 and error in result.stdout + result.stderr, result.stdout + result.stderr
        assert not (root / "dist/server.cjs").exists(), "invalid build wrote server output"
        assert not (root / "dist/client.mjs").exists(), "invalid build wrote client output"
    return result.stdout + result.stderr


def node(root, code):
    result = subprocess.run(["node", "--input-type=module", "-e", code], cwd=root,
                            capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout.strip()


BASE = {
    "src/server.js": '''import Widget, { named } from "./client.js";
import { secret } from "./database.js";
import { shared } from "./shared.js";
export function page() { return { widget: Widget, named, value: secret(), shared }; }
export function forbiddenCall() { return Widget(); }
''',
    "src/client.js": '''"use client";
import "client-only";
import { shared } from "./shared.js";
if (typeof window === "undefined") throw new Error("CLIENT_BODY_EXECUTED_ON_SERVER");
export default function Widget(n) { return shared + n; }
export const named = 42;
''',
    "src/database.js": '''import "server-only";
export function secret() { return "SERVER_SECRET_SENTINEL"; }
''',
    "src/shared.js": 'export const shared = "SHARED_IN_BOTH_ENVIRONMENTS";\n',
}

root = fixture("basic", BASE)
build(root)
manifest = json.loads((root / "dist/manifest.json").read_text())
assert manifest["modules"]["src/client.js"]["exports"] == ["default", "named"], manifest
assert manifest["client"] == "dist/client.mjs" and manifest["server"] == "dist/server.cjs"
model = json.loads(node(root, '''import { createRequire } from 'node:module';
const server = createRequire(import.meta.url)('./dist/server.cjs');
console.log(JSON.stringify(server.page()));
'''))
assert model["widget"] == {"module": "src/client.js", "export": "default"}, model
assert model["named"] == {"module": "src/client.js", "export": "named"}, model
assert model["value"] == "SERVER_SECRET_SENTINEL"
print("ok   one server entry discovers client boundaries and emits reference objects plus a manifest")
server_text = (root / "dist/server.cjs").read_text()
client_text = (root / "dist/client.mjs").read_text()
assert "SERVER_SECRET_SENTINEL" not in client_text
assert "CLIENT_BODY_EXECUTED_ON_SERVER" not in server_text
assert all("SHARED_IN_BOTH_ENVIRONMENTS" in text for text in (server_text, client_text))
print("ok   server and client implementations stay separate; shared code belongs to both")
assert node(root, '''import { createRequire } from 'node:module';
const server = createRequire(import.meta.url)('./dist/server.cjs');
try { server.forbiddenCall(); throw new Error('did not reject'); }
catch (e) { if (!e.message.includes('Cannot call client export')) throw e; }
console.log('rejected');
''') == "rejected"
print("ok   invoking a client export on the server fails explicitly")
assert node(root, '''globalThis.window = {};
const { resolveClientReference } = await import('./dist/client.mjs');
const ref = { module: 'src/client.js', export: 'default' };
if (resolveClientReference(ref)(3) !== 'SHARED_IN_BOTH_ENVIRONMENTS3') throw new Error('wrong implementation');
if (resolveClientReference({ ...ref, export: 'named' }) !== 42) throw new Error('named export lost');
for (const invalid of [null, { module: '__proto__', export: 'x' }, { ...ref, export: 'missing' }]) {
  let threw = false; try { resolveClientReference(invalid); } catch { threw = true; }
  if (!threw) throw new Error('accepted invalid reference');
}
console.log('resolved');
''') == "resolved"
print("ok   browser references resolve to real exports and reject unknown modules/exports")
first = {p.name: p.read_bytes() for p in (root / "dist").iterdir()}
build(root)
assert first == {p.name: p.read_bytes() for p in (root / "dist").iterdir()}
print("ok   paired outputs and reference IDs are deterministic")

bad = dict(BASE)
bad["src/client.js"] += '\nimport { unused } from "./helper.js";\n'
bad["src/helper.js"] = 'import "./database.js"; export const unused = 1;\n'
root = fixture("transitive-server-only", bad)
diagnostic = build(root, "server-only module reached from the client")
assert "src/client.js -> src/helper.js -> src/database.js" in diagnostic, diagnostic
print("ok   transitive server-only imports fail with an import chain, even if unused")

bad = dict(BASE)
bad["src/server.js"] += '\nimport "./browser-only.js";\n'
bad["src/browser-only.js"] = 'import "client-only"; export const dom = 1;\n'
root = fixture("client-only-on-server", bad)
assert "src/server.js -> src/browser-only.js" in build(root, "client-only module reached from the server")
print("ok   client-only dependencies require a client boundary")

bad = dict(BASE)
bad["src/client.js"] += '\nimport fs from "node:fs";\n'
root = fixture("node-in-browser", bad)
build(root, "server-only module reached from the client")
print("ok   Node builtins are rejected from the browser graph")

files = dict(BASE)
files["src/server.js"] += '\nimport { environment } from "conditional"; export { environment };\n'
files["src/client.js"] += '\nexport { environment } from "conditional";\n'
files["node_modules/conditional/package.json"] = json.dumps({"exports": {"browser": "./browser.js", "node": "./node.js"}})
files["node_modules/conditional/browser.js"] = 'export const environment = "BROWSER_CONDITION";\n'
files["node_modules/conditional/node.js"] = 'import "server-only"; export const environment = "NODE_CONDITION";\n'
root = fixture("conditions", files)
build(root)
assert "BROWSER_CONDITION" in (root / "dist/client.mjs").read_text()
assert "NODE_CONDITION" not in (root / "dist/client.mjs").read_text()
assert node(root, '''import { createRequire } from 'node:module';
console.log(createRequire(import.meta.url)('./dist/server.cjs').environment);
''') == "NODE_CONDITION"
print("ok   shared imports resolve separately under browser and Node package conditions")

files["node_modules/conditional/package.json"] = json.dumps({"exports": {"custom": "./custom.js", "browser": "./browser.js", "node": "./node.js"}})
files["node_modules/conditional/custom.js"] = 'import "server-only"; export const environment = "CUSTOM_SERVER_CONDITION";\n'
root = fixture("custom-conditions", files)
write(root, "build.bundler", (root / "build.bundler").read_text().replace('target app', 'target app\n  conditions custom'))
build(root)
assert "BROWSER_CONDITION" in (root / "dist/client.mjs").read_text()
assert node(root, '''import { createRequire } from 'node:module';
console.log(createRequire(import.meta.url)('./dist/server.cjs').environment);
''') == "CUSTOM_SERVER_CONDITION"
print("ok   explicit server conditions override paired defaults without leaking into browser resolution")

files = dict(BASE)
files["src/client.js"] = '''"use client";
export { default } from "./implementation.js";
export * from "./implementation.js";
export * as namespace from "./implementation.js";
'''
files["src/implementation.js"] = '''export default function Widget() { return 'widget'; }
export { value as named } from "./cycle.js";
export * from "./cycle.js";
'''
files["src/cycle.js"] = 'export const value = 42; export * from "./implementation.js";\n'
root = fixture("reexports", files)
build(root)
exports = json.loads((root / "dist/manifest.json").read_text())["modules"]["src/client.js"]["exports"]
assert exports == ["default", "named", "namespace", "value"], exports
print("ok   the existing linker resolves boundary reexports, namespaces and export-star cycles")

files = dict(BASE)
files["src/server.js"] += '\nimport { second } from "./second.js"; export { second };\n'
files["src/second.js"] = '"use client"; import { shared } from "./shared.js"; export function second() { return shared; }\n'
root = fixture("multiple-boundaries", files)
build(root)
manifest = json.loads((root / "dist/manifest.json").read_text())
assert sorted(manifest["modules"]) == ["src/client.js", "src/second.js"], manifest
assert node(root, '''globalThis.window = {};
const { modules } = await import('./dist/client.mjs');
if (modules['src/second.js'].second() !== 'SHARED_IN_BOTH_ENVIRONMENTS') throw new Error('second boundary lost');
console.log(Object.keys(modules).length);
''') == "2"
print("ok   multiple client boundaries share one browser registry")

files = dict(BASE)
files["src/client.js"] = '"use client"; module.exports = function () {};\n'
root = fixture("commonjs-boundary", files)
build(root, "must be an ES module")
print("ok   opaque CommonJS boundaries fail rather than silently losing exports")

files = dict(BASE)
files["src/client.js"] = '"use client"; export { default, named } from "./implementation.js"; export * from "./dynamic.cjs";\n'
files["src/implementation.js"] = 'export default function Widget() {} export const named = 42;\n'
files["src/dynamic.cjs"] = 'module.exports = { runtimeOnly: 1 };\n'
root = fixture("dynamic-star-boundary", files)
build(root, "must be an ES module with statically known exports")
print("ok   dynamic export-star boundaries also fail rather than omit runtime exports")

files = dict(BASE)
files["src/database.js"] = '"use server"; export async function secret() { return 1; }\n'
root = fixture("unsupported-actions", files)
build(root, "use server actions are not supported")
print("ok   unsupported server actions produce an explicit diagnostic")

files = dict(BASE)
files["src/database.js"] = 'export async function secret() { "use server"; return 1; }\n'
root = fixture("inline-actions", files)
build(root, "use server actions are not supported")
print("ok   inline server actions also fail explicitly")

files = dict(BASE)
files["src/client.js"] = '''"use client";
export { default, named } from "./implementation.js";
export * from "./left.js";
export * from "./right.js";
'''
files["src/implementation.js"] = 'export default function Widget() {} export const named = 42;\n'
files["src/left.js"] = 'export const ambiguous = 1;\n'
files["src/right.js"] = 'export const ambiguous = 2;\n'
root = fixture("ambiguous-stars", files)
build(root)
exports = json.loads((root / "dist/manifest.json").read_text())["modules"]["src/client.js"]["exports"]
assert exports == ["default", "named"], exports
print("ok   ambiguous star exports do not become server references")

files = {"src/server.js": 'const text = "use client"; export { text };\n'}
root = fixture("not-a-directive", files)
build(root)
assert json.loads((root / "dist/manifest.json").read_text())["modules"] == {}
print("ok   directive text outside the directive prologue does not create a boundary")

root = fixture("output-collision", BASE)
spec = (root / "build.bundler").read_text().replace('client-outfile "dist/client.mjs"', 'client-outfile "dist/server.cjs"')
write(root, "build.bundler", spec)
build(root, "must have different paths")
print("ok   conflicting output paths fail before any bundle is written")

root = fixture("conflicting-format", BASE)
write(root, "build.bundler", (root / "build.bundler").read_text().replace('target app', 'target app\n  format esm'))
build(root, "paired builds emit cjs")
print("ok   unsupported paired output formats are diagnosed instead of ignored")

root = fixture("orphan-manifest", BASE)
write(root, "build.bundler", (root / "build.bundler").read_text().replace('  client-outfile "dist/client.mjs"\n', ''))
build(root, "client-manifest needs client-outfile")
print("ok   a manifest without a paired output reports the located error from a fused list branch")

files = {"src/server.js": 'export const answer = 42;\n'}
root = fixture("no-client-boundary", files)
build(root)
assert json.loads((root / "dist/manifest.json").read_text())["modules"] == {}
print("ok   a server-only application emits an empty browser registry")

files = {
    "src/server.js": 'import "./effects.js"; export const answer = 42;\n',
    "src/effects.js": '"use client"; export {}; globalThis.clientEffects = (globalThis.clientEffects || 0) + 1;\n',
}
root = fixture("side-effect-boundary", files)
build(root)
assert json.loads((root / "dist/manifest.json").read_text())["modules"]["src/effects.js"]["exports"] == []
assert node(root, '''import { createRequire } from 'node:module';
createRequire(import.meta.url)('./dist/server.cjs');
if (globalThis.clientEffects !== undefined) throw new Error('client side effect ran on server');
await import('./dist/client.mjs');
console.log(globalThis.clientEffects);
''') == "1"
print("ok   side-effect-only ES module boundaries execute only in the browser")
print("all checks passed")
