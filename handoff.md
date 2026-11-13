# Parser speed: handoff (2026-11-13)

The goal was to make the generated JavaScript/TypeScript parser as fast as Oxc **without cheating**.
That means no hand-written parser and nothing language-specific in the compiler. Every speedup comes
from the grammar compiler (`compiler/hl/syntax.coil`) and its runtime (`compiler/hl/rt.coil`). The
grammar (`src/bundle/js.syntax`) is unchanged except for one new declaration, `newline LineEnd`.

## Where things stand

| | big-file set, parse total | typescript.js (9.1 MB) | throughput (big JS) |
|---|---|---|---|
| 2026-11-12, before any of this | — | 278 ms | 33.9 MB/s |
| `83941dc` (last benchmark run) | — | 88 ms | 99.3 MB/s |
| `0ae6c7b` | 200 → 148 ms | ~68 ms | ~134 MB/s (est.) |
| **now (`968ba9d`)** | **~140 ms** | **~65 ms** | **~140 MB/s (est.)** |
| Oxc (Rust, native) | | 31 ms | 282.6 MB/s |
| SWC (Rust, native) | | 61 ms | 146.3 MB/s |
| esbuild (Go) | | 158 ms | 53.4 MB/s |

- **Gap to Oxc:** about 2×. We're now level with SWC (it's ~5% faster on throughput, we're ~6% faster on typescript.js) and well ahead of esbuild and every JavaScript-hosted parser.
- **Estimates:** "est." rows come from interleaved timing against the previous build (`benchmarks/parsers/perf/cmp.sh`), not from re-running `benchmarks/parsers/run.py`. **The README table in `benchmarks/parsers/` still shows the `83941dc` numbers; re-run `run.py` to refresh it.**
- **Parse + early errors:** the early-error pass (`bundle.early.check`) didn't change today. It costs about 37 ms on typescript.js, so parse plus early errors is about 102 ms.

### Today's commits, all checked

