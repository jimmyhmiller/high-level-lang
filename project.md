# high-level-lang

## Summary

An experiment in language-driven development: a JavaScript bundler specified as a
tower of small languages, each a Coil reader metaprogram. The top-level language
describes targets and pipelines and lowers into per-stage languages for parsing,
rewriting and analysis. Compiling the spec produces a native bundler specialised
to it.

- `poc/`: the working proof of concept. `cd poc && coil run`, then `node dist/client.js`.
- `experiments/`: small programs that established how Coil readers behave, and
  minimal repros of Coil issues.

Notes and open issues are in the pad `high-level-lang`.
