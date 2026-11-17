# What the incremental cache changes

Every way a build runs, under each strategy of `src/app/build.pipeline` that tracks, beside esbuild,
Turbopack and Vite 8. Measured 2026-11-16, macOS (12 cores), `esb` built `-O3` from 117800b, every
build of ours with `--pipeline=full`. Median of 7 runs. `results.md` is the full table (least–most
beside each median), `results.json` every sample.

Wall times are from a machine that had other work on it: load average 5.5 when the run started and
33 when it ended. Instructions (G) and answers computed do not move with load; read those first.

## Strategies compared

| column | what it keeps |
|---|---|
| incremental | the default for `--watch` and `--cache`: `red-green` (checked by what each answer read, cut off when made again the same). In the one-shot rows this column is the default one-shot strategy, `once`, which tracks nothing |
| coarse | everything `incremental` keeps, used again only while no input at all changed: an edit makes everything again. This is the "no fine-grained incrementality" baseline |
| lean | as `incremental`, no more than 2000 answers per function, nothing saved with the cache |
| versioned | as `incremental`, package.json and directory listings checked by a content hash instead of by what they read |
| tailored | as `incremental`, what the last three builds did not ask for let go, only packages' answers saved |

`trusting` is not measured: it never looks at `node_modules` again, and the edit here is to a module
in a package, so it never rebuilds (by design).

## Rebuild after one edit, while watching

The edit adds one statement to a module from the middle of the bundle's sources (in a package).

| app | incremental | coarse | lean | versioned | tailored | esbuild | Turbopack | Vite |
|---|---|---|---|---|---|---|---|---|
| zod | **5.4 ms** · 23 answers | 19.4 ms · 2,068 | 5.6 ms | 8.7 ms | 4.7 ms | 14.1 ms | 30.9 ms | 49.8 ms |
| three | **17.6 ms** · 32 | 40.8 ms · 201 | 17.6 ms | 18.6 ms | 18.0 ms | 40.4 ms | – ¹ | 101.3 ms ¹ |
| date-fns | **8.6 ms** · 23 | 29.2 ms · 6,161 | 9.2 ms | 19.1 ms | 8.0 ms | 14.7 ms | 26.6 ms | 47.3 ms |
| rx | **6.3 ms** · 23 | 23.7 ms · 5,800 | 7.9 ms | 15.9 ms | 7.1 ms | 11.1 ms | 25.2 ms | 44.9 ms |
| 12× zod | **28.9 ms** · 23 | 175.4 ms · 23,171 | 31.0 ms | 98.0 ms | 26.3 ms | 110.4 ms | 35.6 ms | 145.1 ms |

The timings don't all measure the same span. Ours is the build's own time. esbuild's is
`ctx.rebuild()` timed in its process. Turbopack's runs from the write until its dev server serves the
edited chunk, so it includes noticing the edit and serving. Vite's runs from the write until
`build.watch` has written the bundle, so it includes noticing the edit.
¹ three's package says it has no side effects: Turbopack dev never serves the edit, and Vite's
rebuilds leave the added statement out.

- Fine-grained dependencies are worth 2.3–6× per rebuild: `coarse` makes 200–23,000 answers again
  per edit, `incremental` 23–32.
- `versioned` pays for its content hashes on every rebuild (12× zod 98 ms against 29 ms). `lean` and
  `tailored` rebuild as `incremental` does.

## Restarting from the cache (a fresh process, `--cache`)

Instructions retired, against a one-shot build (`once`) of the same app:

