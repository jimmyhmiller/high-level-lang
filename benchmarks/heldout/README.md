# Held-out libraries

Libraries the bundler was never developed or tuned against, pinned in `package.json`, for checking
that what it does on the libraries it was built with (`tests/`) holds elsewhere. Every check runs
every output under Node and compares it with an oracle; sizes and times are reported, not checked.

```sh
npm ci --prefix benchmarks/heldout --ignore-scripts
node benchmarks/heldout/node_modules/esbuild/install.js

python3 tools/heldout-sizes.py       # minified bytes and gzip vs esbuild (and terser, swc), time; output = esbuild's
python3 tools/heldout-analyze.py     # --analyze vs esbuild's metafile and the output's own source map
python3 tools/heldout-fragments.py   # two pages a library: what each loads, as Node loads it; output = unbundled
python3 tools/heldout-exercise.py    # every export called on a matrix of inputs; plain and minified = esbuild's
```

Each takes `ESB=path` for another binary, and app or library names to run only those.

- `apps/`: one program a library, exercising a good part of it, whose output is compared. `lit`
  needs a DOM, so under Node every build of it fails the same way; it is compared by that error.
  `jquery` gets a stub of a window (`nodom.js`).
- `pages/LIB/{a,b}.js`: two pages using different parts of a library, for code splitting.
  `pages/trace.mjs` is a Node load hook that records each file a page loads.
- `ex/`: `tests/apps/exercise.mjs` aimed at a library's whole API.

terser and swc minify esbuild's unminified bundle, which defines no `process.env.NODE_ENV`, so on
libraries with development checks (mobx, redux toolkit, vue) their numbers are of a development
build and not comparable.
