#!/usr/bin/env python3
"""Compile and run generic pipeline contexts, including full-width integer keys and cycles."""
import json
import os
from pathlib import Path
import subprocess
import guard

ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / 'out/context-check'
WORK.mkdir(parents=True, exist_ok=True)
(WORK / 'Coil.toml').write_text('''[package]
name = "context-check"
entry = "main.coil"
source-roots = [''' + json.dumps(str(ROOT / 'compiler')) + ''']
[readers]
".rules" = "hl.readers"
".pipeline" = "hl.readers"
[modules]
"fixture" = "fixture.rules"
"fixture.pipeline" = "fixture.pipeline"
''')
(WORK / 'main.coil').write_text('''(module context-check)
(import "fixture" :as f)
(import "fixture.pipeline" :as pipeline)
(defn main [(argc i32) (argv (ptr (ptr i8)))] (-> i64)
  (pipeline/run-started! (if (> argc 2) "bare" (if (> argc 1) "incremental" "once")) "" (= argc 2))
  (f/main argc argv))
''')
(WORK / 'fixture.pipeline').write_text('''pipeline fixture
strategy once
  default
  keep fixture/keyed fixture/textual fixture/cycle-b fixture/shared-key
end
strategy bare
end
strategy incremental
  from once
  watching
  tracks
end
contexts by fixture/context shared fixture/shared end
''')
(WORK / 'fixture.rules').write_text('''rules fixture
main run on big stack
setting context: Text = ""
setting own: Int
setting shared: Int
fn keyed(n: Int) -> Int = own + (if n == 7 then 0 else 1)
fn textual(n: Text) -> Int = own
fn identity(n: Int) -> Int = n
fn own-value(n: Int) -> Int = own + n
fn apply(f: Fn(Int)->Int, n: Int) -> Int = f(n)
fn shared-key(n: Int) -> Int = shared + apply(identity, n)
fn cycle-a(n: Int) -> Int = if n == 0 then own else cycle-b(n - 1)
fn cycle-b(n: Int) -> Int = cycle-a(n)
fn check(ok: Bool) -> Void { if not ok { panic "context regression" } }
fn side(name: Text, value: Int) -> Void {
  with context = name {
    with own = value {
      check(keyed(7) == value)
      check(keyed(288230376151711751) == value + 1)
      check(textual("value") == value)
      check(cycle-b(2) == value)
      check(shared-key(7) == 10)
      check(apply(own-value, 0) == value)
    }
  }
}
fn run() -> Void {
  with shared = 3 {
    side("client", 10)
    side("server", 20)
    side("client", 10)
    side("server", 21)
    with own = 30 { check(textual("client\\x01;value") == 30) }
    side("client", 10)
  }
  print "all context checks passed"
}
''')
code, out, err, _, reason = guard.run(
    ['coil', 'build', '-O1', '--meta-opt=2', '-o', 'program'],
    9500, 300, quiet=True, cwd=WORK, env=dict(os.environ, HL_SHOW_READS='1'))
assert code == 0, (reason, out, err)
reads = {}
for line in (out + err).splitlines():
    if line.startswith('[reads] fixture/'):
        name, values = line[len('[reads] fixture/'):].split(':', 1)
        reads[name] = set(values.split())
assert reads.get('shared-key') == {'fixture.shared'}, reads
assert reads.get('cycle-b') == {'fixture.own'}, reads
assert reads.get('keyed') == {'fixture.own'}, reads
print('ok   static reads distinguish shared work and follow recursive calls', flush=True)
for poison in (False, True):
    env = dict(os.environ)
    if poison:
        env['HL_REGION_CHECK'] = '1'
    for strategy, args in [('once', []), ('incremental', ['tracked']), ('bare', ['bare', 'bare'])]:
        p = subprocess.run([str(WORK / 'program')] + args, env=env, capture_output=True, text=True, timeout=30)
        assert p.returncode == 0 and 'all context checks passed' in p.stdout, (strategy, poison, p.returncode, p.stdout, p.stderr)
        print('ok   generic context keys, per-context settings, shared settings and cyclic reads'
              + f' ({strategy})' + (' (region check)' if poison else ''), flush=True)
