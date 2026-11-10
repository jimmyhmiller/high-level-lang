# high-level-lang

An experiment in language-driven development: a JavaScript bundler specified entirely in small
languages, each one a Coil reader metaprogram. It is checked against esbuild on lodash and eleven
other real libraries.

```
build.bundler        targets, formats, defines, loaders, hooks      → data, given meaning by spec.rules
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

Every language except `.syntax` is defined by a `.syntax` grammar in `src/languages/`.
`.syntax` keeps a hand-written parser, because it is the bootstrap.

## The split

There is no bundler logic in Coil. Everything written in the languages is under `src/`, which
holds no `.coil` file at all, and the Coil under `compiler/` knows nothing about bundling and
names no JavaScript node: it is grammars, types, tables, Datalog and rewriting in general, plus a
runtime of buffers, files and Unicode. `.scopes` takes node names as parameters, checked against
the grammar, and fixes no kind of scope: a file declares its own (`scope function …`, `scope block
…`), and says where names land by naming them: `names VarDecl Params in function` puts every binding
beneath those nodes in the nearest function scope, through blocks, and `name FuncExpr in own` puts a
node's first child in the scope it opens. That covers JavaScript's binding forms (`var` hoisting,
`let`, named function expressions, `with` and `eval`) and rules JavaScript lacks: `outside init of
Let` resolves a `let`'s value in the scope around it, so ML's `let x = x + 1 in …` reads the outer
`x`; `sequential LetStmt` gives a block's `let` a scope that holds what follows it, so
`{ let y = 1; let y = y + 1; y }` shadows as Rust does, also when the statements are a program's
parts analysed at once (`src/tools/letlang.scopes`, checked by langtest). The grammar language's
printer directives (`nomix`, `keepforbid`, soft tokens) are general, each declared by the grammar,
though each exists for one of JavaScript's quirks.

A build spec (`build.bundler`) is data, like `package.json`: `spec.syntax` reads it and
`spec.rules` says what each setting means, as a match from setting to options, with each error
located in the spec. The steps it names (rewrites, resolve and load hooks) are code, so the program
running it offers them by name (`src/app/build.rules`); a name it does not offer is an error at
that name in the spec. `out/bin/spec FILE` builds any spec with those steps.

| Language | Lines | What it says |
|---|---|---|
| `.rules` | 5,891 | Resolution, modules, TypeScript, tsconfig, naming, chunks, lowering, CSS bundling, legal comments, source maps, the build, what a build spec means, the tools |
| `.attrs` | 2,755 | Early errors, what a file loads, JSX, what each statement declares, emit's renaming: attribute grammars, computed in one traversal |
| `.syntax` | 906 | JavaScript with JSX and TypeScript, CSS, literals, comments, where a big file can be cut, package.json and tsconfig.json, build specs |
| `.rewrite` | 157 | Minification, constant folding, dead code |
| `.facts` | 133 | Linking, tree shaking, and which root reaches what for code splitting |
| `.js` | 171 | The runtime's helpers, the bundle's and lowering's, in esbuild's order |
| `.bundler` | 64 | A demo build: data, read with `spec.syntax` |
| `.pipeline` | 48 | Which stages may run in parallel, and five plans for running them |
| `.scopes` | 48 | Scoping, for JavaScript and for a small language with ML's and Rust's `let` |
| `.coil` | 15 | Four `main` functions, because a package's entry must be plain Coil |

The compilers for those languages are about 12,200 lines of Coil and 240 of grammars, with a runtime
of 2,100 (text, paths, tables, threads), counting neither comments nor blank lines.

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

A map is written `{k: v, …}`, and `a ++ b` of maps is `a` with `b`'s entries, `b` winning. A
fold whose step is `acc ++ more` adds `more` to its accumulator in place, never copying it, when
`more` is made whole before it goes in, so a loop that keeps a list or a table is a fold at the
same cost. Enum members settled one after another, each seeing those before it:

```
let settled: [Settled] = fold done = [] for m in members: done ++ [member-settled(done, m, name.text, param, a)]
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

