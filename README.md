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
| `.rules` | 5,645 | Resolution, modules, TypeScript, tsconfig, naming, chunks, lowering, CSS bundling, legal comments, source maps, the build, the tools |
| `.attrs` | 2,654 | Early errors, what a file loads, JSX, what each statement declares, emit's renaming: attribute grammars, computed in one traversal |
| `.syntax` | 815 | JavaScript with JSX and TypeScript, CSS, literals, comments, where a big file can be cut, package.json and tsconfig.json |
| `.rewrite` | 157 | Minification, constant folding, dead code |
| `.facts` | 114 | Linking, tree shaking, and which root reaches what for code splitting |
| `.js` | 171 | The bundle's runtime helpers, and those lowering adds |
| `.bundler` | 70 | A demo build |
| `.pipeline` | 48 | Which stages may run in parallel, and five plans for running them |
| `.scopes` | 26 | Scoping |
| `.coil` | 15 | Four `main` functions, because a package's entry must be plain Coil |

The compilers for those languages are about 8,600 lines of Coil and 400 of grammars, with a runtime
of 1,900 (text, paths, tables, threads).

`.rules` is the least specific of these languages: a typed language over the grammar's nodes, with
pattern matching, relations, dynamic scope and code templates written in JavaScript's own syntax:

```
ExportDefault(e) => var-of(default-binding(base), e)
program-plus(p, stmt`$call_me();`)
```

A grammar names its nodes' children (`-> If(test, yes, no)`), so `.rules` reads `n.test` and
writes `n with { body: b }`, never a child by position. Comprehensions take patterns, tests and
other lists in any order, and make lists, joined lists and maps; `while` ends the loop before it at
the first item that fails, and `distinct` lets each key through once. `fold` keeps a running value,
`scan` every step of one, and `first`, `last`, `any`, `all`, `count` and `sum` search and add up:

```
[name.text for FuncDecl(name, ...) | ClassDecl(name, ...) in stmts]
{spec: t for spec in p.specs if let some(t) = unhooked-target(spec, p.path)}
fn unique-name(name: Text) -> Text = untaken(name) ?? first i in 2..: untaken(name ++ int-text(i))
fn directive-count(stmts: [Node]) -> Int = len([s for s in stmts while s is ExprStmt(Str(_))])
let places = scan p = Place(at: 0, breaks: 0, col: 0) for k in mapped: advanced(text, p, base + k.out)
```

A fixpoint is a recursive function, not a loop with a changed flag:

```
fn needed(names: [Text], definitions: {Text:Node}) -> [Text] {
  let more = [x for n in names if let some(d) = definitions[n] for x in idents(d)
              if starts-with(x, "__") and not (x in names) distinct x]
  if len(more) == 0 then names else needed(names ++ more, definitions)
}
```

Text and paths are a library (`split`, `join`, `replace-many`, `occurrences`, `span-of`,
`trim-bytes`, `path-stem`, `path-ancestors`, …) rather than byte loops in each file. Memo functions
remember by one or several arguments across all workers, so caches are declarations. A dynamically
scoped `context` bound with `with` gathers what a scope produces (a function's temporaries, the
helpers a program needs), and `with` gives its block's value. The compiler keeps these as fast as
the loops they replaced: `join` over a comprehension writes each item's pieces into one buffer, a
`++` chain allocates once, and an `everywhere fn` giving a list adds to one list as it walks.

A walk over a tree says only where it does something. An `everywhere fn` is a match on its node,
and wherever no case matches it is the same function of each child: the node rebuilt from them,
shared when none changed; for `-> Void`, each child visited; for `-> Bool`, whether any child's is
true; for a list, the children's lists one after another. A guarded case is where a walk stops:

```
everywhere fn super-through(n: Node, name: Text) -> Node = match n {
  CallExpr(Super(), args) => CallExpr(Ident(name), super-through(args, name))
  _ if own-this?(n) => n
}
```

It is closer to a small ML than to a one-purpose language, and some of it is still written at a low
level: `corpus/tools/altitude.py` counts 32% of the lines of `.rules` and `.attrs` in functions with
loops over indices, variables updated in place, global or context state written to, or byte
scanning (67% on 2026-11-05). What is left is mostly the build's own sequencing, symbol tables
passed by reference, naming, and printing.

