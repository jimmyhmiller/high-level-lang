#!/usr/bin/env python3
"""Generate and execute a large feature graph; report measured build cost, never inferred scale."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import time
import guard

ROOT = Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--binary', default=str(ROOT / 'out/bin/esb'))
parser.add_argument('--modules', type=int, default=10000)
parser.add_argument('--effects', action='store_true', help='shared observable initialization under the large graph')
parser.add_argument('--incremental', action='store_true', help='measure cold/warm disk cache and a source edit')
parser.add_argument('--entries', type=int, default=32)
parser.add_argument('--policies', nargs='+', default=['exact', 'balanced'])
args = parser.parse_args()
assert args.modules >= args.entries >= 2
WORK = ROOT / 'out/application-scale'
if WORK.exists(): shutil.rmtree(WORK)
WORK.mkdir(parents=True)
(WORK / 'package.json').write_text('{"type":"module"}')
features = WORK / 'features'
features.mkdir()
shared = WORK / 'shared'
shared.mkdir()
if args.effects:
    (shared / 'config.js').write_text('globalThis.scaleInitializations=(globalThis.scaleInitializations||0)+1;export const config={multiplier:1};')
# Shared scoring functions have narrow and wide consumers. Every feature reads two shared
# families. Exporting a second independent function exercises module/fragment policy differences.
for i in range(128):
    (shared / f'policy-{i}.js').write_text(
        ('import {config} from "./config.js";\n' if args.effects else '') +
        f'export function weight(input) {{ return input.priority * {i + 1} + input.budget % 97' + (' + config.multiplier' if args.effects else '') + '; }\n'
        f'export function unused(input) {{ return "UNUSED_POLICY_{i}:" + input; }}\n')
for i in range(args.modules):
    (features / f'feature-{i}.js').write_text(
        f'import {{weight as owner}} from "../shared/policy-{i % 128}.js";\n'
        f'import {{weight as category}} from "../shared/policy-{(i // 32) % 128}.js";\n'
        f'export function score(input) {{ return owner(input) + category(input) + {i} % 19; }}\n'
        f'export function explain(input) {{ return "FEATURE_EXPLANATION_{i}:" + score(input); }}\n')
entries = []
for i in range(args.entries):
    indexes = list(range(i, args.modules, args.entries))
    imports = ''.join(f'import {{score as s{j}}} from "./features/feature-{j}.js";\n' for j in indexes)
    expression = '+'.join(f's{j}(input)' for j in indexes)
    name = f'report-{i}.js'
    entries.append(name)
    (WORK / name).write_text(imports + f'export function run(input) {{ return {expression}; }}\n')
runner = 'const input={priority:3,budget:42000};const values=[];for (const file of process.argv.slice(1)) { values.push((await import(file)).run(input)); }console.log(JSON.stringify({values,initializations:globalThis.scaleInitializations||0}));'
def execute(directory):
    result = subprocess.run(['node', '--input-type=module', '-e', runner,
                             *[(directory / name).as_uri() for name in entries]], capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)
expected = execute(WORK)
results = []
for policy in args.policies:
    for fragments in [False, True]:
        output = WORK / f'{policy}-{fragments}'
        command = [str(Path(args.binary).resolve()), *[str(WORK / name) for name in entries],
                   '--splitting', '--format=esm', '--pipeline=full', f'--outdir={output}',
                   f'--chunk-policy={policy}', f'--fragments={str(fragments).lower()}']
        if args.incremental: command.append('--cache')
        original = (features / 'feature-0.js').read_text()
        for stage in (['cold', 'warm', 'edit'] if args.incremental else ['cold']):
            if stage == 'edit':
                (features / 'feature-0.js').write_text(original.replace('+ 0 % 19', '+ 1 % 19'))
            expected = execute(WORK)
            started = time.perf_counter()
            code, stdout, stderr, peak, reason = guard.run(command, 6000, 180, quiet=True, cwd=WORK)
            elapsed = time.perf_counter() - started
            assert code == 0 and not reason, (reason, stdout[-1000:], stderr[-3000:])
            assert execute(output) == expected
            assert expected['initializations'] == int(args.effects)
            files = list(output.glob('*.js'))
            row = dict(policy=policy, fragments=fragments, stage=stage, shared_effects=args.effects,
                       feature_modules=args.modules, total_source_modules=args.modules + 128 + args.entries + int(args.effects),
                       entries=args.entries, seconds=round(elapsed, 3), peak_mb=round(peak, 1) if peak else None,
                       retained_output_files=len(files), retained_output_bytes=sum(p.stat().st_size for p in files))
            results.append(row)
            print(json.dumps(row), flush=True)
        (features / 'feature-0.js').write_text(original)
(WORK / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
print('ALL large-graph outputs match native execution', flush=True)
