# How fast the parser is, against others

`run.py` times our parser (`out/bin/jsparse bench`) against:
- **Native, parse only:** Oxc (`oxc_parser` 0.152), SWC (`swc_ecma_parser` 47), from Rust (`rust/`), and esbuild's own `js_parser.Parse`, built inside a copy of esbuild 0.28.2 (`esbuild/main.go`). esbuild's parse also visits the tree: it binds scopes and folds constants, as a build does.
- **Through their JavaScript APIs, in Node:** acorn, meriyah, Babel, TypeScript's `createSourceFile`, SWC's `parseSync`, Oxc's `parseSync` (its AST made a JavaScript object, as JSON or by raw transfer), and esbuild's `transformSync`, which has no parse-only form and prints as well.

Each big file runs in a fresh process per parser: three untimed parses, then the best and median of nine. Each corpus is one timed pass. Everything runs on one thread, except that `native esbuild` lets Go's garbage collector use the other cores. Ours keeps every tree it makes, so its corpus runs are cut into chunks of 3,000 files. Each file's goal (module, else script) is settled before timing, as the bundler settles it.

Run `npm install` here first, then `python3 run.py --vscode ~/src/vscode`. It needs cargo and go.

## Results (2026-11-12, Apple M2 Max, `results.json`)

Throughput in MB/s, from the best time of each file, summed:

| Parser | big JS (8 files, 17 MB) | big TS (checker.ts + 4 VS Code) | node_modules JS (62,294 files, 264 MB) | VS Code TS (11,526 files, 186 MB) | peak memory, typescript.js |
|---|---|---|---|---|---|
| **ours, parse** | **33.9** | **45.9** | **33.3** | **40.3** | **443 MB** |
| ours, parse + early errors | 27.4 | 35.9 | | | |
| Oxc (Rust) | 279.9 | 330.8 | 260.4 | 262.6 | 100 MB |
| SWC (Rust) | 143.1 | 164.9 | 122.8 | 120.2 | 140 MB |
| esbuild (Go, one thread) | 49.2 | 56.9 | 52.2 | 55.4 | |
| esbuild (Go) | 55.4 | 66.6 | 56.0 | 57.2 | 170 MB |
| Oxc, raw transfer (JS API) | 139.4 | 136.8 | 104.6 | 106.0 | 344 MB |
| meriyah | 82.9 | | 51.4 | | 311 MB |
| Babel | 36.0 | 33.6 | 35.0 | 31.0 | 423 MB |
| acorn | 35.5 | | 34.0 | | 379 MB |
| esbuild transform (JS API, parses and prints) | 34.7 | 39.8 | 8.4 | 10.4 | 155 MB |
| TypeScript | 32.3 | 35.2 | 25.2 | 32.2 | 545 MB |
| Oxc, JSON (JS API) | 20.2 | 21.5 | 18.3 | 16.6 | 800 MB |
| SWC (JS API) | 12.2 | 13.8 | 10.4 | 12.1 | 1,318 MB |

typescript.js (9.1 MB): ours 278 ms; Oxc 31 ms; SWC 63 ms; esbuild 157 ms; acorn 269 ms; Babel 264 ms; TypeScript 276 ms.

What it says: ours is as fast as the JavaScript parsers (acorn, Babel, TypeScript), at 1/8 of Oxc's speed, 1/4 of SWC's, and 0.6× esbuild's parse and visit. Parsing typescript.js peaks at 49 times the source's size (Oxc: 11 times).
