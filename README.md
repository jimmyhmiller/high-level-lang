# high-level-lang

An experiment in language-driven development: a JavaScript bundler specified entirely in small
languages, each one a Coil reader metaprogram. It is checked against esbuild on lodash and eleven
other real libraries.

```
build.bundler        targets, formats, defines, loaders, hooks      → the build program
build.pipeline       stages, and plans of how many threads run them → plans, checked for shared state
├── js.syntax        JavaScript as a scannerless PEG                → parser, AST, printer, node table
├── literal.syntax   the inside of strings and templates            → a parser for escapes
├── comments.syntax  where annotations can be                       → a scanner for /* @__PURE__ */
├── package.syntax   package.json, only the parts resolution reads  → a parser
├── js.scopes        which nodes open scopes, where bindings land   → resolver
├── link.facts       ES linking and tree shaking, as Datalog        → nested loops with indexes
├── minify.rewrite   syntax minification rules                      → pattern matcher, peephole
└── *.rules          the logic: resolution, loading, early errors,  → typed native code
                     analysis, emit, renaming, source maps, the build
```

Every language except `.syntax` is defined by a `.syntax` grammar in `poc/src/hl/grammars/`.
`.syntax` keeps a hand-written parser, because it is the bootstrap.

## The split

There is no bundler logic in Coil. `poc/src/bundle/` and `poc/src/app/` contain no `.coil` file
at all, and `poc/src/hl/` knows nothing about JavaScript or bundling: it is grammars, types,
tables, Datalog and rewriting in general, plus a runtime of buffers, files and Unicode.

| Language | Lines | What it says |
|---|---|---|
| `.rules` | 9,191 | Resolution, modules, JSX, TypeScript, tsconfig, early errors, analysis, emit, naming, chunks, lowering, CSS bundling, legal comments, source maps, the build, the tools |
| `.syntax` | 780 | JavaScript with JSX and TypeScript, CSS, literals, comments, package.json and tsconfig.json |
| `.rewrite` | 157 | Minification, constant folding, dead code |
| `.facts` | 114 | Linking, tree shaking, and which root reaches what for code splitting |
| `.js` | 171 | The bundle's runtime helpers, and those lowering adds |
| `.bundler` | 70 | A demo build |
| `.pipeline` | 48 | Which stages may run in parallel, and five plans for running them |
| `.scopes` | 26 | Scoping |
| `.coil` | 15 | Four `main` functions, because a package's entry must be plain Coil |

The compilers for those languages are about 8,400 lines of Coil and 300 of grammars.

`.rules` is the least specific of these languages: a typed language over the grammar's nodes, with
pattern matching, relations, dynamic scope and code templates written in JavaScript's own syntax:

```
ExportDefault(e) => var-of(default-binding(base), e)
program-plus(p, stmt`$call_me();`)
```

It is closer to a small ML than to a one-purpose language. Some of it is still byte loops, notably
number spelling, VLQ and path normalising. `early.rules` (968 lines) is the largest file and mostly
a translation of the specification's rules, so it is the best candidate for a language of its own.

Compile time is the real cost: building the tools peaks at about 9 GB, of which the reader image
is about 3.2 GB. Run builds through `corpus/tools/guard.py`, which kills a process tree over a limit.

## Running it

```sh
cd corpus && npm install --ignore-scripts && node node_modules/esbuild/install.js
mkdir -p vendor && git clone --depth 1 https://github.com/tc39/test262-parser-tests vendor/test262-parser-tests

python3 tools/guard.py 9500 500 tools/build-tools.sh -O3  # corpus/out/bin/{esb,jsparse,spec}
out/bin/esb app/named.js --minify --outfile=out/app.js    # command line, esbuild style
python3 tools/verify.py out/bin/esb out/bin/jsparse       # every claim below
out/bin/spec                                              # the build build.bundler describes
```

`tools/same.py` compares a new build with a frozen one, byte for byte, across 189 outputs. That is
how the code moved out of Coil without changing behaviour.

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

**Bundles against esbuild, minified.** All produce the same program output as esbuild's. Output is
ASCII, as esbuild's is by default (`--charset=utf8` turns that off).

| App | Ours (bytes) | esbuild | Difference |
|---|---|---|---|
| lodash-es, tree-shaken | 35,145 | 35,207 | -0.2% |
| all of lodash-es | 92,180 | 92,958 | -0.8% |
| lodash (CommonJS) | 74,500 | 74,092 | +0.6% |
| three | 263,253 | 258,124 | +2.0% |
| zod | 456,947 | 454,182 | +0.6% |
| rxjs | 18,199 | 17,510 | +3.9% |
| date-fns | 23,240 | 22,915 | +1.4% |
| preact | 11,047 | 11,045 | +0.0% |
| immer | 9,562 | 9,431 | +1.4% |
| react + react-dom/server | 218,736 | 216,850 | +0.9% |
| d3 | 47,251 | 46,294 | +2.1% |
| features test app (small) | 2,679 | 2,520 | +6.3% |
| re-exports test app (small) | 1,400 | 1,357 | +3.2% |

