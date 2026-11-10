# Fresh-process bundler comparison

This compares the current declarative bundler with esbuild, Rolldown, Rollup,
webpack and an existing experimental Turbopack CLI. It measures clean builds,
chunk transfer sizes and execution of the emitted code. It does not measure
incremental rebuilds, framework integration or comprehensive application support.

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
Run comparisons sequentially; the harness enforces a lock.

Raw measurements, exact commands, binary hashes, versions, build logs and browser
checks are written under `out/bundler-comparison/`. The checked-in
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
current Next.js application build. The adjacent source checkout has local
modifications; executable hashes are recorded rather than assuming a clean
upstream build. Its browser host loads the bootstrap's declared initial chunks
and sets `TURBOPACK_CHUNK_BASE_PATH="/"`; emitted code is not modified. A separate
two-static-entry probe panicked on this snapshot and is recorded in the project
audit pad. The common single-bootstrap workload passes validation.

## Results

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
