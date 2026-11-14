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
├── report.facts     what a build made, and why: Datalog with        → the same, aggregates, and
│                    count, sum, min, max and !=                       explanations (why-REL)
├── paths.facts      how routes reach modules, for the page          → the same, with why-REL
├── html.syntax      HTML as the analysis page writes it             → printer, templates
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
npm ci --prefix benchmarks/heldout --ignore-scripts            # libraries it was never tuned on
python3 tools/heldout-sizes.py                                 # ... and the other tools/heldout-*.py
(cd tests && ../out/bin/spec)                                 # the build build.bundler describes
(cd tests && ../out/bin/spec other.bundler)                   # another spec, with the same steps
```

`tools/same.py` compares a new build with a frozen one, byte for byte, across 189 outputs. That is
how the code moved out of Coil without changing behaviour. It passes no `--target`, so
`tools/same-lowered.py NEW BASE` compares lowered output (57 cases, TypeScript included), against
the previous commit's build, and `tools/same-split.py NEW BASE` code splitting and stylesheet assets,
hashed file names and maps included.

## Configurable chunks and fragments

Chunk packing and placement granularity are independent choices:

```sh
out/bin/esb home.js admin.js --splitting --format=esm --outdir=out/site \
  --chunk-policy=balanced --fragments \
  --chunk-min-size=20000 --chunk-max-size=200000 \
  --chunk-max-requests=8 --chunk-request-cost=2000
```

The default is `exact` with whole modules. `exact` groups units by the entries/dynamic roots
that consume them. `package` further divides shared groups by npm package (or source directory).
`balanced` starts there, splits oversized groups between units, then merges adjacent groups using
size and request budgets. Request cost estimates the bytes worth spending to save a request;
only inert code may gain consumers. These are selectable policies, rather than replicas of any
particular bundler's algorithm. Size estimates use source spans, not compressed output. Budgets
are hints when a module, dependency cycle, or evaluation constraint is indivisible. A zero maximum
disables that limit. Size/request settings apply to `balanced`.

`--fragments` allows independent declarations in the same module to land in different chunks.
It uses existing parsed statements and linker facts; it does not reparse synthetic modules.
Each top-level statement is placed one of four ways (`fragments.rules`). *Deferred* statements
run nothing as they are defined: functions, inert values, imports that initialize nothing.
*Eager* ones compute as they are defined, but only what cannot be told apart wherever it runs:
calls and `new` the author marked `/*@__PURE__*/` (methods of them included, as in
`new Matrix3().set(…)`), classes whose heritage is a name, static blocks that only mark their
class (`this.prototype.isVector3 = true`), well-known symbol keys, names and constants.
*Attached* writes put such a value on a class or function the module declares
(`Object3D.DEFAULT_UP = new Vector3(0, 1, 0)`) and go with it. Anything else is an *effect*,
and stays in the module's initialization island, in source order.

What a statement runs is told apart from what it only refers to, as Turbopack does: defining
`const v = new Vector3()` runs Vector3's constructor, not its methods. A statement leaves the
island only when nothing could tell: no initialization before it reads it; an eager one reads
nothing defined after it, nothing still waiting for its module's initializer, and nothing that
initialization in its own module, or in one evaluated before it, may change (what it writes, calls
a method of, or hands on); an attached write's target is not run before the write. A statement
and the declarations of the names it assigns share a unit, since another chunk's import of a
name cannot be assigned. These are decided for the whole program at once and grown to a fixed
point. What a module that imports this one changes is not counted, as it ran after this module's
statements; for that to hold, a unit that computes as its chunk loads (an eager value, an attached
write) loads wherever its module is initialized, as well as where it is used, so it is never
computed later than the module was: loaded only after an `import()`, or by a second entry on the
page, it would see what ran in between change what it reads (`new W()` reading a global the first
entry set). Placed apart, a fragment depends only on what it reads; an import of its module still runs
that module's initializer. Consumers propagate through the resulting graph before packing.

So what fragments move between pages is code that runs nothing as it is defined: functions and
inert values. An immer page using only `produce` loads 11.5 KB rather than 18.1, a d3 page 43.0 KB
rather than 44.9, and of the libraries in `benchmarks/heldout`, a redux toolkit page 26.7 KB rather
than 43.8, a valibot page 3.5 KB rather than 5.1, a query-core page 3.1 KB rather than 4.8. On
three.js, three pages each using one part of it (math, a scene, loaders) load 484, 485 and 484 KB
minified, where whole modules load 485 KB for each (esbuild: 480 KB): what its pages do not share
is mostly values made as it loads (`const _v = /*@__PURE__*/ new Vector3()`), which stay with its
initialization. (They were placed with what uses them before 2026-11-12, for 292, 361 and 485 KB,
which was not sound.) zod, rxjs, date-fns and lodash-es are unchanged, as their pages need what
they share. Placing statements apart costs 9–16% more CPU on these builds
(`tools/fragments-real.py` measures, and runs every output against the unbundled source).
Dynamic scopes, `import.meta`, wrappers, duplicate declarations, module cycles and dependencies
that cannot be analyzed retain a whole-module boundary. Dependency cycles are condensed and
dynamic imports retain their lazy boundary. For bundled modules with observable evaluation,
chunks load definitions and once-only initializers; each entry then initializes its static
dependencies in source import order before running its body. This preserves different evaluation
orders for different entries, caches initialization errors per module, and lets unrelated entries
initialize after another entry fails. Top-level await propagates through static dependencies;
async evaluation tracks pending dependencies, async parents and cycle roots so suspended siblings,
parent microtasks and concurrent entry loads retain their evaluation constraints. A synchronous
`require()` of an async module graph is rejected; use `import()` instead. Pure leaf modules avoid
initializer wrappers.
With a single output, fragments do not reorder emission. Turn them off with `--fragments=false`.

The runtime build spec can choose both:

```text
bundler
target site
  entries "home.js" "admin.js"
  outdir "out/site"
  splitting
  format esm
  fragments on
  chunk-policy balanced
  chunk-min-size 20000
  chunk-max-size 200000
  chunk-max-requests 8
  chunk-request-cost 2000