It is closer to a small ML than to a one-purpose language. The goal is that every part of the
bundler is said as patterns, rules, derived facts and grammars, with no statements at all:
`tools/altitude.py` counts the lines of `.rules` and `.attrs` in functions with a statement of any
kind (`let`, an `if` statement or `if … then`, a loop, `return`, an assignment, a call made for its
effect). That was 81% on 2026-11-06, 13% on the morning of 2026-11-07, and is 15 lines (0.3%) at
the end of that day. Functions are matches: on text
(`"./" ++ rest`, `stem ++ ".js"`, `m ++ "e" ++ x`), lists (`[x, rest...]`), records
(`Options(explicit: true, ...)`) and several values at once (`match a, b { … }`), with guards whose
`is` patterns bind names; quantifiers take clauses (`first p in xs if file?(p): p`); `where` names
what an expression, an arm or an `on` block is made of; `on` blocks take guards; a fold over a
record changes its fields in place. A module's settings (resolve options, loaders, the chosen
names, the modules, the linking database) are declared `setting` and given for a call's extent by
`with`; no module keeps state. The module graph is a value made by a depth-first walk the language
knows (`depth-first(roots, children)`); linking answers what it works out, and each module's facts
are a list of `link.Fact` values, solved into a database by `link.solved`; a build answers the files
it writes, and one effect writes them; a lap of `--timing` is `timed(on, label, value)`. What is
still imperative is lowering's supply of fresh names (`fresh-name`, `temp`, `helper` in
`lower.rules`): esbuild names temporaries in the order lowering asks for them, so the order is
threaded through lowering as a context that changes.
`tools.langtest` (`src/tools/langtest.rules`) checks what the language's forms mean.

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
(`tools/readers.sh`, rebuilt only when the readers or the compiler change). Built from
source instead, Coil compiles each reader into every build and keeps what each reading allocates
until the build ends: the bundler took about 30 s and 8–9.8 GB. With the artifact it takes about
7 s and 1.6 GB. Run builds through `tools/guard.py`, which kills a process tree over a limit.

## Running it

```sh
(cd tests && npm install --ignore-scripts && node node_modules/esbuild/install.js)
git clone --depth 1 https://github.com/tc39/test262-parser-tests tests/test262

python3 tools/guard.py 9500 500 tools/build-tools.sh -O3      # out/bin/{esb,jsparse,spec}
out/bin/esb tests/apps/named.js --minify --outfile=out/app.js  # command line, esbuild style
python3 tools/verify.py out/bin/esb out/bin/jsparse           # every claim below
(cd tests && ../out/bin/spec)                                 # the build build.bundler describes
(cd tests && ../out/bin/spec other.bundler)                   # another spec, with the same steps
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

How the build divides its work is a language of its own. `src/app/build.pipeline` names the
stages that work on one file, module or part at a time, the functions each runs, and plans:

```
stage load     per file   bundle.modules/visit-file bundle.modules/next-files bundle.modules/first-files ...
stage facts    per module bundle.analysis/on-demand-calls bundle.analysis/summaries-of
stage emit     per module bundle.mangle/unit-usage bundle.emit/unit-emitted
stage optimize per part   bundle.api/default-optimize bundle.finish/ascii-only
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

A library inside one function, as lodash is, has no top-level place to cut, so it is cut inside
that function: the body holding most of the file is found by its indentation, the rest of the file
is parsed with only that body's line breaks left in it, and the pieces' statements go into the
body (`jsparse pieces FILE` shows the cut, and checks the tree is the one a whole parse gives). A
script that names `module`, `exports` or `require` is declared under CommonJS's wrapper before its
parts are walked, so a CommonJS file is analysed once. Looking ahead follows only what defines
leave of a file, so the development builds behind `process.env.NODE_ENV` are never parsed.

A CommonJS module is a single statement of the output, its wrapper, which nothing could cut. For
minifying and printing, the body of a statement heavier than a part's share is taken out, leaving
a hole, and cut into parts as the top level is; the parts fill the hole again, as trees or as text
with their source map marks moved. A body that a rule for a function's end would have changed is
done whole instead. `tools/same-plans.py` checks every plan against the serial one, maps included,
across 18 apps and 11 kinds of build.

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

CommonJS-heavy builds were the slowest and are now in line: react (`react-dom/server`, two 270 KB
CommonJS files) from 2.25 of esbuild's time to 1.02–1.05, and lodash as CommonJS from 1.54 to
1.06–1.10. Zod is the closest: 1.17 in this run and 1.21 in the next, so at the edge of 20%. What got it there
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

## Watching, the cache, and how answers are kept

How answers are kept is not part of the bundler. `src/bundle` is plain functions with one code path;
`src/app/build.pipeline` says, by function name, which of them a run keeps (a *strategy*) and how (a
*mechanism*), and the rules compiler applies it, as it applies the pipeline's parallel stages. A
run picks one with `--strategy=NAME`; `--watch` and `--cache` use the one marked `watching`.