Unminified, tree-shaken lodash-es and all of lodash-es are **byte-identical** to esbuild's
output after normalising. That covers tree shaking, module order and renaming.

**Soundness of minification.** An exerciser calls every exported function of lodash,
date-fns, d3 and immer on a matrix of inputs: about 300,000 calls. Results match esbuild's,
plain and minified. Only lines where esbuild's own plain and minified builds agree count.

**Speed.** Single-threaded, `--minify`, ms, best of 7. Moving the logic out of Coil cost almost
nothing:

| App | Logic in Coil | Logic in `.rules` |
|---|---|---|
| tree-shaken lodash-es | 72 | 72 |
| all of lodash-es | 85 | 86 |
| lodash (CommonJS) | 39 | 40 |
| react | 62 | 62 |
| d3 | 78 | 79 |
| zod | 108 | 110 |
| three | 143 | 146 |

Against esbuild it is about 1 to 3 times slower per core, measured before this move: esbuild on one
core took 76, 78, 24, 30, 42, 48 and 56 ms on those apps, and is faster still on all cores.

## Parallelism

How the build divides its work is a language of its own. `poc/src/app/build.pipeline` names the
stages that work on one file, module or part at a time, the functions each runs, and plans:

```
stage load     per file   bundle.modules/visit-file bundle.modules/next-files bundle.modules/first-files ...
stage facts    per module bundle.analysis/on-demand-calls bundle.analysis/summaries-of
stage emit     per module bundle.mangle/unit-usage bundle.emit/unit-emitted
stage optimize per part   bundle.api/default-optimize bundle.ascii/converted
stage print    per part   bundle.api/render-part
stage link     whole      bundle.analysis/link

plan full
  threads auto
  load parallel
  facts parallel
  emit parallel
  optimize parallel auto parts 48
  print parallel auto parts 24
end
```

A plan that runs a stage in parallel compiles only if nothing those functions call, in any module,
writes shared state. The checker infers each function's effects from the `.rules` sources and says
what is in the way. Running `load-file` in parallel, for example:

```
plan unsafe runs graph in parallel, but bundle.modules/load-file
  writes shared state bundle.modules.table, in bundle.modules/load-file
  writes shared state bundle.modules.modules, in bundle.modules/load-file
  writes shared state bundle.modules.by-path, in bundle.modules/load-file
  writes shared state bundle.cssbundle.assets, in bundle.cssbundle/file-asset
  bundle.modules/load-file calls transform, whose effects cannot be known here
  ...
```

A query of a `.facts` database counts as a read; relations make the indexes queries need under a
lock, so many threads can query at once.

`.rules` has what the stages need:
- `task state`: one copy per worker, for caches and scratch space.
- `memo fn`: an answer computed once per build by whichever worker asks first, then shared. A
  worker that asks while another computes it waits. Directory listings, `package.json`, and a big
  file's pieces are memos.
- `parallel-map`, and `parallel-walk`, which follows imports as workers find them. Its optional
  `first` names follow-ups that carry on an item's own work, ahead of what is waiting.
- `arrive!(key, n)`: of `n` items, the last to finish is told so and goes on, so no worker waits
  for the others.

The runtime has a pool of parked workers, and a work queue that idle workers sleep on.

**Big files.** A big plain-JavaScript file is parsed in pieces. A piece starts at a top-level
declaration, found by a scan of the bytes; a wrong guess only means a piece is no program by
itself, and then the file is parsed whole. The last piece to finish prepares the file. Each part is
then walked for scopes in a table of its own, at the same time as early errors and comment scans.
The last of those grafts the parts' tables back in order, giving the same symbol and scope ids a
single walk would. A file with many imports resolves each as an item of its own.

Every plan gives the same output, byte for byte, as the serial build. That holds for 12 apps,
plain, minified, pretty and with source maps, and the verify suite passes under the `full` plan.
Parts are cut by weight and only after declarations, which no minification rule merges across.
`--pipeline=NAME` picks a plan, and `--threads=N` runs every stage on N threads.

`--minify`, ms, best of 15, every column measured side by side, 12-core (8 fast, 4 slow) M-series
laptop shared with other work:

| App | single | load-only | back-half | two | full | esbuild | full / esbuild |
|---|---|---|---|---|---|---|---|
| tree-shaken lodash-es | 48.3 | 30.9 | 47.0 | 35.5 | **24.2** | 27.1 | 0.89 |
| all of lodash-es | 61.7 | 41.9 | 53.3 | 42.3 | **28.7** | 29.2 | 0.98 |
| rxjs | 27.4 | 16.5 | 27.2 | 19.1 | **13.8** | 16.4 | 0.84 |
| date-fns | 29.6 | 18.4 | 28.4 | 20.5 | **16.2** | 20.6 | 0.79 |
| d3 | 58.5 | 27.2 | 56.2 | 38.6 | **19.7** | 17.3 | 1.13 |
| zod | 80.5 | 55.2 | 62.0 | 50.5 | **24.0** | 16.6 | 1.45 |

