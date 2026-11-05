#!/bin/zsh
# usage: go.sh [apps...]: rebuild the bundler and compare each app with esbuild.
S=/private/tmp/claude-501/-Users-jimmyhmiller-Documents-Code-projects-high-level-lang/42c609f3-96d2-4d12-b20e-26987dd12610/scratchpad
cd ~/Documents/Code/projects/high-level-lang/poc && coil build -O1 -o $S/esb 2>&1 | grep -v '^wrote' | sed -E "s#$PWD/##g" | cut -c1-300 | head -10
cd ../corpus
apps=($@); (( $#apps )) || apps=(named all cjs)
for a in $apps; do echo "== $a"; ( time $S/esb app/$a.js --outfile=out/ours/$a.js $=EXTRA ) 2>&1 | grep -E 'total|panic|error' | sed -E 's/.*(user|system)//' | cut -c1-240 | tail -3; node tools/cmp.cjs out/ours/$a.js out/esb/$a.plain.js out/esb/$a.expected 2>&1 | cut -c1-260 | head -6; done