| app | one-shot | warm, unchanged | warm, one edit | `coarse`, warm, one edit |
|---|---|---|---|---|
| zod | 0.80 G · 29 ms | 0.11 G · 15 ms | 0.28 G · 27 ms | 1.00 G · 57 ms |
| three | 1.64 G · 68 ms | 0.11 G · 15 ms | 0.48 G · 44 ms | 1.42 G · 93 ms |
| date-fns | 0.65 G · 27 ms | 0.13 G · 19 ms | 0.43 G · 32 ms | 1.61 G · 76 ms |
| rx | 0.56 G · 25 ms | 0.12 G · 17 ms | 0.39 G · 30 ms | 1.15 G · 61 ms |
| 12× zod | 6.37 G · 130 ms | 0.79 G · 79 ms | 2.06 G · 153 ms | 10.13 G · 431 ms |

- With nothing changed, a restart does about 5–15× less work than building.
- After one edit it does 1.4–3.4× less work. On wall time it is about even with a one-shot build, and
  slower for 12× zod (153 against 130 ms): the one-shot build spreads over every core, while the warm
  run's checking and reading back is mostly serial.
- `lean` saves no answers, so its warm runs cost what a cold build does (zod 45 ms, 0.85 G).
- `tailored` saves only packages' answers: its cold cache costs the most (12× zod 509 ms, 975 MB).

## What tracking costs

| app | one-shot, `once` | one-shot, tracking (`coarse`) | `--cache`, cold | watch, first build |
|---|---|---|---|---|
| zod | 29 ms · 48 MB | 35 ms · 68 MB | 44 ms · 77 MB | 36 ms · 86 MB |
| three | 68 ms · 78 MB | 68 ms · 115 MB | 77 ms · 126 MB | 94 ms · 129 MB |
| date-fns | 27 ms · 31 MB | 41 ms · 52 MB | 55 ms · 67 MB | 47 ms · 86 MB |
| rx | 25 ms · 32 MB | 36 ms · 50 MB | 46 ms · 58 MB | 41 ms · 81 MB |
| 12× zod | 130 ms · 338 MB | 191 ms · 649 MB | 279 ms · 751 MB | 214 ms · 841 MB |

Recording dependencies makes a one-shot build 1.0–1.5× slower, with 1.4–1.9× the memory. That is why a
plain build uses `once`. A cold cache adds the cost of saving on top.

For context, esbuild one-shot: zod 21 ms, three 48 ms, date-fns 26 ms, rx 21 ms, 12× zod 106 ms.

## Correctness while measuring

Running the strategies on many threads turned up two bugs, both fixed before these numbers were
taken:

- 283ed0e: `lean` from a warm cache with `--pipeline=full` panicked. A names table was read back
  from the cache inside a naming job, through the guard meant for the build's shared table.
- 117800b: a memo's answer that another thread was making again could be read as current. The node
  is marked current before the new answer goes into the table, so a reader in between got the old
  answer, and later held its region after that region was let go (`coarse`, `--pipeline=full`, a
  watcher started from a warm cache).

`mechanism-check.py` (now with `--pipeline=full` cache runs), `cache-check.py`, `strategy-check.py`
and `watch-check.py` all pass on this binary (`checks/`).

A third crash predates this work and is still open: about one run in three of
`tools/evaluation-check.py` segfaults in a minified `--pipeline=full` build, in `hl.rt.tok!`
printing a part of a chunk (`chunk-own--working`). The binary from before this work fails at the
same rate.

## Reproduce

```
HL_TOOLS_OUT=out/bin-o3-cachebench tools/build-tools.sh -O3
B=out/bin-o3-cachebench/esb
python3 tools/bench.py --runs=7 --apps=zod,three,datefns,rx,manyzod --out=out/results.md \
  incremental=esb:$B:--pipeline=full coarse=esb:$B:--pipeline=full,--strategy=coarse \
  lean=esb:$B:--pipeline=full,--strategy=lean versioned=esb:$B:--pipeline=full,--strategy=versioned \
  tailored=esb:$B:--pipeline=full,--strategy=tailored \
  esbuild=esbuild:tests/node_modules/esbuild turbopack=turbopack:out/bin/turbopack-cli-4ebb2b7 \
  vite=vite:benchmarks/bundlers/node_modules/vite
```