```
mechanism red-green          # the mechanism of old
  store memory disk          # kept while the program runs, and saved with the cache
  check reads                # used again once everything it read is shown unchanged
  cutoff equal               # made again the same, it changes nothing that read it
  evict none
end

strategy incremental
  from once                  # everything `once` keeps, and its own
  tracks
  persists
  watching
  uses red-green
  keep with frozen bundle.modules/runtime-parsed
  keep bundle.modules/graph bundle.modules/parsed-alone …
end
```

Each part of a mechanism is a policy or a function of the strategy's own (`… by F`, in
`src/app/versions.rules`): `store memory disk by F` saves only the answers F picks; `check by F`
uses an answer again while F, a version such as a content hash, gives what it gave; `cutoff by F`
decides when an answer made again counts as the same; `evict by F` lets answers go after each
build; `update by F` makes an answer from the last one instead of afresh. A strategy's functions are
called through what the pipeline registers when a run picks it, so they may read anything the
bundler has. Strategies today: `once` (one build's repeated work: files read, names resolved), the
default; `incremental`; `lean` (at most 2000 answers per function, never saved); `trusting`
(packages under `node_modules` never checked); `coarse` (kept while nothing changes); `versioned`
(package.json and directory listings by content version); `tailored` (what three builds did not ask
for let go, only packages' answers saved, a package.json's layout ignored). Every strategy makes the
same bytes (`tools/strategy-check.py`); each that tracks is checked from the cache and while
watching against fresh builds, across edits to the entry, a module, a new file and a package.json
(`tools/mechanism-check.py`).

An answer kept by `check reads` records what it was made from: the files it read (by content, so a
write that changes nothing rebuilds nothing), the parts of the settings it read (by field path), and
the other answers it used (`hl.rt`'s dependency graph). A change marks only what depends on it, and
an answer made again the same stops the change there. Settings a build gives with `with` are
compared with what the last build gave, part by part. The cache on disk is an append-only log of
answers, read lazily; the watcher uses kqueue on macOS and inotify on Linux.

Granularity against Turbopack's (its sources at next.js 4ebb2b7; zod, 96 modules). `incremental`
keeps 2,193 answers; Turbopack's build runs about 10,850 tasks (`TURBOPACK_TRACING=turbo-tasks`).
Both keep a file's parse and analysis, its references, its side effects and its generated code per
module; a resolution per directory and specifier; a file's existence from its directory's listing;
and a package.json per package. Ours prints per group of a module's statements, where Turbopack
joins and minifies a whole chunk in one task, and ours saves every kept answer, where Turbopack
saves no parse, chunk item content or module graph. Turbopack splits modules into parts (1,282
part modules for zod) and answers each export question as a task of its own (`follow_reexports`,
`is_export_missing`, about 1,000). Linking here is Datalog over every module's facts, and
`incremental` keeps it `update by app.versions/solved-again`: the facts language's `solved-from`
brings the last database up to date by deleting and deriving again (DRed), group by group of
relations that derive each other, so what an edit's facts do not reach is not derived again. A
group where an edit takes out more than a quarter of the rows (a change reaching most of the tree
shaking, which Turbopack's build also does over the whole graph) is solved afresh from the groups
below it. Set `HL_CHECK_DATALOG` to check every update against solving afresh.

None of linking's three whole-program steps redoes the whole program after an edit:

- **The symbol table.** Each module's own table is placed once at its stable place
  (`modules.file-block`), and the build's table is joined from those blocks without copying them
  (`sym.joined-from`): joining costs one entry per module. A table that knows its blocks says where
  it differs from the last (`changes-Table`), so a setting given it looks only at what was read in
  the blocks that changed, not at everything anyone read.
- **Facts and Datalog.** The facts come in blocks, one per module and kind (`an.fact-blocks`); a
  block a build kept is the very block it was and is not looked into. Each row counts the facts that
  state it, and the database is changed in place: a row taken out stays where it is, marked, so an
  update reads a relation as it began (rows below its start, those it took out included) without a
  copy. Each update says which rows each relation lost and gained, and only queries that see those
  rows change. A database read back from the cache counts every fact once, on its first update.
- **Naming.** esbuild's renamer tries `x`, `x2`, `x3`… for a name, all of one stem (the name
  without the digits it ends in), so only names of one stem can take each other's, and the top
  level is named stem by stem (`nm.stem-named`). Linking's database says which modules claim or
  reserve names of each stem; modules keep ranks in the program's order while the order around them
  does (`rt.Ranks`), so adding a module renumbers nothing. Each module's block is named on its own
  (its claims' names, its nested scopes'), and the output's names are a table joined from those.

Dependencies here are marked dirty all the way up from what changed, and an answer that comes out
the same stops nothing already marked. What naming reads of the modules (their claims, by stem)
and of the top level (each stem's names) is therefore given as settings, which are compared part by
part, so an edit dirties only the stems it changed and the modules that read them.

Rebuild laps on Linux for twelve copies of zod, one statement added to a module (before → after):
the table 12.8 → 0.2 ms, facts and Datalog 11.6 → 2.7 ms. Naming, a statement edit 2.8 → about 2
ms; an edit that declares a new name, about 33 → 5 ms (on macOS). What a rebuild still does for
every module is a short pass: each module's block, facts and names found unchanged.

Rebuilds after one edit, on Linux (`tools/bench.py`, median of 7; esbuild 0.28.2 and Turbopack's
CLI built from next.js sources, measured 2026-11-09; ours 2026-11-10 at dea365e). The edit is to a
module the app imports:

| App | Rebuild (`--watch`) | esbuild `context().rebuild()` | Turbopack dev | One-shot, ours / esbuild |
|---|---|---|---|---|
| zod (96 modules) | 1.9 ms | 14.9 ms | 15.1 ms | 93 ms / 29 ms |
| date-fns | 3.1 ms | 14.8 ms | 12.6 ms | 48 ms / 31 ms |
| rx (225 modules) | 2.2 ms | 12.0 ms | 12.5 ms | 46 ms / 29 ms |
| three | 25.3 ms | 54.6 ms | not observable (the package says it has no side effects, and dev never serves the edit) | 143 ms / 71 ms |
| 12 copies of zod | 24.7 ms | 81.6 ms | 20.9 ms | 924 ms / 115 ms |

Making the three steps incremental cost a little elsewhere: more answers kept (zod's first build
makes 3,725 against 2,165), so first builds take 5–20% longer, the cache is about 10% bigger, and a
watcher holds a few percent more memory. For twelve copies of zod, a rebuild went from 40.1 to 24.7
ms and a run from a warm cache with one edit from 279 to 262 ms; what the rebuild spends now is
mostly parsing the edited file again (about 10 ms) and printing (about 10 ms).

`--hmr` watches too, writing a development format: no scope hoisting or renaming, each module a
function registered with `hmr_runtime.js` by path, its imports read through live namespace objects
(`hmr.attrs`, 170 lines without comments). `--serve=PORT` serves the output's directory and an
event stream at `/hmr`, from a thread in `hl.rt`. After each rebuild the modules whose functions
changed are sent; `hmr.facts` (Datalog, 4 rules) finds which modules run again, stopping at those
that call `import.meta.hot.accept()`, and reloads when an entry that does not accept changed.
`import.meta.hot.dispose` and `hot.data` carry state across a replacement.

### Memory while watching

A run that builds once keeps every value until it exits. A watcher lets go of what its builds no
longer need, and nothing in `src/bundle` says how: every value lives in a *region* (`hl.rt`), memory
taken in chunks and let go whole, and each region has an owner the incremental machinery already
knows.

- **An answer** is made in a region of its own, which its memo table holds. Made again, the new
  region replaces the old; made again the same (`cutoff equal`), the new one is let go and the old
  answer stays; evicted (`lean`, `generational`), its region goes with it.
- **Who uses a value holds its region.** Asking for an answer, or reading a setting, makes the
  region being made in hold the region the value is in, so an old answer lives as long as anything
  made from it.
- **A memo's arguments** are copied, the first time a key is computed, into a region of the store's,
  and the answer is computed from the copies, so no answer points into what its caller made.
- **A setting's value** (`with`, or given for good) is made in a region the setting holds while it is
  given and while it is held for the next build to compare against.
- **A relation** is a region of its own, since it is indexed after it is made, from any thread. A
  database brought up to date from the last (`update by`) holds the relations it shares with the
  last and its own new ones, not the last, which is let go once replaced.
- **The top of the program** (the watch loop, outside any memo) gives each turn of a statement loop
  a region, let go when the next turn starts; a `var` from before the loop that a turn gives a value
  holds a copy in a region of its own, and a loop with a `return` or that changes something from
  before it in place keeps its turns in the region around it.
- **The runtime's own tables** (the dependency graph, interned names, places, versions, watched
  paths) keep their own copies of the texts they keep, and free what they replace.

Regions nothing holds are let go at the end of each build, once the last save of the cache is done,
when no value on any stack can be in one; the cache's writer, which knows values by where they are,
forgets those addresses. Big chunks are pages of their own, given back to the system. One-shot
builds use the thread's own region, as before.

`tools/memory-check.py` runs a watcher through a hundred edits of two kinds, each making answers it
never made before or changing what linking derives, and checks that its regions hold what they held
after the twentieth build and that its footprint stays within 3%. `HL_REGION_CHECK=1` maps every
chunk and makes it unreadable once let go, so a value read after its region was let go stops the
program where it is read; the watch, HMR, cache and mechanism checks all pass under it.
`HL_REGION_TRACE=1` prints what each build's end let go and what is held, and `HL_REGION_LABELS=1`
which functions' answers hold the most.

A watcher's memory after a hundred edits of one module, before regions and with them (macOS
footprint; Linux resident set, from build 20 to build 101):

| App | Before: first build → 200 edits (macOS) | With regions, macOS | With regions, Linux |
|---|---|---|---|
| zod | 82 MB → 1,054 MB | 116 → 117 MB (200 edits) | 106.4 → 106.5 MB |
| three | 88 MB → 4,822 MB | 181 → 170 MB | 191.5 → 191.7 MB |
| 12 copies of zod | 888 MB → 11,264 MB | | 1,156.6 → 1,156.6 MB (60 edits) |

What it costs, on Linux (`tools/bench.py`, median of 7): a rebuild takes what it took (zod 4.2 ms,
three 26.5 ms, twelve copies of zod 40.8 ms); a watcher's first build retires 5–17% more
instructions and holds 11–16 MB more (twelve copies of zod: 126 MB), each answer's region having
memory to spare at its end; one-shot builds keep everything as before, three holding 11 MB more
(a list that grows is copied within a region where malloc grew it in place).

`tools/watch-check.py` checks every rebuild byte for byte against a fresh process, across edits to
a module, to the entry, a new file, a `package.json`, and a write that changes nothing.
`tools/hmr-check.py` runs a served bundle in Node and checks updates, reloads, kept state and
dispose data, and that all 15 test apps run the same in the development format as bundled.
A build error in `--watch` still ends the process.

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
names, `--external` (a package's subpaths with it, and `*` patterns; in ES module output each import
of one stays an import statement, as esbuild leaves it), `--platform=node`, identifier and syntax
minification, source maps, output to standard output when no path is given (its map inline), and
resolve, load, transform and optimize hooks.

## What it does not do

Being explicit, because "everything esbuild does" is a lot:

- **Not built:** CSS modules, CSS nesting and other CSS lowering, JavaScript
  (stage 3) decorators, `accessor` fields, `--keep-names`, `--inject`, `--mangle-props`, `--metafile`,
  and inlining enum values across files.
- **Hard errors for now:** `@import` with `layer()` or `supports()`, a media query on an import inside
  another, stylesheets with `--splitting`, `--legal-comments=inline`, `--jsx=preserve` with `--pretty`, a decorated class expression or `export default`
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

Everything written in the languages is under `src/`; everything in Coil under `compiler/`.

- `src/languages/`: the grammars of the languages themselves, and the `.rules` prelude.
- `src/bundle/`: the bundler, in those languages.
- `src/tools/`: the command-line `esb` and `jsparse`, and `ptest`, which checks that `parallel-map` gives the serial answer, in `.rules`.
- `src/app/`: a demo spec with six targets, a format, a loader and plugins; the program that offers
  it its steps (`build.rules`); and the pipeline.
- `compiler/hl/`: the languages' compilers. `syntax`, `rules`, `rewrite`, `facts`, `scopes`,
  and `pipeline` are readers; `rt` and `symtab` are their domain-free runtime;
  `grammars/` turns each grammar in `src/languages/` into its parser.
- `compiler/boot/`: five `main` functions, because a package's entry must be plain Coil.
- `tests/apps/`: the apps and fixtures the checks build; `tests/oracles/` the Node scripts that
  check outputs with acorn and esbuild. `tests/node_modules/` and `tests/test262/` are not checked in.
- `tools/`: building (`build-tools.sh`, `readers.sh`, `guard.py`), the checks (`verify.py`,
  `same.py`, `same-lowered.py`, `same-split.py`, `same-plans.py`), measuring (`altitude.py`, `bench.py`,
  `profile.sh`, `min.sh`, `formats.sh`, `go.sh`). Run them from the top; they work in `tests/`.
- `out/`: everything built: binaries, the reader artifact, the frozen baseline, the checks'
  outputs. Not checked in, but for `out/package.json`, which runs outputs as ES modules.

Coil issues found on the way are in the `coil-bugs` pad. Do not run `coil lint --fix` here with a
compiler older than the `reader-guest-spans` fix: it can overwrite DSL sources.
