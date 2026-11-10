#!/usr/bin/env python3
"""Package map behavior compared with native Node, including rejected private paths."""
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
ESB = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / 'out/bin/esb'
WORK = ROOT / 'out/resolution-check'
if WORK.exists(): shutil.rmtree(WORK)
WORK.mkdir(parents=True)
checks = 0


def run(args, cwd):
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=60)


def case(name, mapping, spec='subject', files=None, reject=False, imports=None, source=None, flags=()):
    global checks
    root = WORK / name
    package = root / 'node_modules/subject'
    package.mkdir(parents=True)
    (root / 'package.json').write_text(json.dumps({'type': 'module', 'name': 'application',
        **({'imports': imports} if imports is not None else {})}))
    (package / 'package.json').write_text(json.dumps({'name': 'subject', 'type': 'module', 'exports': mapping}))
    for path, value in {'one.js': 'export default "one";', 'two.js': 'export default "two";',
                        'private.js': 'export default "private";', **(files or {})}.items():
        p = package / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(value)
    entry = source or f'import value from {json.dumps(spec)}; console.log(JSON.stringify(value));'
    (root / 'entry.js').write_text(entry)
    native = run(['node', *flags, 'entry.js'], root)
    assert (native.returncode != 0) == reject, (name, native.stdout, native.stderr)
    for plan in ('single', 'full'):
        output = root / f'{plan}.mjs'
        built = run([str(ESB), 'entry.js', '--platform=node', '--format=esm', f'--pipeline={plan}',
                     f'--outfile={output}', *[flag for flag in flags if flag.startswith('--conditions=')]], root)
        assert (built.returncode != 0) == reject, (name, plan, built.stdout, built.stderr)
        if not reject:
            actual = run(['node', str(output)], root)
            assert actual.returncode == 0 and actual.stdout == native.stdout, (name, plan, actual.stdout, actual.stderr, native.stdout)
        checks += 1
    print('ok  ', name, flush=True)

case('root-sugar', './one.js')
case('exact', {'.': './one.js', './two': './two.js'}, 'subject/two')
case('encapsulation', {'.': './one.js'}, 'subject/private.js', reject=True)
case('blocked', {'.': './one.js', './private.js': None}, 'subject/private.js', reject=True)
case('null-root', None, reject=True)
case('no-root', {'./two': './two.js'}, reject=True)
case('pattern', {'./*': './*.js'}, 'subject/one')
case('specific-pattern', {'./*': './private.js', './features/*': './*.js'}, 'subject/features/two')
case('exact-before-pattern', {'./*': './private.js', './one': './one.js'}, 'subject/one')
case('trailer-pattern', {'./*.js': './*.js'}, 'subject/two.js')
case('repeated-target-star', {'./*': './nested/*/*.js'}, 'subject/one', files={'nested/one/one.js': 'export default "repeated";'})
case('blocked-pattern', {'./*': './*.js', './private*': None}, 'subject/private-hidden', reject=True)
case('condition-order', {'node': './one.js', 'import': './two.js', 'default': './private.js'})
case('nested-condition', {'node': {'unknown': './private.js', 'import': './two.js'}, 'default': './one.js'})
case('nested-fallthrough', {'node': {'unknown': './private.js'}, 'default': './one.js'})
case('custom-condition', {'custom': './two.js', 'default': './one.js'}, flags=['--conditions=custom'])
case('array-invalid-fallback', ['../invalid.js', './one.js'])
case('array-null-fallback', [None, './one.js'])
case('array-condition-fallback', [{'unknown': './private.js'}, './two.js'])
case('array-missing-no-fallback', ['./missing.js', './one.js'], reject=True)
case('empty-array', [], reject=True)
case('invalid-target', '../one.js', reject=True)
case('traversal', './nested/../one.js', reject=True)
case('encoded-traversal', './%2e%2e/one.js', reject=True)
case('encoded-separator', './nested%2fone.js', reject=True)
case('numeric-condition', {'0': './one.js', 'default': './two.js'}, reject=True)
case('leading-zero-condition', {'01': './two.js', 'default': './one.js'}, flags=['--conditions=01'])
case('encoded-file-target', './%6fne.js')
case('mixed-keys', {'.': './one.js', 'default': './two.js'}, reject=True)
case('imports-external', './one.js', '#subject', imports={'#subject': 'subject'})
case('imports-pattern', './one.js', '#feature/two', imports={'#feature/*': 'subject/*'},
     files={'package.json': json.dumps({'type': 'module', 'exports': {'./*': './*.js'}})})
