# Fresh-process bundler comparison

This compares the current declarative bundler with esbuild, Rolldown, Rollup,
webpack and an existing experimental Turbopack CLI. It measures clean builds,
chunk transfer sizes and execution of the emitted code. It does not measure
incremental rebuilds, framework integration or comprehensive application support.

The tables under “Baseline results” preserve the original measurements. The
optimization follow-up below compares the updated implementation against that
baseline; both use the normal `-O1 --meta-opt=2` development build.

## Reproduce on macOS

From the repository root, with Coil, Node, Python and Chrome installed:

```sh
npm ci --prefix tests
npm ci --prefix benchmarks/bundlers
tools/build-tools.sh
python3 tools/scale-check.py --effects --modules=10000 --entries=32
python3 tools/compare-bundlers.py --runs=5 --report-name=results
```

The scale check generates the source fixture and also validates it. The comparison
uses `out/bin/esb`. Turbopack is included only if
`out/bin/turbopack-cli-4ebb2b7` exists, or an executable is supplied with
`--turbopack=PATH`. That binary is not installed by npm. Set `CHROME` to override
the default macOS Chrome executable. Use `--cases=real,mixed`,
`--tools=ours-exact-fragments,esbuild` or `--plain-only` for smaller runs.
Use `--binary=PATH` to measure another explicitly built executable; its hash is
recorded. Run comparisons sequentially; the harness enforces a lock.

Raw measurements, exact commands, binary hashes, versions, build logs and browser
checks are written under `out/bundler-comparison.noindex/` (Spotlight skips it, so it does not index the outputs while builds are timed). The checked-in
[results.json](results.json) preserves the measured results and samples; its
absolute command paths identify the original machine and are not portable.

## Method

Five fresh processes per tool/configuration, rotating tool order each round.
Each build starts with empty output, no persistent cache, no retained build
context, no watch and no source maps. Our flags include `--no-cache
--strategy=once --pipeline=full`. Normal within-build memoization and OS file
caches remain enabled. Time includes process startup, dependency loading,
minification when requested, and output writing. Plain and minified results are
separate. Minifiers use each tool's configured/native algorithm; Rollup uses
Terser. The adapters are intentionally isolated from the parser test corpus.

Peak RSS is the larger of the main process's macOS high-water RSS and sampled
aggregate process-group RSS (20 ms sampling), including minifier workers. This
is an estimate: short-lived child peaks can escape sampling. No builds run in
parallel with one another; browser validation occurs outside timed builds.

All tools receive one bootstrap with independently invoked dynamic report roots:

- **large:** 10,195 source modules, including 10,000 generated features, 128 shared
  policy modules, observable shared initialization and 32 lazy report roots.
- **real:** existing lodash-es, RxJS and D3 import fixtures with two lazy roots
  and a further dynamic dependency. This is a real-package fixture, not a full
  production application.
- **mixed:** one generated library containing 300 class/config/function families,
  split between two disjoint consumers. It deliberately exposes the possible
  benefit of fragments and is not representative of every codebase.

Each final output is executed in Chrome, loading the first route and then all
remaining routes. Values, logs (compared without ordering), and observable
once-only initialization counts are checked against native Node execution.
Browser exceptions and failed resource requests fail validation. This checks
these workloads; it is not a claim of complete JavaScript conformance.

`first_route` counts every JS resource actually requested through completion of
the first route, including runtime/bootstrap/shared chunks. `total_js` counts
all emitted JS, even unrequested files. Gzip is summed independently per file;
HTML, license text and maps are excluded. Sizes describe payload bytes, not
network latency or browser execution cost.

## Turbopack qualification

This is the pinned experimental standalone CLI labelled `4ebb2b7a5b`, not a
current Next.js application build. The harness uses `out/bin/turbopack-cli-4ebb2b7-define`, the
same source with one addition: a repeatable `--define KEY=VALUE` option
(`turbopack-cli-define.patch`, applied to that checkout), whose values are
parsed as Next.js's `defines` parses its env map and added to the CLI's own `CompileTimeDefines`
and free-variable references, beside `process.env.NODE_ENV`. The applications need constants
(react-admin reads `process.env.REACT_APP_DATA_PROVIDER` and `import.meta.env.MODE`), and the
CLI had no way to give them. The adjacent source checkout has local
modifications; executable hashes are recorded rather than assuming a clean
upstream build. Its browser host loads the bootstrap's declared initial chunks
and sets `TURBOPACK_CHUNK_BASE_PATH="/"`; emitted code is not modified. A separate
two-static-entry probe panicked on this snapshot and is recorded in the project
audit pad. The common single-bootstrap workload passes validation.

## Baseline results (before optimization)

See the tables below and the complete JSON for all six of our combinations
(exact/package/balanced × modules/fragments). Conclusions apply to these
fixtures and pinned configurations; they do not establish a universal ranking.

Measured on Apple M2 Max, v26.5.0. Five-run medians. All 66 final configurations passed browser validation; 330 timed builds completed.

### Large graph — minified

