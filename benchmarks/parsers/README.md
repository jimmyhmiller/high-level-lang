# How fast the parser is, against others

`run.py` times our parser (`out/bin/jsparse bench`) against:
- **Native, parse only:** Oxc (`oxc_parser` 0.152), SWC (`swc_ecma_parser` 47), from Rust (`rust/`), and esbuild's own `js_parser.Parse`, built inside a copy of esbuild 0.28.2 (`esbuild/main.go`). esbuild's parse also visits the tree: it binds scopes and folds constants, as a build does.
- **Through their JavaScript APIs, in Node:** acorn, meriyah, Babel, TypeScript's `createSourceFile`, SWC's `parseSync`, Oxc's `parseSync` (its AST made a JavaScript object, as JSON or by raw transfer), and esbuild's `transformSync`, which has no parse-only form and prints as well.

Each big file runs in a fresh process per parser: three untimed parses, then the best and median of nine. Each corpus is one timed pass. Everything runs on one thread, except that `native esbuild` lets Go's garbage collector use the other cores. Ours keeps every tree it makes, so its corpus runs are cut into chunks of 3,000 files. Each file's goal (module, else script) is settled before timing, as the bundler settles it.

Run `npm install` here first, then `python3 run.py --vscode ~/src/vscode`. It needs cargo and go.

## Results (2026-11-13, Apple M2 Max, `results.json`)

Throughput in MB/s, from the best time of each file, summed:

| Parser | big JS (8 files, 17 MB) | big TS (checker.ts + 4 VS Code) | node_modules JS (88,867 files) | VS Code TS (11,526 files, 186 MB) | peak memory, typescript.js |
|---|---|---|---|---|---|
| Oxc (Rust) | 282.6 | 324.3 | 263.5 | 263.6 | 100 MB |
| Oxc, raw transfer (JS API) | 151.2 | 142.4 | 99.3 | 107.8 | 345 MB |
| SWC (Rust) | 146.3 | 161.6 | 131.3 | 132.3 | 140 MB |
| **ours, parse** | **99.3** | **109.4** | **88.7** | **93.7** | **208 MB** |
| meriyah | 84.3 | | 61.9 | | 315 MB |
| ours, parse + early errors | 70.4 | 79.0 | 59.5 | 67.7 | |
| esbuild (Go) | 53.4 | 64.0 | 57.1 | 60.2 | 164 MB |
| esbuild (Go, one thread) | 51.5 | 58.0 | 52.8 | 58.6 | |
| acorn | 36.1 | | 31.4 | | 378 MB |
| esbuild transform (JS API, parses and prints) | 35.4 | 39.0 | 8.3 | 17.5 | 154 MB |
| Babel | 33.8 | 26.1 | 34.6 | 33.5 | 424 MB |
| TypeScript | 33.0 | 33.9 | 31.0 | 33.3 | 548 MB |
| Oxc, JSON (JS API) | 20.6 | 21.4 | 18.2 | 17.4 | 800 MB |
| SWC (JS API) | 12.2 | 13.9 | 11.7 | 12.9 | 1,318 MB |

typescript.js (9.1 MB): ours 88 ms (with early errors 125 ms); Oxc 31 ms; SWC 61 ms; esbuild 158 ms; meriyah 105 ms; acorn 255 ms; Babel 262 ms; TypeScript 271 ms.

Ours was 33.9 MB/s on the big JS files (typescript.js 278 ms, 443 MB) on 2026-11-12, before the
generated parsers were made faster: the tree built in place rather than copied out of scratch
storage, lists allocated at their size, the memo's answers logged and kept only once backtracked
over, infix operators by precedence climbing, and operator loops guarded by the next byte. The
grammar did not change. Ours now parses faster than esbuild's parser and every parser written in
JavaScript; SWC is 1.5 times as fast, Oxc 2.8 times.