- `0ae6c7b` **Out-parameters** (rules write into the caller's `(mut Node)` and return bool):
  - No backtrack for alternatives the first byte rules out.
  - Inline pushes onto the parse stack and memo.
  - The `newline` grammar declaration replaces the runtime's hardcoded ECMAScript line terminators.
- `376ecac` **Two-token prediction**, plus "chain rules begin like their base" for first-byte sets.
- `217408e` `skip-new!` no longer repeats its caller's test.
- `968ba9d` Lexer byte loops over a local index.

Each commit:
- produced identical trees on 3,411 files (`same-trees.sh`), apart from source line numbers in error traces;
- left test262 unchanged at `{"cases": 103533, "rejects_valid": 805, "accepts_invalid": 1396}`;
- passed the full suite (verify 228/228, same/lowered/split identical to baseline, 0 plan diffs, correctness 83/83).

## How to measure (scripts in `benchmarks/parsers/perf/`, run from the repo root)

- **Build a parser binary without the full tool build:**
  `coil build compiler/boot/jsparse.coil -O3 --meta-opt=2 --reader-artifact "$(tools/readers.sh)" -o out/bin/jsparse-X`
- **Benchmark:** `out/bin/jsparse bench LIST N` prints `BENCH path bytes parse-best parse-median check-best check-median` in µs.
- **`insn.sh LIST bin…`:** instructions retired. Load-independent; the first thing to look at.
- **`cycles.sh LIST bin…`:** cycles and IPC, min of 3. Fewer instructions often meant *more* cycles today; check both.
- **`cmp.sh LIST ROUNDS bin…`:** interleaved wall-clock timing. The machine is shared (load 10–15), so only interleaved comparisons mean anything.
- **`same-trees.sh A B LIST`:** identical printed trees and errors. Use `ops.js`/`ops.ts` (630 operator pairs) for a quick check and the 3,411-file set for a full one. To ignore shifted line numbers, pipe through `sed -E 's/\.coil:[0-9]+:[0-9]+//'`.
- **`big.list`:** the big-file set (typescript.js, echarts, react-dom, three, vue, d3, lodash, moment, checker.ts).
- **`dump.sh`:** builds once with a hook that writes the generated parser to `out/js-generated.coil` (and a one-defn-per-line split), then restores `syntax.coil`.
- **`trace.py`:** single-steps one call in lldb and counts instructions per function. This was the most useful tool of the day, the only way to see where instructions go inside the inlined rule functions.
- **Profiling:** `tools/profile-fresh.py --under=bundle.js.parse-working -- out/bin/jsparse bench LIST 3` for self time, `--callers=FN` for who calls a function.
- **Full check before committing:**
  1. `tools/build-tools.sh -O3`
  2. `tools/verify.py`
  3. `tools/same.py`, `same-lowered.py` and `same-split.py` against a saved baseline `esb`
  4. `tools/same-plans.py`
  5. `tools/heldout-*.py`
  6. `tools/correctness-check.py`
  7. test262 via `run262.py JSPARSE TEST262_DIR WORK_DIR`

  **Never edit `compiler/hl` or `src` while a build or suite runs**: it fails with "stale provider artifact".

## Where the time goes now

**Self time, typescript.js parse:**
- Rule functions (`p-Assign`, `p-Call`, `p-Unary`, `p-Primary`, `p-Stmt`, `p-Binary-climb`): **~37%**
- Whitespace (`skip-new!`): ~10–13%
- Identifier lexing (`lex-BindName`, `lex-Reserved`, `lex-IdPart`): ~8–10%
- `memmove` copying list items off the parse stack (`stack-take!`): ~5%
- Memo promotion (`memo-table-put!`): ~1–3%

**One realistic statement**, `const a = callback(array[i], i);` (35 bytes), costs **7,448 instructions**, about 213 per byte. Oxc is probably around 20 per byte. Per identifier operand:
- **Descent** (Assign → AssignExpr → AssignBase → Cond → Binary → Unary → Exp → Update → PostUpdate → Call → New → Primary): about 600–700 instructions. Each level runs its guards, a function prologue, and on the way back its own "is an operator next" check.
- **Lexing the identifier:** about 250 (the reserved-word check about 70, the rest about 17 per character).
- **Whitespace:** about 105 for a single space the first time.
- **The memo for `Assign`:** about 100–150 (key, log entry, kept node).
- **Keyword alternatives tried because an identifier shares their first letter** (`class` on `callback`, `async function` on `array`): 0–300.

## What worked (in order of size)

1. **Out-parameters instead of returning `Option<Node>` (96 bytes) by value: 1.25×.** Every call site of a rule no longer needs its own result slot; `p-Unary-alt9` had a 784-byte frame. Single-capture pass-through alternatives parse straight into the caller's slot.
2. **No backtrack after an alternative the first byte rules out: 8%.** It cost ~18 instructions × 24 alternatives in `p-Stmt` per statement.
3. **Two-token prediction plus correct first-byte sets for chain rules: ~5%.** The second part mattered more:
   - `rule-start` returned "unknown" for suffix and infix rules, so `Assign` had no first-byte guard.
   - As a result, every block-closing `}` logged a memo entry and promoted it into a hash table on backtrack.
4. **Inline fast paths for pushes:** 3%.
5. **Tight lexer loops; `skip-new!` not repeating its caller's test:** ~1% instructions each, time unchanged.

## What didn't work (measured, reverted)

| Idea | Result | Why |
|---|---|---|
| Byte switch choosing a group of alternatives (`case` on the byte) | more cycles; +0.6% at best | with `Option<Node>` it multiplied result slots (8.9 KB frame for `p-Stmt`); with out-params the sequential guards are only ~3 instructions each and predict well |
| Whitespace fast path (rescan plain runs instead of the per-position table) | +8% cycles | backtracking re-skips the same space many times; the table answers in one lookup |
| 1024-slot direct-mapped whitespace cache instead of the 4-bytes-per-source-byte table | slower | more rescans; the big table wasn't a memory bottleneck |
| Two-entry whitespace cache | +7% instructions | most positions have no space in front of them; the one-entry cache answers repeats there with one compare |
| First-byte guards on lookahead choices (`!("{" \| "function" …)`) | no change | |
| Guarding keyword alternatives by comparing the whole keyword at the token start | ~5% slower | `token-start` expanded in every guard; code growth |
| …the same, by the length of the word at the token start | ~9% slower | the word scan duplicates the identifier lex that follows; a failed keyword attempt (~25–40 instructions) is cheaper |
| Inline byte compares for literals; literal choices switched on first byte | no change | LLVM already does about as well |
| Word classification (classify each word once against all whole-word literals; keyword literals and `Reserved` answered from it) | +6.5% instructions, 5% slower | classifying every new identifier costs more than the old reserved-word check, which rejects most identifiers within a few byte compares |

**The lesson:** with this code shape, most local changes cost about as much as they save. IPC falls as generated code grows, so check cycles, not just instructions.

## Bugs found, not fixed

- **`js.syntax` `Reserved` lists `"in"` before `"instanceof"`.** With PEG ordered choice, `"in"` matches, `!IdPart` fails and `"instanceof"` is never tried, so `instanceof` isn't reserved and `var instanceof = 1` is accepted. The fix is to list `"instanceof"` first, but it changes what's accepted; check test262 and verify. Other literals shadowed by an earlier prefix in a `(… | …) !Word` choice are worth a compile-time warning; the compiler can detect them (the code was written in the reverted word-classification patch: `keyword-set`).
- **The README benchmark table is stale** (see above).

## What I think would help next

Ordered by expected value.

1. **A different parser back end from the same grammar.** I think this is the only route to Oxc-level speed. The current code shape (one function per rule, ordered alternatives behind one-byte guards, ~13 levels per operand) is the limit, and tuning it has stopped paying. The idea:
   - Generate a tokenizer for the grammar's context-free tokens.
   - Compile the predictive parts of the grammar (LL(1)/LL(2) by FIRST/FOLLOW analysis, Redziejowski's LL(1p) for PEGs) into switch-on-token code.
   - Compile the `precedence`/infix/suffix/postfix declarations into one Pratt loop.
   - Fall back to today's backtracking code only where the grammar isn't predictive: arrow parameters, TS generics vs. `<`, regex vs. `/`.

   For the context-sensitive tokens, see context-aware scanning (Van Wyk & Schwerdfeger) and flap's fused lexing (Yallop et al., PLDI 2023). This is a multi-session rewrite of the back end with an uncertain result, but it stays declarative.
2. **A Pratt loop for the expression chain alone**, within today's back end. It targets the ~37% in rule functions:
   - Parse the prefix part once (Unary operators, `new`, Primary).
   - Then loop over postfix, suffix and infix operators of all levels with one next-byte test per iteration, instead of each level re-checking on the way up.
   - Guess: 10–25%. Uncertain given today's results.
3. **Memoize only where re-entry is possible** (Becket & Somogyi, PADL 2008). `Assign` is memoized for nested arrow-parameter backtracking, and every expression pays about 100–150 instructions to log and keep its node. A grammar analysis could memoize only where a later alternative can re-request the same position, for example `Assign` inside `Params` versus in the parenthesised expression after it. Cuts (Mizushima et al., PASTE 2010) would also shrink the log.
4. **Build lists in place instead of copying off the parse stack** (`stack-take!` and memmove, ~5%), for example by growing the list in the tree cursor when it's the innermost open list.
5. **Whitespace (10–13%)** is mostly table lookups on revisits plus the first scan. Nothing simple worked. Computing the newline flag during the space lex instead of rescanning with `newline-in?` may help a little.
6. **Early errors (~37 ms on typescript.js)** weren't touched today. The top costs are `name-problem` (per identifier: `valid-name?`, `unescaped`, membership tests against keyword lists), `attrs-visit` and `var-names-into!`. Compiling `x in [literal list]` in the rules compiler to a switch would help everywhere.

## Research pointers

- flap: deterministic parser with fused lexing (PLDI 2023): https://arxiv.org/abs/2304.05276
- A typed, algebraic approach to parsing (PLDI 2019): https://www.cl.cam.ac.uk/~jdy22/papers/a-typed-algebraic-approach-to-parsing.pdf
- Context-aware scanning (GPCE 2007): https://galois.com/wp-content/uploads/2023/06/gpce.pdf
- Redziejowski, FIRST/FOLLOW and LL(1p) for PEGs: https://arxiv.org/pdf/1304.3177 and the Mouse PEG Explorer: https://mousepeg.sourceforge.net/explorer.htm
- Packrat with cuts, mostly constant space (PASTE 2010): https://kmizu.github.io/papers/paste513-mizushima.pdf
- DCGs + memoing = packrat, but is it worth it? (PADL 2008): https://www.mercurylang.org/documentation/papers/packrat.pdf
- Rats! (PLDI 2006), a list of packrat optimizations: https://cflmark.nms.kcl.ac.uk/hg/regexp/raw-file/tip/PEGParsing/pldi06.pdf
- Parsley, staged selective parser combinators (ICFP 2020): https://mpickering.github.io/papers/parsley-icfp.pdf
- Oxc parser architecture: https://oxc.rs/docs/learn/architecture/parser

## Gotchas

- **Validity check in `bench`:** it panics on a file with an early error ("an early error the first check did not find"), so micro-benchmark files must be valid. Redeclaring `const` makes them invalid.
- **`a;` microbenchmarks mislead.** `a` collides with `async`/`await`. Even `x;` overstates label and arrow attempts compared with real code. Trace a realistic statement before estimating a gain.
- **`trace.py` is slow** (~25 steps a second): trace one statement of a four-statement file.
- **Never edit compiler sources during a build or suite.** It fails with "stale provider artifact".
- **Notes** with more detail and numbers are in the `high-level-lang-parser` pad.
