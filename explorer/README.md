# Tower Explorer

A local tool for working on the bundler: what a rule is, where it applies in real bundles, what a
build holds and why, and examples kept for each rule.

    tools/build-tools.sh                 # out/bin/esb, which records when asked
    python3 explorer/server.py           # http://127.0.0.1:8770
    python3 explorer/server.py --check   # run every rule example; exits 1 if one fails

## What it is made of

- **The map** is the tower: every module under `src/`, colored by its language, in columns by how
  far it builds on others (grammars and facts on the left, the bundler's top on the right). Hover
  one for what it builds on and what builds on it; click to open its code.
- **Code** is a module's source with every name a link (an alias's `js.render`, the file's own
  declarations, a grammar's node kinds): hover for what it is, click to go to it, ⌥-click to put it
  in the middle of what uses it. Beside the code is a picture of the module in its language's terms,
  kept in step with it: who calls whom (`.rules`, `.attrs`), which relations derive which and what
  states their facts (`.facts`), each rule's pattern and result as trees with how often it applied
  (`.rewrite`), which productions use which with each one's railroad (`.syntax`), mechanisms and
  strategies and the stage/plan table (`.pipeline`), which nodes open scopes and where names land
  (`.scopes`).
- **Focus** puts one declaration in the middle: what uses it on the left, what it uses on the right,
  across languages (calls, facts asserted and read, node kinds matched, functions the pipeline
  keeps), two steps out; click any to move there.

- **Builds** are real bundles of `tests/apps`, made with `esb --record=DIR` and kept under
  `out/explorer/builds`. A recording holds what each rewrite rule did (`rewrites.jsonl`: the rule's
  file and line, the module and place, the node before and after, recorded by the rewrite compiler
  in `compiler/hl/rewrite.coil` for every `.rewrite` language), every statement of every module and
  the derivation that keeps it (`explain.json`, `src/bundle/explain.rules`, from link.facts'
  `why-active-part`), and the analysis and ledger the bundler already writes. A build's page is the
  bundle analyzer: modules by bytes, then a module's statements, kept or not, and for each the rules
  behind it.
- **Rules** are every rewrite rule, Datalog rule and declaration under `src/`, read from the files
  as they are (`explorer/catalog.py`). A rule's page shows what it is, its picture, the language it
  is written in, what refers to it, and every place it applied in the builds made so far: the
  rewrite's before and after, or the fact derived and the statement it is about.
- **Examples** are small programs kept for a rule in `explorer/examples/*.json`: a source, flags,
  and what is expected (the rule applies; the output holds something). Make one from any place a
  rule applied, or write one. `--check` runs them all.
- **Languages** are the tower itself: each language's grammar (railroad diagrams), its compiler in
  `compiler/hl`, the files written in it, and where each form of it is used in `src/`.
- **Compare** two builds of the same entry, before and after a change to the bundler: statements
  kept now and not before, rules applied more or less, bytes by module. "Build each again" rebuilds
  every build the current bundler did not make.

## What is recorded, and what is not yet

Rewrite rules (every `.rewrite` file) and linking's Datalog rules (`link.facts`) are recorded.
Attribute grammars (`.attrs`), `.rules` functions and the constants pass are listed with their
references but not recorded: their rule pages say so.