Where a big file can be cut for parsing in parallel is a grammar too (`coarse.syntax`), all of it
fragments, so it builds one node for each stretch between cuts, and a repetition of single bytes
compiles to a loop over bytes. It costs three.js's build about 1.5 ms more than the hand-written
scanner did (42 ms, 0.86 of esbuild's time).

`.attrs` is an attribute grammar over a grammar's trees, compiled by the same compiler. Nothing in
it walks a tree: it declares attributes, and `on` blocks give equations for the nodes a pattern
matches. An `inh` attribute is inherited, a child having its parent's value unless an equation says
otherwise; a `given` one is inherited but not copied; a `collect` one is gathered in tree order;
an `input` is the same everywhere. The compiler makes one traversal that computes them all, and an
attribute grammar may `include` another, whose equations then run in the same traversal:

```
inh in-loop: Bool = false
collect problem: Problem?
on While(_, body) { body.in-loop = true }
on Continue(_) as n { if not in-loop { report("continue is only valid in a loop", n) } }
```

Early errors (`early.attrs`, 1,045 lines) are written this way, and include what a file loads
(`calls.attrs`), so a JavaScript file is checked and its `require` and `import()` calls found in one
traversal. So is what each top-level statement declares and mentions, for linking.

An attribute grammar may also rewrite the tree, in the same traversal. `rewrite Pattern => value`
says what a node becomes: the pattern sees the node as it was, and `x.out` is what a child the
pattern names became. A node no rule matches is rebuilt from its children, and is itself when they
all stayed; a rule giving `[…]` puts several nodes, or none, in a list's place. JSX lowering is
twelve such rules, and emit's renaming ten:

```
rewrite JsxAttr(name, v) as a => Prop(key-of(name), v.out) with { lo: a.lo, hi: a.hi }
rewrite JsxContainer(None()) => []
rewrite Member(object, property) as n =>
  namespace-read(n) ?? Member(object.out, property) with { lo: object.out.lo, hi: property.hi }
```

The languages' readers are one provider, `hl.readers`, compiled once as a native reader artifact
(`corpus/tools/readers.sh`, rebuilt only when the readers or the compiler change). Built from
source instead, Coil compiles each reader into every build and keeps what each reading allocates
until the build ends: the bundler took about 30 s and 8–9.8 GB. With the artifact it takes about
7 s and 1.6 GB. Run builds through `corpus/tools/guard.py`, which kills a process tree over a limit.

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
how the code moved out of Coil without changing behaviour. It passes no `--target`, so
`tools/same-lowered.py NEW BASE` compares lowered output (57 cases, TypeScript included), against
the previous commit's build, and `tools/same-split.py NEW BASE` code splitting and stylesheet assets,
hashed file names and maps included.

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
| tree-shaken lodash-es | 40.7 | 26.4 | 38.6 | 29.3 | **21.5** | 26.0 | 0.83 |
| all of lodash-es | 50.7 | 35.8 | 43.3 | 34.8 | **23.7** | 28.3 | 0.84 |
| rxjs | 22.9 | 13.8 | 22.3 | 15.8 | **12.1** | 15.8 | 0.76 |
| date-fns | 25.1 | 15.9 | 24.1 | 17.8 | **14.2** | 20.2 | 0.70 |
| d3 | 50.5 | 22.8 | 47.8 | 32.9 | **16.7** | 17.0 | 0.98 |
| zod | 72.0 | 50.3 | 52.9 | 45.2 | **20.2** | 17.2 | 1.17 |

Zod is the closest: 1.17 in this run and 1.21 in the next, so at the edge of 20%. What got it there
from 1.45, besides what is above: linking's liveness reads `mentions` directly instead of a copy,
`visits` is kept only for modules that forward names, and what a part mentions of its imports is
joined once (link went from 4.4 to 2.7 ms); relations are made big enough for the facts about to be
stated; a big file's early errors are checked per part; a file's `require()` and `import()` calls
are found once; minifying, ASCII and printing run as one pass per part; whitespace skipping costs
one comparison when the space was skipped already; task state is one thread-specific lookup.

Tried and taken out, because they were slower: data-parallel Datalog rule scans, resolving each
import as an item of its own for files with few imports, starting big files ahead of the queue, and
starting the worker pool from `main`.

Trees are immutable, and a pass shares what it does not change. The rewrite engine keeps a node
none of whose children changed, and marks its copies of what a rule captured as normal for the
pass, so they are not walked again; `n with { kids: [f(c) for c in n.kids] }` in `.rules` is `n`
itself when every `f(c)` is `c`. Minifying got 11–20% faster.

Per core this bundler still does about twice esbuild's work: most of the rest is the number of
passes over a tree, about a dozen to esbuild's three. Attribute grammars are how they become fewer.

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