| Bundler | Build (s) | Peak RSS (MiB) | First-route gzip (bytes) | Total gzip (bytes) |
|---|---:|---:|---:|---:|
| Ours: whole modules | 1.423 | 1765.7 | 8461 | 206610 |
| Ours: fragments | 1.446 | 1816.2 | 8461 | 206630 |
| esbuild | 0.308 | 479.1 | 5474 | 122270 |
| Rolldown | 0.329 | 613.2 | 4889 | 105213 |
| Rollup + Terser | 7.775 | 2391.2 | 3621 | 67155 |
| webpack | 3.868 | 1861.7 | 5066 | 79923 |
| Turbopack (pinned CLI) | 1.925 | 777.1 | 9033 | 89954 |

### Real packages — minified

| Bundler | Build (s) | Peak RSS (MiB) | First-route gzip (bytes) | Total gzip (bytes) |
|---|---:|---:|---:|---:|
| Ours: whole modules | 0.134 | 218.0 | 12480 | 16324 |
| Ours: fragments | 0.142 | 219.1 | 12476 | 16320 |
| esbuild | 0.058 | 93.4 | 10119 | 13692 |
| Rolldown | 0.104 | 148.1 | 8791 | 12178 |
| Rollup + Terser | 1.196 | 469.8 | 8139 | 11245 |
| webpack | 0.741 | 436.9 | 10795 | 15607 |
| Turbopack (pinned CLI) | 0.083 | 123.4 | 14362 | 20467 |

### Mixed export families — minified

| Bundler | Build (s) | Peak RSS (MiB) | First-route gzip (bytes) | Total gzip (bytes) |
|---|---:|---:|---:|---:|
| Ours: whole modules | 0.029 | 50.7 | 9204 | 9795 |
| Ours: fragments | 0.025 | 38.8 | 4081 | 7848 |
| esbuild | 0.016 | 24.8 | 9013 | 9858 |
| Rolldown | 0.074 | 76.8 | 9305 | 10192 |
| Rollup + Terser | 0.403 | 257.4 | 7756 | 8635 |
| webpack | 0.555 | 269.1 | 8841 | 9488 |
| Turbopack (pinned CLI) | 0.057 | 114.9 | 8711 | 13154 |

The large graph exposes the main weaknesses: our fragment build takes about
4.7× esbuild's time and 3.8× its peak memory, and emits about 69% more total gzip.
Rolldown is also substantially faster, smaller and lower-memory here. We are
faster than Rollup and webpack in this configuration, but their minified
payloads are considerably smaller. The pinned Turbopack CLI is slower than us
here and uses less memory; its total payload is smaller while its first-route
payload is slightly larger.

Fragments reduce mixed-fixture first-route gzip from 9,204 to 4,081 bytes
(56%), and total gzip from 9,795 to 7,848 bytes (20%). The fragment result has
the smallest first-route gzip among these configurations. Its measured build
time and memory are lower than our whole-module variant in this small case;
that does not establish a general performance improvement. On the large graph,
fragments add about 1.6% time and 2.9% peak memory with effectively no payload
benefit. The real-package fixture also has almost no fragment size benefit.

Exact and balanced emit the same sizes on the real and mixed fixtures. On the
large graph, balanced adds about 0.3% total gzip and 1.3% first-route gzip over
exact with fragments; package policy also adds small overhead. These workloads
therefore do not establish a useful balanced-policy advantage. The complete JSON includes all combinations
and plain builds, including timing ranges and individual samples.

Next investigations should address measured large-graph allocation cost and
output overhead, then extend support with real application acceptance cases.
These measurements do not exercise CSS/assets, client/server boundaries, HMR,
source maps or every package resolution edge case; those need separate
coverage before claiming production parity.

## Optimization follow-up

The updated implementation is at `3f59b61` (normal `-O1 --meta-opt=2` build).
[optimized-results.json](optimized-results.json) records five new fresh processes
for all six of our configurations, on each fixture, plain and minified:
**180 builds and 36 browser-validated final outputs**. Persistent caching remains
disabled. External-tool controls below are the unchanged, pinned versions from
[the baseline run](results.json), not newly timed external-tool runs. The
interrupted exploratory `optimized-results` run under `out/` is not this report;
the final source file was `out/bundler-comparison/optimized-final.json`.

### Before and after: exact policy with fragments, minified

| Fixture | Build seconds, before → after | Peak MiB, before → after | First-route gzip bytes, before → after | Total gzip bytes, before → after |
|---|---:|---:|---:|---:|
| large | 1.4459 → 1.1548 | 1816.2 → 1367.3 | 8,461 → 4,422 | 206,630 → 97,758 |
| real | 0.1417 → 0.1343 | 219.1 → 188.1 | 12,476 → 12,476 | 16,320 → 16,315 |
| mixed | 0.0252 → 0.0233 | 38.8 → 37.7 | 4,081 → 4,081 | 7,848 → 7,848 |

The large graph improves by **20.1% in build time, 24.7% in peak memory,
52.7% in total gzip and 47.7% in first-route gzip**. Across all 36 configurations,
peak memory is lower in every case, and neither total nor first-route gzip
increases. Build medians improve in 33 configurations. Three real-package
variants take 2–6 ms longer; their timing ranges overlap the baseline ranges.
This is not a claim that every variant becomes faster.

