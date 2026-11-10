#!/usr/bin/env python3
"""Compile-time ownership checks for the generic boxed-record declaration."""
import json
from pathlib import Path
import subprocess
import guard

ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / 'out/record-layout-check'
WORK.mkdir(parents=True, exist_ok=True)
header = '''rules fixture
main run on big stack
boxed record Value { count: Int, items: [Int] }
record Container { value: Value }
'''
cases = {
    'field': ('var x = Value(count: 1, items: [])\n  x.count = 2', 'boxed records are immutable'),
    'nested': ('var x = Container(value: Value(count: 1, items: []))\n  x.value.count = 2', 'boxed records are immutable'),
    'collection': ('var x = Value(count: 1, items: [])\n  x.items ++= [2]', 'boxed records are immutable'),
    'map-key': ('let x = {Value(count: 1, items: []): 2}\n  print "{}", len(keys(x))', 'boxed records are values, not scalar map keys'),
}
for name, (body, expected) in cases.items():
    folder = WORK/name
    folder.mkdir(exist_ok=True)
    (folder/'Coil.toml').write_text('[package]\nname = "record-layout-check"\nentry = "main.coil"\nsource-roots = ['+json.dumps(str(ROOT/'compiler'))+']\n[readers]\n".rules" = "hl.readers"\n[modules]\n"fixture" = "fixture.rules"\n')
    (folder/'main.coil').write_text('(module record-layout-check)\n(import "fixture" :as f)\n(defn main [(argc i32) (argv (ptr (ptr i8)))] (-> i64) (f/main argc argv))\n')
    (folder/'fixture.rules').write_text(header+'fn run() -> Void {\n  '+body+'\n}\n')
    code, out, err, _, reason = guard.run(['coil','build','-O1','--meta-opt=2','-o','program'],9500,120,quiet=True,cwd=folder)
    assert code != 0 and expected in out+err, (name, code, reason, out+err)
    print('ok   boxed record rejects '+name, flush=True)
print('all boxed record ownership checks passed')
