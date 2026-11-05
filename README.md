# high-level-lang

An experiment in language-driven development: a JavaScript bundler specified entirely in small
languages, each one a Coil reader metaprogram. It is checked against esbuild on lodash and eleven
other real libraries.

```
build.bundler        targets, formats, defines, loaders, hooks      → the build program
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
| `.rules` | 3,820 | Resolution, modules, early errors, analysis, emit, naming, source maps, the build, the tools |
| `.syntax` | 449 | JavaScript, its literals and comments, package.json |
| `.rewrite` | 157 | Minification, constant folding, dead code |
| `.facts` | 77 | Linking and tree shaking |
| `.js` | 58 | The bundle's runtime helpers |
| `.bundler` | 56 | A demo build |
| `.scopes` | 26 | Scoping |
| `.coil` | 12 | Three `main` functions, because a package's entry must be plain Coil |

The compilers for those languages are about 6,400 lines of Coil and 260 of grammars.

`.rules` is the least specific of these languages: a typed language over the grammar's nodes, with
pattern matching, relations, dynamic scope and code templates written in JavaScript's own syntax:

```
ExportDefault(e) => var-of(default-binding(base), e)
program-plus(p, stmt`$call_me();`)
```

It is closer to a small ML than to a one-purpose language. Some of it is still byte loops, notably
number spelling, VLQ and path normalising. `early.rules` (968 lines) is the largest file and mostly
a translation of the specification's rules, so it is the best candidate for a language of its own.

Compile time is the real cost: building the tools peaks at about 6.5 GB, of which the reader image
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

## What it does

Module graph, Node resolution (`exports`, `main` fields, conditions, `sideEffects: false`),
scope hoisting, esbuild-compatible renaming, tree shaking with `/* @__PURE__ */` and class
purity, CommonJS wrapping, re-exports from CommonJS, `__esm` wrapping for `require` and `import()`
of ES modules, namespace objects, `define`, aliases, loaders (js, json, text, base64, dataurl with
MIME types, file, css, empty), CSS bundling (`@import` in place with media queries, `url()` through the
loaders, whitespace minified, stylesheets imported from JavaScript), legal comments (eof, linked,
external, none, with esbuild's grouping for packages), TypeScript (types erased by the grammar, enums, namespaces, parameter properties, unused
imports, `import x = …`, `export =`, `./x.js` meaning `./x.ts`), JSX (classic, automatic and dev runtimes, preserve, pragmas in block comments), banner and
footer, tree shaking off, iife/esm/cjs and spec-defined output formats, `--target=es2015` and later (`??`, `?.`, logical
assignment, `**`, numeric separators, optional catch binding, object spread and rest, async
functions, async generators and `for await`, class fields, private members and static blocks, each
checked by acorn at that version), several entries with `--outdir`, code splitting with
shared chunks and `import()` (`--splitting`, `--entry-names`, `--chunk-names`, `--outbase`), global
names, `--external`, `--platform=node`, identifier and syntax minification, source maps, and resolve,
load, transform and optimize hooks.

## What it does not do

Being explicit, because "everything esbuild does" is a lot:

- **Not built:** watch and serve, CSS modules, CSS nesting and other CSS lowering, `tsconfig.json`, TypeScript decorators, `accessor` fields, inlining enum
  values across files.
- **Hard errors for now:** `export *` from a CommonJS or external module in the entry point of ES
  module output.
- **Hard errors for now:** `@import` with `layer()` or `supports()`, a media query on an import inside
  another, stylesheets with `--splitting`, `--legal-comments=inline`, the automatic JSX runtime in a CommonJS module, and `--jsx=preserve` with
  `--pretty`.
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

- `poc/src/hl/`: the languages. `syntax`, `rules`, `rewrite`, `facts`, `scopes` and `bundler` are
  readers; `rt` and `symtab` are their domain-free runtime.
- `poc/src/hl/grammars/`: the grammars of those languages.
- `poc/src/bundle/`: the bundler, in those languages.
- `poc/src/tools/`: the command-line `esb` and `jsparse`, in `.rules`.
- `poc/src/app/`: a demo spec with four targets, a format, a loader and plugins.
- `poc/src/boot/`: three `main` functions.
- `corpus/`: test apps and oracles. `node_modules` and `vendor` are not checked in.
- `experiments/`: small programs that established how Coil readers behave, and repros of Coil issues.

Coil issues found on the way are in `experiments/repros/`. Do not run `coil lint --fix` in
`poc/` with a compiler older than the `reader-guest-spans` fix: it can overwrite DSL sources.
