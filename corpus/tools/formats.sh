#!/bin/zsh
# Every output format, ours against esbuild's, by what a consumer sees.
S="$(cd "$(dirname $0)/.." && pwd)/out/bin"; mkdir -p $S/mt
cd "$(dirname $0)/.."
cat > $S/mt/uselib.mjs <<'EOT'
import(process.argv[2]).then((m) => { console.log(Object.keys(m).sort().join(), m.answer, m.hello("x"), new m.default().hi()); });
EOT
cat > $S/mt/usecjs.cjs <<'EOT'
const m = require(process.argv[2]); console.log(Object.keys(m).sort().join(), m.answer, m.hello("x"), new m.default().hi());
EOT
for f in esm cjs; do for mode in "" --minify; do ext=$([ $f = esm ] && echo mjs || echo cjs); o=$PWD/out/ours/lib.$f$mode.$ext; e=$PWD/out/esb/lib.$f$mode.$ext; $S/esb app/lib.js --format=$f ${=mode} --outfile=$o > /dev/null 2>$S/mt/err || head -2 $S/mt/err; node_modules/.bin/esbuild app/lib.js --bundle --format=$f ${=mode} --outfile=$e --log-level=error; u=$([ $f = esm ] && echo uselib.mjs || echo usecjs.cjs); a=$(node $S/mt/$u $o 2>&1 | head -3 | cut -c1-160); b=$(node $S/mt/$u $e 2>&1 | head -2 | cut -c1-120); [ "$a" = "$b" ] && r="SAME ($b)" || r="DIFF: $a"; printf '%-4s %-9s ours=%5s esb=%5s %s\n' $f "$mode" $(wc -c < $o) $(wc -c < $e) "$r"; done; done
for mode in "" --minify; do $S/esb app/lib.js --global-name=Lib ${=mode} --outfile=out/ours/lib.iife.js >/dev/null; node -e 'const c=require("fs").readFileSync("out/ours/lib.iife.js","utf8");const m=new Function(c+";return Lib")();console.log("global-name'"$mode"':",Object.keys(m).sort().join(),m.answer,m.hello("y"))' 2>&1 | head -3 | cut -c1-140; done