### Updated large graph against the original controls, minified

| Bundler | Build seconds | Peak MiB | First-route gzip bytes | Total gzip bytes |
|---|---:|---:|---:|---:|
| Ours: fragments | 1.155 | 1367.3 | 4,422 | 97,758 |
| esbuild | 0.308 | 479.1 | 5,474 | 122,270 |
| Rolldown | 0.329 | 613.2 | 4,889 | 105,213 |
| Rollup + Terser | 7.775 | 2391.2 | 3,621 | 67,155 |
| webpack | 3.868 | 1861.7 | 5,066 | 79,923 |
| Turbopack (pinned CLI) | 1.925 | 777.1 | 9,033 | 89,954 |

Our payload now beats esbuild and Rolldown on both gzip measures for this graph.
We still take about 3.75× esbuild's build time and 2.85× its peak memory. Rollup
still emits the smallest payload here, and webpack's total gzip is also smaller.
The real-package fixture retains a payload gap against the leading controls.
The goal of winning every category against every tool is **not achieved**.

### Changes and correctness

- Initializer equivalence is a declarative fold in
  [analysis.attrs](../../src/bundle/analysis.attrs). Inert synchronous modules
  can share the sole initializer they forward to. Cycles, asynchronous graphs,
  require-driven wrappers and opaque dependencies retain their existing guards.
  The large output falls from 10,162 initializer-like allocations to two; the
  remaining guards preserve shared initialization and cached exception behavior.
- Safe nonnegative integer remainder folding lives in the minifier rules. Unsafe
  integers, zero divisors, signed zero, fractional and legacy-octal forms remain
  conservative. Ten thousand constant modulo operations disappear from the graph.
- Generic generated parsers allocate speculation in isolated scratch storage and
  copy accepted trees/error diagnostics out. Known-size lists and node children
  reserve storage once, with single evaluation of slice bounds.
- The generic runtime packs large memo values densely behind small hash indices;
  removed slots are reused. Small values keep direct hashing. This reduces
  within-build storage and does not depend on cross-build reuse.
- Joined symbol tables use bounded binary search within ID pages. Canonical path
  resolution shares a tracked within-build answer between resolution and graph
  loading. Symlink identity still comes from real-path resolution.
- Freed-page poisoning now releases backing storage while preserving unreadable
  reservations. Small-allocation arena growth no longer gets stuck creating
  individual chunks. These changes are generic runtime behavior, not bundler
  policy embedded in the compiler.

The full verification suite passed **222 checks**, including parser round trips,
source maps, real application CRUD/assets, all package-resolution checks,
client/server splitting, cache/watch mechanisms and memory stability. The final
declarative initializer fold additionally passed the complete evaluation suite,
with all policies, modules/fragments and minification, both entry orders,
cycles, async evaluation and cached failures. New allocation-budget assertions
check that forwarding wrappers disappear as well as executing correctly.
Generic runtime checks cover sparse/duplicate block starts, indexed lookup,
scratch lifetime, large/small memo values, removal and slot reuse. An intentional
read of released scratch memory faults in check mode.

Further work is still required for competitive large-graph speed and memory:
reduce parser/analysis work and introduce sound, bounded lifetimes for more
intermediate graphs and emitted trees. One-shot value arenas still retain much
of that work until process exit. More aggressive function/constant propagation
and inlining are needed to close the remaining output-size gaps. These are
remaining engineering tasks, not completed optimizations or promises of wins.

## Applications (2026-11-12)

`python3 tools/compare-bundlers.py --runs=7 --cases=dashboard,three10,large --minified-only --tools=ours-exact-modules,ours-exact-fragments,esbuild,bun,rolldown,rspack,rollup,webpack,turbopack --report-name=apps`
adds two application workloads and two more bundlers (Bun, from `bun` on the PATH, and Rspack,
pinned here); results are in [apps-results.json](apps-results.json).

- **dashboard:** `benchmarks/apps/dashboard`, a single-page app on real packages (React rendering
  with `react-dom/server`, d3, date-fns, lodash-es, zod, immer, RxJS), five routes loaded with
  `import()`, about 1,300 modules. Written without JSX so no bundler needs a transform plugin.
- **three10:** esbuild's own JavaScript benchmark, ten copies of three.js's sources with every
  namespace kept, about 7,600 modules.

**Vite** (8.3.8, which bundles with Rolldown 1.2 and minifies with Oxc) builds through its own
`build()` API with the entries as Rollup-style inputs, `@vitejs/plugin-react` for the TypeScript
applications as their own configs have it, `base: "./"`, and Vite's own `import.meta.env`.

Every tool builds for production: minified, `process.env.NODE_ENV` defined as "production" (Rollup
through `@rollup/plugin-replace`), code splitting, ES modules. Each sample records the one-minute
load average when the build started; the machine is shared, so check it before reading wall times.
CPU time (user + system over all threads and children) is recorded too.
