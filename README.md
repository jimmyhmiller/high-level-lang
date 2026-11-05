# high-level-lang

An experiment in language-driven development: a JavaScript bundler written as a tower of
small languages, each one a Coil reader metaprogram. It is checked against esbuild on
lodash and eight other real libraries.

```
build.bundler        targets, formats, defines, plugins          → the build program
├── js.syntax        JavaScript as a scannerless PEG              → parser, AST, printer, node table
├── js.scopes        which nodes open scopes, where bindings land → resolver
├── link.facts       ES linking and tree shaking, as Datalog      → nested loops with indexes
├── minify.rewrite   syntax minification rules                    → pattern matcher, peephole
└── Coil             the rest: module resolution, renaming, early errors
```

Every language except `.syntax` is itself defined by a `.syntax` grammar, in
`poc/src/hl/grammars/`. `.syntax` keeps a hand-written parser, because it is the bootstrap.

The compiled bundler is about 530 KB of native code, specialised to its spec.

## Running it

```sh
cd corpus && npm install --ignore-scripts && node node_modules/esbuild/install.js
mkdir -p vendor && git clone --depth 1 https://github.com/tc39/test262-parser-tests vendor/test262-parser-tests

tools/build-tools.sh -O3                                  # corpus/out/bin/{esb,jsparse}
out/bin/esb app/named.js --minify --outfile=out/app.js    # command line, esbuild style
python3 tools/verify.py out/bin/esb out/bin/jsparse       # every claim below
python3 tools/bench.py out/bin                            # timings against esbuild

cd ../poc && coil build -O3 -o ../corpus/out/bin/spec     # the bundler build.bundler describes
cd ../corpus && out/bin/spec
```

## Results

`tools/verify.py` checks all of this in one run.

**Parser.** Valid code is checked by round trip: print our tree, then require that esbuild
normalises the original and our output to the same bytes, or that acorn gives the same tree.

| Corpus | Files | Parsed | Round trip |
|---|---|---|---|
| lodash.js | 1 | 1 | same acorn tree |
| lodash-es | 644 | 644 | 644 byte-identical |
| test262 `pass/` | 1,983 | 1,983 | 1,972 identical, 5 same tree, 6 esbuild itself rejects |
| three, zod, rxjs, date-fns, preact, immer, react, axios, d3 | 4,217 | 4,217 | 4,106 identical, 111 same tree |

Invalid code: 714 of 729 test262 `fail/` and 662 of 668 `early/` are rejected. What remains
is regex pattern validation, some Annex B cases, and tests newer JavaScript made valid.

**Bundles against esbuild, minified.** All produce the same program output as esbuild's.

| App | Ours (bytes) | esbuild | Difference |
|---|---|---|---|
| lodash-es, tree-shaken | 34,641 | 35,207 | -1.6% |
| all of lodash-es | 91,647 | 92,958 | -1.4% |
| lodash (CommonJS) | 74,093 | 74,092 | 0.0% |
| three | 263,047 | 258,124 | +1.9% |
| zod | 387,473 | 454,182 | -14.7% (+0.7% against `--charset=utf8`, 384,756 bytes) |
| rxjs | 18,199 | 17,510 | +3.9% |
| date-fns | 23,240 | 22,915 | +1.4% |
| preact | 11,047 | 11,045 | 0.0% |
| immer | 9,562 | 9,431 | +1.4% |
| react + react-dom/server | 217,450 | 216,850 | +0.3% |
| d3 | 47,246 | 46,294 | +2.1% |
| features test app (small) | 2,679 | 2,520 | +6.3% |

Unminified, tree-shaken lodash-es and all of lodash-es are **byte-identical** to esbuild's
output after normalising. That covers tree shaking, module order and renaming.

**Soundness of minification.** An exerciser calls every exported function of lodash,
date-fns, d3 and immer on a matrix of inputs: about 300,000 calls. Results match esbuild's,
plain and minified. Only lines where esbuild's own plain and minified builds agree count.

**Speed.** Single-threaded, against esbuild on one core and on all of them (ms, best of 9):

| App | Ours | esbuild, 1 core | esbuild, all cores |
|---|---|---|---|
| tree-shaken lodash-es | 75 | 76 | 29 |
| all of lodash-es | 87 | 78 | 30 |
| lodash (CommonJS) | 44 | 24 | 19 |
| three | 164 | 56 | 54 |
| zod | 119 | 48 | 22 |
| react | 67 | 30 | 17 |
| d3 | 85 | 42 | 19 |

So about 1 to 3 times esbuild per core. Parsing and printing lodash.js alone takes about the
same as esbuild (around 19 ms each). The clearest next win is parsing files on several threads.

## What it does

Module graph, Node resolution (`exports`, `main` fields, conditions, `sideEffects: false`),
scope hoisting, esbuild-compatible renaming, tree shaking with `/* @__PURE__ */` and class
purity, CommonJS wrapping, `__esm` wrapping for `require` and `import()` of ES modules,
namespace objects, JSON, `define`, iife/esm/cjs output, global names, `--external`,
`--platform=node`, identifier and syntax minification, source maps, per-target plugins.

## What it does not do

Being explicit, because "everything esbuild does" is a lot:

- **Not built:** code splitting, TypeScript, JSX and CSS loaders, syntax lowering for older
  targets, watch and serve, legal comments in output, the plugin API.
- **Hard errors for now:** `export *` or re-exports from a CommonJS module, and destructuring at
  the top level of an ES module that is `require`d or `import()`ed.
- **Simplifications:** `sideEffects` as an array counts as "has effects", which is safe but
  keeps more. Source maps have no `names`. Regex patterns are not validated. Labels are not
  renamed. Single-use `const` inlining is missing, because it needs use counts the rewrite
  rules cannot see yet.

## Layout

- `poc/src/hl/`: the languages. `syntax`, `rewrite`, `facts`, `scopes` and `bundler` are readers.
- `poc/src/hl/grammars/`: the grammars of those languages.
- `poc/src/bundle/`: the bundler: `js.syntax`, `js.scopes`, `link.facts`, `minify.rewrite`, and Coil.
- `poc/src/app/`: a demo spec with three targets and a plugin.
- `corpus/`: test apps and oracles. `node_modules` and `vendor` are not checked in.
- `experiments/`: small programs that established how Coil readers behave, and repros of Coil issues.

Coil issues found on the way are in `experiments/repros/`. Do not run `coil lint --fix` in
`poc/` with a compiler older than the `reader-guest-spans` fix: it can overwrite DSL sources.