Zod is not yet within 20% of esbuild, and what stands in the way is measured:
- **Link is serial, about 4.6 ms:** the fact replay and the Datalog solve. Running long rule scans
  in chunks on several threads, with the same rows in the same order, made it slower (6.0 ms):
  at this size, dispatching costs more than the joins.
- **Memory.** Zod touches 115 MB to esbuild's 50. A tree node is about 88 bytes, and emit and the
  rewrite passes each build a new tree. Even exiting takes 2 ms, against 0.5 ms for a tiny build.
- **Its biggest files sit at the end of an import chain:** about 6.5 ms of loading, even with
  those files parsed and analysed in parallel pieces.

In CPU time this bundler does about 2.6 times esbuild's work on zod (130 ms to 50). Going further
means a compact tree rewritten in place, a faster Datalog engine, and fewer passes over the tree.

## What it does

Module graph, Node resolution (`exports`, `main` fields, conditions, `sideEffects: false`),
scope hoisting, esbuild-compatible renaming, tree shaking with `/* @__PURE__ */` and class
purity, CommonJS wrapping, re-exports from CommonJS, `__esm` wrapping for `require` and `import()`
of ES modules, namespace objects, `define`, aliases, loaders (js, json, text, base64, dataurl with
MIME types, file, css, empty), CSS bundling (`@import` in place with media queries, `url()` through the
loaders, whitespace minified, stylesheets imported from JavaScript), legal comments (eof, linked,
external, none, with esbuild's grouping for packages), TypeScript (types erased by the grammar, enums, namespaces, parameter properties, unused
imports, `import x = …`, `export =`, `./x.js` meaning `./x.ts`, and `tsconfig.json` with `extends`, `paths`, `baseUrl`, JSX settings,
`useDefineForClassFields` and `verbatimModuleSyntax`, and `experimentalDecorators`), JSX (classic, automatic and dev runtimes, preserve, pragmas in block comments), banner and
footer, tree shaking off, iife/esm/cjs and spec-defined output formats, `--target=es2015` and later (`??`, `?.`, logical
assignment, `**`, numeric separators, optional catch binding, object spread and rest, async
functions, async generators and `for await`, class fields, private members and static blocks, each
checked by acorn at that version), `--drop:console`, `--drop:debugger`, `--pure:`, `--packages=external`, `--charset`,
`--main-fields`, `--conditions`, `--resolve-extensions`, `--public-path`, several entries with `--outdir`, code splitting with
shared chunks and `import()` (`--splitting`, `--entry-names`, `--chunk-names`, `--outbase`), global
names, `--external`, `--platform=node`, identifier and syntax minification, source maps, and resolve,
load, transform and optimize hooks.

## What it does not do

Being explicit, because "everything esbuild does" is a lot:

- **Not built:** watch and serve, CSS modules, CSS nesting and other CSS lowering, JavaScript
  (stage 3) decorators, `accessor` fields, `--keep-names`, `--inject`, `--mangle-props`, `--metafile`,
  and inlining enum values across files.
- **Hard errors for now:** `export *` from a CommonJS or external module in the entry point of ES
  module output.
- **Hard errors for now:** `@import` with `layer()` or `supports()`, a media query on an import inside
  another, stylesheets with `--splitting`, `--legal-comments=inline`, the automatic JSX runtime in a
  CommonJS module, `--jsx=preserve` with `--pretty`, a decorated class expression or `export default`
  class, and decorators on members with computed names.
- **Hard errors when lowering:** `super` inside an async function, object rest nested inside another
  pattern or in an assignment, a computed key in an object rest, and calling a parenthesized optional
  chain, all below the version that has them; browser names in `--target`.
- **Simplifications:** CSS minification is whitespace and number spelling only, so minified
  stylesheets are a few percent larger than esbuild's. Content hashes in file names differ from
  esbuild's. A computed class field name is evaluated before the class's computed method
  names when lowered, not in source order. Data URLs are spelled out or base64, without esbuild's percent escaping. Source maps have no
  `names`. Regex patterns are not validated. Labels are not renamed. Single-use `const` inlining is
  missing.

## Layout

- `poc/src/hl/`: the languages. `syntax`, `rules`, `rewrite`, `facts`, `scopes`, `bundler` and
  `pipeline` are readers; `rt` and `symtab` are their domain-free runtime.
- `poc/src/hl/grammars/`: the grammars of those languages.
- `poc/src/bundle/`: the bundler, in those languages.
- `poc/src/tools/`: the command-line `esb` and `jsparse`, and `ptest`, which checks that `parallel-map` gives the serial answer, in `.rules`.
- `poc/src/app/`: a demo spec with four targets, a format, a loader and plugins, and the pipeline.
- `poc/src/boot/`: four `main` functions.
- `corpus/`: test apps and oracles. `node_modules` and `vendor` are not checked in.
- `experiments/`: small programs that established how Coil readers behave, and repros of Coil issues.

Coil issues found on the way are in `experiments/repros/`. Do not run `coil lint --fix` in
`poc/` with a compiler older than the `reader-guest-spans` fix: it can overwrite DSL sources.