end
```

Policies are ordinary `.rules` functions with type
`Fn([bundle.fragments.Unit], bundle.chunking.Limits) -> [bundle.chunking.Group]`.
A unit supplies its parts, source modules/path, consumers, byte estimate, portability and
evaluation-island marker.
A group supplies a unique key and unit IDs. Every unit must occur exactly once. The placement
engine validates ownership, rejects new consumers of nonportable code, and collapses chunk cycles.
A canonical consumer key puts a group in its entry facade; other keys create shared files.
See `src/app/chunk-policies.rules` for the `directories` example and `Steps.chunkers` in
`src/app/build.rules` for registration. Adding a policy needs no compiler or emitter changes.
The generic graph algorithms, fragment eligibility and built-in policies all live in `.rules`.

`python3 tools/chunking-check.py` checks policy/mode combinations and execution semantics.
`python3 tools/evaluation-check.py` compares original ESM and split outputs in both entry orders,
including conflicting import order, diamonds, cycles, lazy imports, cached errors, top-level
await, async-parent microtasks, pending async cycles and concurrent entry loads. All policies and
fragment modes are covered, with minification/source maps tested on the parallel pipeline.
`python3 tools/chunking-bench.py --baseline PATH --runs 7` compares time, CPU, memory and instructions
against a frozen binary on real libraries, many small modules, a large single module, and a
mixed module with classes, object literals and initialization effects.
The mixed-module fixture exercises classes, object configuration and an initialization effect.
Compare initial dependency-closure bytes as well as total output: fragments primarily avoid
loading declarations used by another entry. Ordered initialization adds runtime guards, so
size/performance measurements must include those guards. Results are recorded in the project pad.
Use `--baseline-fragments` when comparing against an older fragment-capable binary.
Use `--iterations 5` to amortize launch overhead and CPU timer resolution. Multi-output watch
and disk caching retain their existing CLI restriction; single-output caching accepts fragments.

## What a build says of itself

`--analyze=DIR` (in a spec, `analyze "DIR"`) writes what the build made, and why, as
`DIR/analysis.json`, what Turbopack's `next analyze` gathers; `esb --view=DIR` makes from it
`DIR/index.html`, a page to read it in. Keep a directory per build to compare them. The outputs
themselves are byte for byte those of the same build without it.

- **Outputs**: each file's size, the files it imports and loads with `import()`, and what of each
  module it holds, to the byte, and of that what the bundler wrote for it (its CommonJS wrapper,
  its namespace object); the rest is the file's own: imports and exports, the format's wrapper, the
  banner and footer, the legal comments gathered at its end, the line naming its source map.
- **Routes**: each entry and each `import()` root, the files it loads before it runs, their bytes,
  and how much of each module that is.
- **Modules**: size in the output and in the source; statements kept of all; what it imports; the
  modules whose kept code reads what it declares, and the names they read (`*` a whole namespace
  object, `()` what runs a module); the names it only passes on (a module with `export … from` and
  nothing else holds no code, but is how the code held is reached); and the statements kept only
  for what they do as the module loads, with their lines. On three.js's math page,
  `three.module.js`'s 163 KB is used by nothing, and kept by 13 such statements (`ShaderLib = {…}`).

The page has no script. A sidebar holds the routes and every package's modules, largest first.
Each route is a treemap of what it loads: packages, then their directories, then modules, every
area its bytes, laid out squarified (Bruls, Huizing and van Wijk) by a function of the view, in
whole hundredths of a percent; labels show where they fit (container queries). Under it, the
route's packages, each opening to its modules, and the files it loads, each said to be its own or
shared. The route shown is the one the address names (`:target`); its tab stands out by `:has`. A
module, in the map, the sidebar or anywhere it is named, opens its drawer over the side of the page
(HTML's `popover`), leaving the route where it is: its sizes, what keeps it (from each route, who
reads what, to it), who reads what of it, the import chain from each route, what it passes on, the
statements kept for what they do as it loads, and what it imports; chains alike but for their route
are one. A module named in a drawer opens its own over it, and closing it goes back. It is HTML
defined as a grammar (`src/bundle/html.syntax`), which gives its nodes, its printer and its
templates, and views written as templates over the analysis's records (`src/bundle/view.rules`); a
hole inside other text is an error, not printed as written. `--view` reads the JSON back into those
records with `read-json`, which the rules compiler derives from the type wanted, as it derives `json`
from the type written.

On Workbench (`examples/workbench.bundler` writes `out/workbench/analysis`, and `tools/workbench.py`
makes its page) the page says why the app loads 448 KB of zod for its schemas, 259 KB of it every
locale zod has. Each locale's drawer says what keeps it: every route runs `model.js`, which reads
`classic/external.js` all, as a namespace (`import { z } from "zod/v4"`), which reads
`locales/index.js` all, as a namespace, which reads `he_default`.

The analysis is stated as rules, `src/bundle/report.facts`: what each output holds of each module
is a sum over the stretches of its code the printer marked (`held(O, M, sum B) :- span(O, M, N, B)`),
what a root loads is what its output imports, and on (`loads`), what is used of a module and by
whom is a join over linking's parts (`used-by(M, R, S) :- …, M != R`), what a module passes on
follows what live code reads through re-exports (`passes`), and what is kept for its effects is
another. The report is records (`src/bundle/analyze.rules`), written as JSON by `json`. How a route
reaches a module, and what keeps it there, are worked out by the page, from the JSON, by rules of its
own (`src/bundle/paths.facts`: `reached`, and `needs(R, D) :- reads(D, M), needs(R, M)`), as the
explanations of rows: `.facts` answers `why-REL(db, …)` with the row's derivation, each row explained
only by rows derived before it, so in a recursion every step is one of the fewest.

The emitter gives each statement, and a few levels inside it, its module, and what it writes for a
module (a wrapper, a namespace object) the module and no place in it, which a source map leaves out;
the printer marks only where the output passes from one module's code to another's, or to what was
written for it (`render-files`), not every token as a source map does. The build pays only for the
data: `--analyze` costs 1.6–3.4% more CPU on zod, d3 and three.js, and 4.8% on rxjs, whose 226
CommonJS modules are a lot of analysis for a 50 ms build; the rest is the report's rules (about 1%),
copying linking's relations in, and the JSON. The page is made when it is looked at. A facts
database is passed to a function by reference, and its queries read it where it is: nothing copies
one but a binding that gives it a place of its own.
`tools/heldout-analyze.py` checks the same against two measurements made without it, on
fifteen libraries the bundler was never tuned on (`benchmarks/heldout`): esbuild's metafile
(`bytesInOutput`; the same modules, each module's share of its output within two points) and the
output's source map attributed byte by byte with Mozilla's `source-map` (each module within 0.5%,
up to the wrappers and namespace objects a map cannot say have no source).
`tools/analyze-check.py` checks the outputs are unchanged, every byte is attributed, each route
loads what its files import and its modules and files' own bytes add up to it, a module holds code
or passes names on, and what each module holds agrees with the same build's source map, up to what
has no source (a file's own bytes, and what the bundler wrote for a module, which a map gives to the
code before it); and the page has no script, a section for each route and a drawer for each module,
every link leads to a section and every button opens a drawer, every chain runs from routes to its
module, and each treemap's boxes fill it, overlap nowhere and are each as large as their bytes.

## Blame: which edit changed what a route loads

`--ledger` (with `--analyze=DIR`; in a spec, `ledger`) writes `DIR/ledger.json` beside the
analysis: every statement the build placed, what of each statement each route loads to the byte,
and every fact linking stated, in the blocks the build gave them (`src/bundle/ledger.rules`).
Linking numbers modules, statements, symbols and names in the order it meets them, so its numbers
mean nothing outside the build that made them. The ledger says each by name instead: a module by
its path, a statement by its module, its kind and what it declares (or a print of its text when it
declares nothing), a symbol by its module and name. Two ledgers made by different processes, from
different checkouts, then speak of the same things in the same words. A statement's bytes come
from the printer's marks, the ones a source map is made from, so `--ledger` prints with them.

`esb --blame=BASE,HEAD` (`--blame-json`) compares two such directories (`src/bundle/blame.rules`).
Both builds' facts are solved again by `link.facts` itself, in one database's numbers. A statement
a route loads after and not before was gained, and one it loaded before and not after was lost.
Which edit did it is decided by counterfactuals, not guessed. An edit is a module whose facts or
`import()`s changed: its source, or what it is given, such as a package's `sideEffects`. The
earlier build's facts, with one edit's swapped for the later build's, are solved again. A statement
the route then reaches, and did not before, was gained by that edit **alone**; when several edits
each would gain it, by **any** of them. What no edit gains alone, edits gain **together**: which,
found by leaving each edit out in turn while the statement is still gained. A loss is the same the
other way. Other changes are put down to other causes:

- A statement in the route before and after, at another size, was **edited in place**, or else
  changed by renaming and minifying around it.
- A statement the earlier build reached already was **placed** elsewhere: chunking or packing moved it.
- What no statement holds belongs to the outputs: their imports, exports and wrappers.

Each route's groups add up to what it changed by. Each group's largest statement is explained:
the chain that reaches it (`why-reaches`, or `why-active-part` without splitting), and the facts
on that chain that the edit made, or took away. A module only the later build has is no edit of
its own: it comes with whatever imports it. With splitting, the roots are worked out again for each
counterfactual, from what the entries reach by imports and `import()`. A module that stops being
`import()`ed loses its route to the edit that stopped it, not to "the entries". On the zod
fixture (`tests/apps/blame/zod`, `import { object, string }` made `import { z }` read whole):

```
route main.js: 85335 -> 455332 bytes (+369997)
   +369607  edit to main.js
        +29309  zod/v4/core/compile.js (81 parts)
        ...
      reached so:
        main.js:3  User = schemas.object({ name: schemas.string().min(2) });
        -> schemas in main.js:2  schemas = z;
        -> external_exports in zod/v4/classic/external.js (its namespace object)
        -> locales_exports in zod/v4/locales/index.js (its namespace object)
        -> he_default in zod/v4/locales/he.js:217  function () {
      made: main.js imports z from zod/v4/index.js
      +392  renaming and minifying around what changed
```

`--watch --ledger` prints the same after each rebuild, against the build before it.

`esb --what-if=DIR` (`--what-if-json`) asks the other question of one build: which edits would
save each route the most. Each edit is tried by solving the build's facts again without what the
edit takes away, and each number is linking's answer, counted at the sizes this build printed. The
edits it tries are these:

- a statement kept for what it does as it loads, had it no side effects;
- a module, had none of its statements any;
- a package that says it has none (`"sideEffects": false`);
- a namespace object, had nothing read it whole, with the chain that does;
- a name a namespace object holds, had its module not exported it.

On zod read whole it finds −260,619 bytes if nothing read `zod/v4/locales/index.js` whole, and the
chain `schemas = z` → `external.js`'s namespace object → the locales'. On three.js it finds
−168,033 bytes if none of `three.module.js`'s 13 load-time statements had side effects, the 13
statements `--analyze` showed by hand. The edits are a stage of the pipeline (`stage what-if`), so a
plan tries them on many threads. Workbench's 445 edits take 4.3 s on one thread and 0.58 s with
`--pipeline=full`, and say the same.

What the facts language gained for this knows nothing of bundling: a database's schema as values
(`relation-names`, `relation-columns`, `relation-given?`, `relation-arity`) and facts as values
(`fact-values`, `fact-of`). So a program can carry any fact without naming its relation, and a
ledger made by a bundler whose linking states other facts is refused, not misread.

The outputs and `analysis.json` are byte for byte those of the same build without `--ledger`.
`--ledger` costs 13–19 ms more than `--analyze` alone (interleaved medians, `-O3`):

| App | `--analyze` | with `--ledger` |
|---|---|---|
| zod | 55 ms | 71 ms |
| three | 101 ms | 120 ms |
| d3 | 63 ms | 81 ms |
| rxjs | 38 ms | 51 ms |

A ledger is about 1 MB for zod's 90 KB output, and 3.2 MB for Workbench. Blaming zod takes 0.1 s.

`tools/blame-check.py`, part of `tools/verify.py`, checks blame and what-if against builds, not
against themselves:

- **Identity:** a build blamed against itself changes nothing.
- **Accounting:** each route's groups add up to its change, both ways.
- **Duality:** blamed backwards, every cause moves the same bytes the other way. What edits gained
  only together, any one of them undoes.
- **Counterfactual trees:** for each edit blame says acts alone (or as any one of several), the
  earlier tree with only that file taken from the later is built, and every module blame names
  gained or lost bytes in that route.
- **What-if edits:** `"sideEffects": false` and `/* @__PURE__ */` are made to a copy of a fixture,
  and the modules what-if said would go are gone.
- **Plans and watching:** the answers are the same under `--pipeline=full`, and a watched rebuild
  prints its blame.

Limits:

- An edit is a whole module. Which statements of it matter shows in the chain and in the facts it
  made.
- A statement that declares nothing is known by its text, so editing it is one statement lost and
  another gained, both put down to the edit.
- A counterfactual tree may be one the bundler refuses (an import of a name not yet exported).
  Linking's rules still answer for it, and `blame-check.py` says how many such trees it met.
- Sets of edits found together are ones none can be left out of, not always the smallest.
- What-if does not try making an import lazy, which would change the roots, not only the facts.
- Stylesheets are not in the ledger.

## Lints over what ships

`--lint=FILE` (in a spec, `lint "FILE"`) runs rules over what the build ships. The rules file is
a project's own `.lint`, read when the build runs, as a spec is; changing it needs no new bundler.
Rules are Datalog with negation, comparisons, tests of text (`starts-with`, `ends-with`,
`contains`) and `count`, `sum`, `min` and `max`. JavaScript patterns are atoms:
`code(P, `process.env.$N`)` holds for every statement `P` with code the pattern matches, and binds
`N`. The relations are the build's own (`esb --lint-relations` lists them, `src/bundle/shipped.rules`
gives them):

- what each route ships and to the byte (`ships`, `bytes`, `route-bytes`);
- what it needs, from its root, by what statements read (`reaches`);
- what each statement needs, in its module or through an import (`needs`), and what it reads of
  other modules, by name or whole (`reads`, `reads-whole`);
- what stays for its side effects (`effect`), and what is in the output (`live`);
- modules, packages and the copy each comes from, imports, `import()`s, exports, and the project's
  dependencies.

They are what linking and tree shaking decided, not the import graph of the source, so an import
nothing uses is no finding, and code that ships through a re-export is.

```
public-prefix("PUBLIC_");
env-read(P, N) :- code(P, `process.env.$N`) ;
public(N) :- env-read(_, N), public-prefix(X), starts-with(N, X) ;
lint secret-shipped error at P "process.env.{N} is in code {R} sends to the browser" :-
  platform("browser"), ships(R, P), env-read(P, N), !public(N) ;
```

A finding says where it is and why, row by row. Each row was made by rows that came before it, so
an explanation ends. For a route that ships a statement, the explanation goes on into linking's own
chain from the route's root:

```
src/config.js:1: error [secret-shipped] process.env.STRIPE_SECRET is in code src/main.js sends to the browser
    export const config = {
  because
    platform(browser)
    ships(src/main.js, src/config.js:1)
      src/main.js:6  render(config, label("main"));
      -> config in src/config.js:1  export const config = {
    env-read(src/config.js:1, STRIPE_SECRET)
      `process.env.$N` at src/config.js:2, STRIPE_SECRET
    no public(STRIPE_SECRET)
```

An error stops the build before it writes anything. Warnings are said beside what it writes. While
watching, both are said after each build and the watcher goes on, and the rules file is watched as
any input is (`keep bundle.lint/file-program`). Lints change nothing a build writes.

`examples/ship.lint` is a library of such rules:

- **Secrets:** `process.env` reads, not public, in what a browser route ships.
- **Left from debugging:** `debugger` statements, and the project's own `console.log`s.
- **Layering:** what `src/ui` needs, at any distance, must not be `src/db`'s.
- **Budgets:** per route, and per package in a route.
- **Packages:** a package shipped in two copies, with the chain that ships each; dependencies of
  which nothing ships; the project reading a package's module whole.
- **At load:** I/O in code that may run as its module loads.
- **Splitting:** an `import()` whose module the entry ships anyway.
- **Exports:** the project's exports that nothing shipped reads.
- **Kept only for side effects:** a package's statements that ship only because they run as their
  module loads, and all only they need. On three.js it finds three.module.js keeping 171,467
  bytes for 13 such statements, what the analysis's page showed by hand.

The rules are checked before anything is solved, each error at its place in the file:

- every relation named is the build's or derived by a rule, at its arity;
- every variable is bound;
- nothing is negated or aggregated through recursion;
- every pattern is one js.syntax reads;
- no rule adds to what the build gives;
- every name a message uses is bound.

Literals are solved in the order written, each test as soon as what it tests is bound. A variable
of a negated atom that nothing else binds stands for any value.

The engine (`src/bundle/lint.rules`) solves stratum by stratum, semi-naively: each round joins only
what the last added. It indexes what a stratum reads of those below once for all its rounds, and
explains from indexes of the final rows. The whole library adds about 80 ms to zod's build and
110 ms to three.js's at `-O1`.

`tools/lint-check.py`, part of `tools/verify.py`, checks:

- the fixture `tests/apps/lint`'s findings, exactly, and their explanations;
- that lints change no output;
- each kind of rule error;
- watching, and a spec's `lint`;
- the library over real libraries, which finds no error.

Limits:

- `needs` is reading, not calling, so a rule about what runs says "may".
- A pattern matches the source as parsed (before defines and minifying), node for node: `$X` is
  anything, and `$$X` the rest of a list. A pattern holds no backquote.
- A statement is a top-level one: a pattern's match inside a function is that function's
  statement.
- Values are text, compared as numbers only by `<`, `<=`, `>` and `>=`.
- An aggregate's explanation shows the first five rows it counted.
- Dependencies are read from the `package.json` where the build runs.
- Stylesheets are not in the relations.

## Rewrites and fixes

The same files hold rewrites, `rewrite NAME `pattern` => `template` [:- conditions] ;`, made with
`--rewrite=FILE` (in a spec, `rewrite "FILE"`) to each module's code as it loads
(`src/bundle/rewrites.rules`):

```
rewrite no-get `$G($O, $K)` => `$O?.[$K]` :- imported(G, "tiny-get", "get") ;
rewrite no-asserts `$A($$X)` => `` :- imported(A, "./assert.js", "assert") ;
off("beta");
rewrite flags-off `$Fl.$F` => `false` :- imported(Fl, "./flags.js", "flags"), off(F) ;
```

They are made before scopes and linking, where a spec's `transform` is. So tree shaking, renaming,
minifying and source maps all see what they make:

- an `assert` taken out takes its module with it;
- `get(o, k)` written `o?.[k]` stops shipping the package;
- with `--minify-syntax`, a flag rewritten `false` takes its branch out before tree shaking, as a
  constant's does, and with it what only that branch read.

On `tests/apps/rewrite` the three rules take the build from 523 bytes to 135. A tree is rewritten
from its leaves up: each node, its children rewritten first, by the first rewrite that holds. What
a rewrite makes is not rewritten again, so rewrites cannot loop. An empty template takes out a
statement, or the expression statement whose expression it matched. Every node a template makes
is placed where the code it replaced was, so a source map still says where the code came from.

A rewrite's conditions read what the names its pattern matched are in their module, as the
module's own scope analysis says:

- `imported(X, Spec, Name)`: X is an import (`Name` is the name imported, `default` or `*`);
- `global(X)`: no declaration of the module's is X;
- `local(X)`: X is declared in the module;
- `in-module(M)`, `in-package(K)`: where the code is;
- and what the file's own facts derive.

So a function of the module's own called `get` is not the import. What a build ships is not a
rewrite's to read, since rewriting changes it; reading `ships` in a rewrite is an error at its place,
as are a template variable the pattern binds nowhere and a pattern js.syntax cannot read. Rewrite
files are watched inputs, as rule files are. `examples/rewrites.lint` has these and a
`console.log` rewrite that keeps a module's own `console`.

A lint may have fixes, `fix LINT `pattern` => `template` ;`. `--fix` makes them to the source
files instead of building. In the statement each finding of the lint is at, what the pattern
matches becomes the template, filled with the code each variable matched as it is written. An
empty template takes the statement out, and its line when the statement was all of it. A package's
files are not the project's to fix. `examples/ship.lint` fixes its `debugger` and `console.log`
findings so.

`tools/rewrite-check.py`, part of `tools/verify.py`, checks:

- the fixture's output, and that it prints what it printed;
- a source map through a rewrite;
- each kind of rule error;
- watching, and a spec's `rewrite`;
- that `--fix` edits only what it should (whole lines, a filled template, no package files), and
  that linting again finds what was fixed gone.

## What an object holds, read by name

Bundlers drop what nothing reads statement by statement and export by export. An object, once
read, ships whole. esbuild, Rollup 4 and this bundler before this all kept every property of:

- `export const Utils = { clamp, lerp, … }` read as `Utils.clamp`;
- `export default { parse, stringify }` read as `csv.parse`;
- a namespace read through a `const` alias (`const api = ns; api.alpha()`).

All but Rollup also kept everything of a destructured namespace (`const { alpha } = ns`).

Linking now follows such objects in `link.facts`. Two kinds of object qualify:

- **Object literals:** one a top-level `const` (or `export default`) gives a name, with no spread,
  computed key, `__proto__`, repeated key, `this` or `super`.
- **Namespace objects** reached through `const` aliases (`api`), through imports and re-exports of
  those, and through simple destructuring.

The rules:

- **Read whole:** an object is read whole when it is named as a value, here or through an import;
  when it is read as another namespace's export or with a name that tells more than one property
  (`hasOwnProperty` and its kind); when it is exported from an entry or written through; or when
  anything else reads it.
- **Kept properties:** a property is kept when its object is read whole, or when a live statement
  reads it by name (`O.k`, here or through an import or an alias). What a kept property reads is
  read by its statement, so its dependencies stay too.
- **Which properties may go:** only those that can go unread (`pure?`) and read only names. A
  property whose value does something as it loads, or reads a namespace member, always stays.

The declaring statement is still one part. Each property's reads are found by the statement's own
summary walk run on its value; emit prints only the kept properties; and destructuring of a
namespace object is printed as one declarator per name, each the export itself. The relations
`object`, `object-read-whole` and `prop-kept` let lints say why an object ships whole, and
`examples/ship.lint` has a rule that points at the project's statement keeping a package's object
whole.

On the apps, with output the same:

| App | before | after | change |
|---|---|---|---|
| three (math only) | 263,187 | 139,590 | −47% |
| date-fns | 23,098 | 22,896 | −0.9% |
| all of lodash-es | 93,389 | 93,195 | −0.2% |
| zod read through `const schemas = z; schemas.object(…)` | 455,332 | 85,353 | −81% |

Most of three's comes from `ShaderChunk`, an object of about 150 GLSL strings of which the
`ShaderLib` entries this app keeps name 34, and from `MathUtils`, of which it reads `clamp`. An
app that renders reads `ShaderChunk[name]` and keeps it whole. The held-out libraries, whose
exercisers call nearly every export, change by under 1%.

It costs about 1.5–2% of a cold build where nothing is shaken (zod, d3, lodash-es), and three's is
faster for printing less. `--property-shaking=false` (in a spec, `property-shaking off`) turns it
off. Its output is byte for byte the earlier bundler's across all 189 of `tools/same.py`'s outputs,
which is how verify's identity checks against esbuild run.

`tools/shake-check.py`, part of `tools/verify.py`, builds each case in `tests/apps/shake` with us
and with esbuild and runs both. It checks what goes (exports through destructuring and aliases,
literals' and default objects' properties and what only those read) and what escapes and stays
whole (`Object.keys`, `for in`, spread, `hasOwnProperty`, passing the object on, reading it through
a namespace, `this` in a method, a property that does something as it loads). It also checks a split
build where two routes read different properties, one statement reading a property by name and the
object whole through a namespace alias, and a write through a namespace alias, which throws as
writing the namespace does: emit never makes a member that is written into a write to the export's
binding. The held-out exercisers' calls and `tools/correctness-check.py` pass with it on.

`tools/shake-fuzz.py COUNT SEED` writes random programs of a few modules. Their objects' properties
are methods, arrows, values, shorthands, getters, nested objects, properties that do something as
they load, properties that read their own object or another, and methods that use `this`. The
programs reach those objects:

- through imports, `export … from`, `export *`, default exports, namespaces, `const` aliases (chains
  of them), destructuring, `require` and `import()`;
- and every way an object escapes: `Object.keys`, `for in`, spread, `in`, `hasOwnProperty`, `?.`,
  `o[k]`, passing it on, writing, deleting, freezing.

Some programs are split into two entries. Each is built with shaking on, with it off, and by
esbuild, and run. On and off must print the same, or the run fails and keeps the program; one where
ours and esbuild differ is counted apart, as shaking did not do it.

## Paired client/server builds

A target with `client-outfile` builds one server entry and discovers browser entries from its
`"use client"` boundaries. The server gets callable-guarded references to those modules' exports;
the browser gets their implementations and a `resolveClientReference` export. Dependencies below
a client boundary belong to the browser graph without needing their own directive. Shared source
can be compiled into both environments, each with its own package resolution conditions.

```
bundler
target app
  entry "src/server.js"
  outfile "dist/server.cjs"
  client-outfile "dist/client.mjs"
  client-manifest "dist/manifest.json"
end
```

The server output is CommonJS, the browser output ESM; `client-manifest` defaults to
`client-outfile` plus `.manifest.json`. The manifest records module IDs (paths relative to the
build's working directory), exported names and the browser output file. A server reference
serializes as `{ "module": "src/Counter.jsx", "export": "default" }`; the browser's
`resolveClientReference` returns the corresponding implementation. Calling that reference on
the server throws. All exports of a boundary are retained in the browser registry, including
named/default exports and static re-exports; opaque CommonJS boundaries and dynamic export-star
boundaries are rejected.

`import "server-only"` and `import "client-only"` declare environment restrictions. The build
checks the source dependency graphs before writing either bundle, including unused imports,
and reports the import chain for a violation. Node builtins are also server-only. A client-only
module may be imported by the server through a `"use client"` boundary, where it is a reference.
The marker imports do not require installed packages. External modules are not inspected.

The policy is `src/bundle/boundaries.facts`; `boundaries.rules` uses the existing loader, linker,
hooks and emitter to make the paired outputs. Client dependencies resolve with browser/import
conditions; the server defaults to Node conditions, which explicit target settings can override.
The generic compiler contains no execution-environment policy.

Run the interactive React counter demo:

```sh
python3 tools/client-server-demo.py --serve
# Open http://127.0.0.1:8000
```

Its server entry imports a database module and a client component. The database supplies the
initial counter value; the server serializes client references into `model.json`; the browser
resolves one and mounts the real React counter. `tools/boundary-check.py` checks the paired build,
separation, reference handoff, conditions and invalid imports, and is part of `tools/verify.py`.
The demo serves only its `public/` output directory; the server bundle stays outside that directory.

This implements the module-graph boundary used by a Next-style split, with a small JSON reference
handoff for the demo. It does not implement React Flight, server rendering/hydration, server
actions (`"use server"` is an error), routing or paired-build watch/HMR. One browser bundle is
emitted for all boundaries; paired builds do not combine with code splitting yet. It is a build
graph check, not a sandbox for runtime filesystem/network access or nonliteral dynamic imports.

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
| lodash-es, tree-shaken | 35,541 | 35,207 | +0.9% |
| all of lodash-es | 93,384 | 92,958 | +0.5% |
| lodash (CommonJS) | 74,453 | 74,092 | +0.5% |
| three | 262,779 | 258,124 | +1.8% |
| zod | 456,977 | 454,182 | +0.6% |
| rxjs | 17,655 | 17,510 | +0.8% |
| date-fns | 23,250 | 22,915 | +1.5% |
| preact | 11,047 | 11,045 | +0.0% |
| immer | 9,566 | 9,431 | +1.4% |
| react + react-dom/server | 218,404 | 216,850 | +0.7% |
| d3 | 46,341 | 46,294 | +0.1% |
| features test app (small) | 2,578 | 2,520 | +2.3% |
| re-exports test app (small) | 1,342 | 1,357 | -1.1% |

**Libraries it was never tuned on** (`benchmarks/heldout`, `tools/heldout-sizes.py`), minified, ES
module output: every bundle prints what esbuild's prints (lit needs a DOM, and fails as esbuild's
does). Median +0.5% bytes, +0.5% gzipped.

| Library | Ours (bytes) | esbuild | Difference | gzip |
|---|---|---|---|---|
| chart.js 4.6.1 | 207,194 | 206,273 | +0.4% | +0.0% |
| dayjs 1.11.23 (and three plugins) | 16,638 | 16,641 | -0.0% | -1.2% |
| immutable 5.1.10 | 68,416 | 66,501 | +2.9% | +1.2% |
| jquery 4.0.0 | 80,308 | 79,990 | +0.4% | +0.2% |
| lit-html 3.3 | 8,289 | 8,295 | -0.1% | +0.5% |
| marked 18.2.0 | 50,089 | 50,123 | -0.1% | -0.1% |
| mobx 7.1.6 | 45,980 | 45,177 | +1.8% | +1.8% |
| moment 2.31.0 | 64,170 | 64,222 | -0.1% | -0.3% |
| @tanstack/query-core 5.107.1 | 25,539 | 25,247 | +1.2% | +0.9% |
| ramda 0.32.0 | 59,212 | 58,668 | +0.9% | +0.5% |
| @reduxjs/toolkit 2.14.0 | 30,858 | 30,172 | +2.3% | +1.6% |
| solid-js 1.9.19 | 12,192 | 12,049 | +1.2% | +1.0% |
| valibot 1.5.0 | 5,491 | 5,479 | +0.2% | +0.2% |
| vue 3.5.45 | 69,126 | 67,090 | +3.0% | +2.3% |
| yup 1.7.1 | 42,717 | 42,488 | +0.5% | +0.5% |

Three gaps found this way are closed: mobx was +28.8% (its `__DEV__` flag, a `const`, was not
written in, so its development messages stayed), query-core +8.8% (private names were not
minified), and redux toolkit resolved another file than esbuild (the `module` condition).
`tools/heldout-exercise.py` calls every export of ramda, valibot, immutable, yup and mobx on the
exerciser's matrix, about 262,000 calls: ours prints what esbuild's prints, plain and minified.
Writing in constants is a pass over each file of its own, where esbuild does it as it parses: it
costs 2–6% more instructions on a minified build (three 5.8%, d3 4.2%, zod 2.5%, date-fns 1.8%),
and nothing on one that is not. Checking every write against what the language forbids
(`src/bundle/writes.rules`) is another pass over each file: 2–3% more instructions on any build
(zod 2.0%, three 3.3%, d3 3.3%).

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

How the build divides its work is a language of its own, and the rules that do the work say
nothing of it. `src/app/build.pipeline` names the stages that work on one file, module, unit or
chunk at a time, the functions each runs, and plans:

```
stage load     per file bundle.modules/led-ahead ...
               reads files
               also bundle.modules/parsed-of bundle.modules/loaded
stage pieces   per piece bundle.jspieces/piece
               alone bundle.jspieces/cut is bundle.jspieces/uncut
               inside bundle.scopes
stage early    per 512 statements bundle.early/part-found
stage resolve  per 64 requests bundle.modules/target-of
stage facts    per module bundle.analysis/summaries-of bundle.analysis/module-link ...
stage gather   per module bundle.analysis/module-facts-at bundle.analysis/binding-facts-at
               names by bundle.modules/name-id
stage chunks   per chunk bundle.api/chunk-at
               gives settings
stage link     whole    bundle.analysis/link

plan full
  threads auto
  load parallel
  pieces parallel
  facts parallel
  chunks parallel 6
end
```

Where the rules make a list of one of a `per` stage's functions' answers, that list is the
stage's work:

```
fn link(symbols: Int) -> Linked = linked-of([module-link(id) for id in m.order], symbols)
```

The rules compiler has it made on as many threads as the run's plan gives the stage, the answers
in the list's order. What each call is given is worked out first, by the thread that asks for the
list; then each thread takes the next item it finds free. A stage also says what its work needs:
`gives settings` (its functions give settings by `with`, so one runs at a time while answers are
tracked), `names by F` (its functions meet names that get ids in the order met, so the list is
made once to find the names, F is given them in order, and it is made again), `per N units` (its
units are small: a thread takes N at a time, and a list of N or fewer is made by whoever asks),
`reads files` (the names a walk reaches are files to read ahead), `alone F is G` (the rules give
two ways to one answer, and on one thread the undivided one answers; the test suite builds both
and compares), `inside M` (a language module, such as a scopes definition, divides what it is
given itself, as this stage's work) and `also F` (functions its threads make on the way). A
stage's work with no list anywhere in the rules does not compile. Sizes the rules cut work by are
given beside the plans, `size bundle.jspieces/piece-bytes 8192`; a plan may give its own, and so
may a run, `--size:bundle.jspieces/piece-bytes=16384`, with no rebuild. The suite checks that no
size changes what a build makes. `HL_SHOW_STAGES=1` set
while compiling prints every list that is a stage's work, and where it is.

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
- `reach(roots, f)`: how many names can be reached from `roots`, where `f`, a stage's function,
  says what each leads to. Each name is given to `f` once, on whichever of the stage's threads
  takes it; a thread that finds work waiting never waits for a wave to finish. Loading is this:
  `reach(roots, led-ahead)`.
- A list inside a stage's work that is another stage's (a big file's pieces, a file's many
  imports) is offered to the other threads, who take part before they take anything new.
- `arrive!(key, n)`: of `n` items, the last to finish is told so and goes on, so no worker waits
  for the others.

The runtime has a pool of parked workers, and a work queue that idle workers sleep on.

**Big files.** The bundler's rules parse a file, check it and analyse its scopes, and say nothing
of its size. A big plain-JavaScript text is parsed in pieces by a module of the JavaScript
language, `bundle.jspieces`: a piece starts at a top-level declaration, found by a scan of the
bytes; a wrong guess only means a piece is no program by itself, and then the text is parsed
whole. Its early errors are a list, a check of each statement, with what concerns the statements
together checked of the program. Its scopes are analysed in parts by the scopes definition itself
(`inside bundle.scopes` on the `pieces` stage): the program's own names are declared, each run of
statements is walked in a table of its own, and the tables are grafted back in order, giving the
same symbol and scope ids a single walk would. On one thread nothing is cut.

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
`--pipeline=NAME` picks a plan, and `--threads=N` runs on N threads every stage the pipeline checker shows writes no shared state (any other on one).

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
  level is named stem by stem, the stems in 64 buckets (`nm.bucket-named`). A small database of
  its own (`stems.facts`, of the modules in the output only) says which modules claim or reserve
  names of each stem, brought up to date as linking's is; modules keep ranks in the program's order
  while the order around them does (`rt.Ranks`), so adding a module renumbers nothing. Each module
  in the output has its block named on its own (its claims' names, its nested scopes'); a module
  left out keeps its block as placed. The output's names are a table joined from those.

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
| zod (96 modules) | 2.0 ms | 14.9 ms | 15.1 ms | 96 ms / 29 ms |
| date-fns | 2.7 ms | 14.8 ms | 12.6 ms | 57 ms / 31 ms |
| rx (225 modules) | 3.6 ms | 12.0 ms | 12.5 ms | 53 ms / 29 ms |
| three | 26.5 ms | 54.6 ms | not observable (the package says it has no side effects, and dev never serves the edit) | 141 ms / 71 ms |
| 12 copies of zod | 24.4 ms | 81.6 ms | 20.9 ms | 910 ms / 115 ms |

What it costs elsewhere, against the build before (instructions, which load does not move): a
one-shot build 1–5% more, a watcher's first build 3–8% more (zod's makes 2,618 answers against
2,165), a cold cache 2–7% more; a run from a warm cache with one edit about the same or less
(twelve copies of zod 2.53 → 2.37 G). For twelve copies of zod a rebuild went from 40.6 to 24.4 ms;
what it spends now is mostly parsing the edited file again (about 10 ms) and printing (about 10 ms).

`--hmr` watches too, writing a development format: no scope hoisting or renaming, each module a
function registered with `hmr_runtime.js` by path, its imports read through live namespace objects
(`hmr.attrs`, 170 lines without comments). `--serve=PORT` serves the output's directory and an
event stream at `/hmr`, from a thread in `hl.rt`. The `.rules` caller chooses that event path;
the runtime serves events at the path it is given. `tools/serve-check.py` checks a different path
without bundler code. After each rebuild the modules whose functions
changed are sent; `hmr.facts` (Datalog, 4 rules) finds which modules run again, stopping at those
that call `import.meta.hot.accept()`, and reloads when an entry that does not accept changed.
`import.meta.hot.dispose` and `hot.data` carry state across a replacement.

### Patching statements in place

Most edits don't re-run a module at all. If an edit changes only a function, an inert value (a
literal, an arrow function, an object of them), or a class's methods, `--hmr` sends a patch. The
patch gives those names their new values inside the running module, so the module keeps its state:
its counters, caches, singletons and open connections. Other modules see the change straight away,
because they read imports through live namespaces. A class keeps its identity. Its new methods go
onto the class that already exists (`super` still resolves as before), so the instances it already
made use them. A function the edit adds goes into the patch's own scope. A function the edit removes
is fine as long as nothing still names it. `--hmr-patch=false` turns patching off: each changed
module runs again, as one that cannot be patched does, saying so (`runs again: patching is off`),
and no module's function hands the runtime an evaluator of its scope.

```
[hmr] apps/hmrpatch/counter.js: patched bump
[hmr] apps/hmrpatch/shapes.js: patched Counter.prototype.inc
[hmr] apps/hmrpatch/store.js runs again: statement 3 (`export const store = createStore(reducer);`) captured `reducer` when it ran, and the edit changed it
[hmr] apps/hmrpatch/store.js runs again: statement 6 (`export const initial = start();`) ran `start` when it ran, and the edit changed `base`
[hmr] three.core.js runs again: statement 258 (`const MathUtils = {`) captured `clamp` when it ran, and the edit changed it
```

A patch is only sent when it gives the same result as running the module again would have, apart
from the state it keeps. Otherwise the module runs again, as before, and the client is told which
statement made that necessary. Two kinds of facts make the decision.

**What changed** is worked out per module by comparing the two builds statement by statement
(`plan-of` in `hmr.attrs`). A statement's role depends on whether it runs anything when defined,
using the same test fragments use (`evaluation.rules`' `inert-stmt`):

- *Declares*: a function, or an inert value. A patch can give it a new value.
- *Methods*: a class. A patch can replace its methods.
- *Runs*: anything else. It already ran when the module loaded, and can't be undone.

If a Runs statement changes, appears or disappears, the module runs again. It also runs again if:

- its imports changed;
- it accepts its own updates (its author asked for a re-run);
- it is CommonJS;
- a class's constructor, fields, heritage or static members changed;
- a class whose methods changed has private names, which the new methods could not reach on old
  instances;
- a removed name is still mentioned somewhere;
- a Runs statement mentions a name the edit adds.

**What already ran with the old value** is Datalog (`hmr.facts`), fed from the shape the
development format already computes for each module. For each statement that ran, the facts record
what it read, what it called or constructed, and which properties it used by name. For each
function, class constructor and method, they record the same about its code. `provides` follows
exports through `export … from` and `export *`. `spoiled` holds every name whose code, if run now,
would read or call something the patch changes. `stale` holds every statement that read a changed
name as it ran (it *captured* the old value), or ran spoiled code. A module with a stale statement,
in any module, runs again, and the usual rules then decide whether that propagates up to a module
that accepts updates or to a page reload. `why-stale` gives the derivation, and the client's note
prints it as the chain of code the statement ran.

What counts as "ran" follows fragments' rule: a function passed as a value (`render(App)`,
`addEventListener("click", f)`) has not run, but a call has. A function called where it is written
counts as run, and so does one passed to an array method that calls it immediately (`forEach`,
`map`, …). `x.m()` and `x.m` may run any method or getter named `m` on any class.

To patch, each ES module's function first gives the runtime an evaluator for its own scope
(`(c) => eval(c)`). A patch is code evaluated there, so its assignments reach the module's own
bindings. Each patch returns the evaluator for the scope it created, so a function it added is
visible to later patches. It then gives the module's namespace its exports again. A patch that
throws reloads the page.

Limits:

- A getter or method reached through a computed key (`x[k]`) is not counted as run.
- A function value captured inside another value, and called later, keeps the old code.
- What a stored callback did before the edit stays as it was. The page shows old output until
  something calls the code again.
- Modules that accept their own updates are always re-run, never patched.

`tools/hmr-check.py` checks each of these behaviours on `tests/apps/hmrpatch`. On every edit it also
checks that nothing that should have kept running ran again, and that the bundle the watcher wrote
matches a fresh build.

What it costs: each module's statements are now analysed and printed one at a time, and every
update solves the facts for the whole graph. On three.js (`three.module.js` and `three.core.js`,
1.1 MB, -O3, macOS, interleaved with the build before), a development build's first run goes from
about 61 to about 90 ms. An edit to a `Vector3` method goes from about 40 ms, which ended in a
reload, to about 62 ms, which ends in a patch. On the small apps the check uses, an update takes
0.5 ms either way. Normal bundles are unchanged: `tools/same.py` finds all 189 outputs byte for
byte the same.

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
A build error in `--watch` still ends the process. Split builds can be watched and cached;
HMR remains a single-entry development format.

## Application acceptance and larger graphs

`examples/workbench.bundler` builds a React project-management application and its Node API.
Overview, projects and D3 reports are lazy routes, with separate stylesheets. The application
uses shared Zod schemas, date-fns, package self-references and `#imports`, JSON data, text, SVG
images and CSS background assets. Create and complete projects, filter/search them, switch
between routes and change the theme. The API serializes mutations and saves JSON through an
atomic rename. It is an acceptance application: authentication, authorization and a multi-user
database service are outside this fixture.

```sh
python3 tools/workbench.py --serve       # builds the spec, serves at http://127.0.0.1:8000
node tools/workbench-check.mjs           # actual Chrome: routes, CRUD, assets, persisted restart
node tools/assets-check.mjs              # policies × modules/fragments, lazy CSS failure/retry
python3 tools/resolution-check.py        # Node/esbuild resolution differential checks
python3 tools/multi-output-check.py      # split JS/CSS/assets: cold/warm cache and watched edits
python3 tools/scale-check.py             # 10,160 source modules, 32 entries, native-output oracle
```

Browser checks use the installed macOS Chrome, or the executable in `CHROME`. They require
`npm ci` in `tests/` for playwright-core; no browser download is needed. Build the native tools
first as described above. The full verification suite includes browser and API acceptance;
the larger generated graph is a separate stress test, with measurements in
`out/application-scale/results.json`. Generated scale and real-application behavior are
separate evidence; neither alone establishes performance for every large application.

Package-map selection is in `bundle.package-targets`: explicit missing, blocked, invalid,
local and redirected targets; ordered conditions; exact and wildcard subpaths; array fallback
and path validation. `bundle.resolve` handles package scope, `#imports`, self-references,
request-specific import/require conditions, browser file/dependency replacements (including
`false`), and canonical symlink identity. Unexported/private paths do not fall back to disk.
Resolution requests retain their kind even when one file both imports and requires a package.
This is a larger supported subset, not a claim of complete Node/package-manager parity.

Split stylesheets follow each root's static import closure, independent of JavaScript packing
policy. Static entries receive a matching `.css` file for the HTML to link. A dynamic import
waits for its root's CSS before evaluating any of that root's JavaScript. Concurrent requests
share a stylesheet load; a failed stylesheet rejects the import and can be retried. CSS import
cycles terminate, and imports of one sheet under different media conditions remain distinct.
Assets are copied for split builds too; `public-path` is available in the spec as well as the CLI.

An entry may contain implementation definitions only when other implementation chunks do not
import them. Otherwise it becomes a facade, avoiding initialization cycles caused by splitting
a large entry. Chunk hashes include their own content before their dependency closure. Different
contents targeting the same normalized output path fail before any file is written.

`--watch` and `--cache` accept split and multiple-output builds; their checks compare every current
JS/CSS/asset/source-map byte with a fresh build. Old hashed files are retained for existing clients.
HMR still supports a single JavaScript entry. Recovering from build errors and publishing a whole
output generation atomically remain follow-up work; file output is not a deployment transaction.

## What it does

Module graph, Node resolution (`exports`, `main` fields, conditions as esbuild has them: the
platform's, and `module` unless `--conditions` names others, `sideEffects: false`), an import, or an
`export … from`, of a name its module does not export reported where it is written, as esbuild
reports it (from TypeScript, which may import a type, it is not),
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
minification (private names too, each class's own the shortest after those of the classes around
it), `const`s written in where they are read with `--minify-syntax`, as esbuild does as it parses
(those at the start of a statement list whose values are numbers, booleans, `null`, `undefined`,
`NaN`, `Infinity` or strings of up to three characters, before tree shaking, so the branches they
decide are gone: `src/bundle/constants.rules`), source maps, output to standard output when no path
is given (its map inline), and resolve, load, transform and optimize hooks.

## What it does not do

Being explicit, because "everything esbuild does" is a lot:

- **Not built:** CSS modules, CSS nesting and other CSS lowering, JavaScript
  (stage 3) decorators, `accessor` fields, `--keep-names`, `--inject`, `--mangle-props`, `--metafile`,
  inlining enum values across files, and writing in a constant another module exports (esbuild
  prints an imported `const`'s value where it is read). A `switch` on a constant is not folded.
- **Hard errors for now:** `@import` with `layer()` or `supports()`, a media query on an import inside
  another, `--legal-comments=inline`, `--jsx=preserve` with `--pretty`, a decorated class expression or `export default`
  class, and decorators on members with computed names.
- **Hard errors when lowering:** `super` inside an async function, object rest nested inside another
  pattern or in an assignment, a computed key in an object rest, and calling a parenthesized optional
  chain, all below the version that has them; browser names in `--target`.
- **Simplifications:** CSS minification is whitespace and number spelling only, so minified
  stylesheets are a few percent larger than esbuild's. Content hashes in file names differ from
  esbuild's. Data URLs are spelled out or base64, without esbuild's percent escaping. Source maps have no
  `names`. Regex patterns are not validated. Labels are not renamed. Output that is not minified
  is printed compact: `--pretty` breaks lines, without esbuild's indentation, so compare sizes
  minified.

Known semantic gaps remain outside the Workbench acceptance target, all of which esbuild has too:
scope hoisting does not preserve imported names read only through direct `eval` (`eval("y")` for
`import { x as y }`; local declarations read only by direct `eval` keep their liveness and
spelling). Code that is not strict, put in an ES module output, becomes strict: a
duplicate parameter name or an assignment to an undeclared name then fails where the original did
not. ES modules put in IIFE or CommonJS output are no longer strict (`this` in a plain call is the
global object). These are correctness bugs, not completed production guarantees.

What the language forbids and a bundle would let through is an error, as esbuild reports it: an
assignment to a `const`, a class's own name inside it, an import or a namespace import's property
(a bundle makes them `var`s in one scope, where the assignment would succeed); and, for ES module
output, `delete x` and `with` in code that is not strict (`src/bundle/writes.rules`). Legacy octal
numbers and escapes in such code are printed as what they mean (`010` as `8`).

## Layout

Everything written in the languages is under `src/`; everything in Coil under `compiler/`.

- `src/languages/`: the grammars of the languages themselves, and the `.rules` prelude.
- `src/bundle/`: the bundler, in those languages.
- `src/tools/`: the command-line `esb` and `jsparse`, and `ptest`, which checks that `parallel-map`, for a program with no pipeline, gives the serial answer, in `.rules`.
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