case('imports-missing', './one.js', '#missing', imports={}, reject=True)
case('imports-blocked', './one.js', '#blocked', imports={'#blocked': None}, reject=True)
case('imports-conditions', {'import': './one.js', 'require': './two.js'}, '#subject',
     imports={'#subject': {'import': 'subject', 'require': 'subject'}})
# A single module uses both request kinds. createRequire is the native reference; the bundler's
# recognized require() is deliberately used in the bundled source.
root = WORK / 'dual-kind'
package = root / 'node_modules/subject'
package.mkdir(parents=True)
(root / 'package.json').write_text('{"type":"module"}')
(package / 'package.json').write_text(json.dumps({'type': 'module', 'exports': {'import': './esm.js', 'require': './cjs.cjs'}}))
(package / 'esm.js').write_text('export default "imported";')
(package / 'cjs.cjs').write_text('module.exports="required";')
(root / 'entry.js').write_text('import value from "subject"; console.log(JSON.stringify([value,require("subject")]));')
(root / 'native.js').write_text('import {createRequire} from "node:module"; const require=createRequire(import.meta.url);\n' + (root / 'entry.js').read_text())
expected = run(['node', 'native.js'], root)
for plan in ('single', 'full'):
    built = run([str(ESB), 'entry.js', '--platform=node', '--format=esm', f'--pipeline={plan}', '--outfile=bundle.mjs'], root)
    assert built.returncode == 0, built.stdout + built.stderr
    actual = run(['node', 'bundle.mjs'], root)
    assert actual.returncode == 0 and actual.stdout == expected.stdout, (actual.stdout, actual.stderr, expected.stdout)
    checks += 1
print('ok   import and require select independent targets in one module')


# Self references and local imports share canonical module identity with their relative paths.
root = WORK / 'workspace'
root.mkdir()
(root / 'package.json').write_text(json.dumps({'name': '@workspace/domain', 'type': 'module',
    'exports': {'./*': './src/*.js'}, 'imports': {'#state': './src/state.js'}}))
(root / 'src').mkdir()
(root / 'src/state.js').write_text('export const state={count:0};')
(root / 'alias').symlink_to('src', target_is_directory=True)
(root / 'entry.js').write_text('import {state as a} from "@workspace/domain/state";import {state as b} from "#state";import {state as c} from "./alias/state.js";a.count++;console.log(JSON.stringify([a===b,b===c,c.count]));')
expected = run(['node', 'entry.js'], root)
for plan in ('single', 'full'):
    built = run([str(ESB), 'entry.js', '--platform=node', '--format=esm', f'--pipeline={plan}', '--outfile=bundle.mjs'], root)
    assert built.returncode == 0, built.stdout + built.stderr
    actual = run(['node', 'bundle.mjs'], root)
    assert actual.returncode == 0 and actual.stdout == expected.stdout, (actual.stdout, actual.stderr, expected.stdout)
    checks += 1
print('ok   package self reference, local imports and symlink retain one instance')

# Browser maps are a bundler convention. Compare with the installed esbuild oracle, and check
# Node builds ignore the browser substitutions. Both dependencies and files can be disabled.
root = WORK / 'browser'
package = root / 'node_modules/subject'
package.mkdir(parents=True)
(root / 'package.json').write_text('{"type":"module"}')
(package / 'package.json').write_text(json.dumps({'type': 'module', 'main': './node.js',
    'browser': {'./node.js': './browser.js', './unused.js': False, 'fs': False}}))
(package / 'node.js').write_text('export default "node";')
(package / 'browser.js').write_text('import fs from "fs";import unused from "./unused.js";export default ["browser",Object.keys(fs).length,Object.keys(unused).length];')
(package / 'unused.js').write_text('throw new Error("disabled module ran");')
(root / 'entry.js').write_text('import value from "subject";console.log(JSON.stringify(value));')
for platform in ('browser', 'node'):
    oracle = run([str(ROOT / 'tests/node_modules/.bin/esbuild'), 'entry.js', '--bundle', '--format=esm', f'--platform={platform}', '--outfile=oracle.mjs'], root)
    assert oracle.returncode == 0, oracle.stderr
    expected = run(['node', 'oracle.mjs'], root)
    for plan in ('single', 'full'):
        built = run([str(ESB), 'entry.js', '--format=esm', f'--platform={platform}', f'--pipeline={plan}', '--outfile=bundle.mjs'], root)
        assert built.returncode == 0, built.stdout + built.stderr
        actual = run(['node', 'bundle.mjs'], root)
        assert actual.returncode == 0 and actual.stdout == expected.stdout, (actual.stdout, actual.stderr, expected.stdout)
        checks += 1
print('ok   browser dependency/file replacements, disabled modules, and Node isolation')
print(f'ALL {checks} resolution checks passed')
