#!/bin/bash
# Build a jsparse that writes the generated JS parser to out/js-generated.coil (one defn per line in
# out/js-generated.split.coil), then put compiler/hl/syntax.coil back. Don't run during a suite.
set -e
cd "$(dirname "$0")/../../.."
cp compiler/hl/syntax.coil out/syntax.predump.coil
python3 - "$PWD/out/js-generated.coil" <<'PY'
import pathlib, sys
p=pathlib.Path('compiler/hl/syntax.coil'); s=p.read_text()
a='''    (let [shell (dsl/render (emit-module! (mut g) (mut c) levels))]
      (splice-aux shell (.aux g)))))'''
b='''    (let [shell (dsl/render (emit-module! (mut g) (mut c) levels))
          out (splice-aux shell (.aux g))]
      (when (rt/at? path (- (len path) 9) "js.syntax") (rt/write-output "%s" out))
      out)))''' % sys.argv[1]
assert s.count(a)==1; p.write_text(s.replace(a,b))
PY
coil build compiler/boot/jsparse.coil -O3 --meta-opt=2 --reader-artifact "$(tools/readers.sh)" -o out/bin/jsparse-dump 2>&1 | grep -v '^wrote' | tail -3 || true
cp out/syntax.predump.coil compiler/hl/syntax.coil
tr '\n' ' ' < out/js-generated.coil | sed 's/(defn /\n(defn /g' | sed 's/  */ /g' > out/js-generated.split.coil
