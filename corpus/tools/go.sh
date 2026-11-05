#!/bin/zsh
# usage: go.sh [apps...]: rebuild the bundler and compare each app with esbuild.
S="$(cd "$(dirname $0)/.." && pwd)/out/bin"; mkdir -p $S/mt
"$(dirname $0)/build-tools.sh" -O1
cd "$(dirname $0)/.."
apps=($@); (( $#apps )) || apps=(named all cjs)
for a in $apps; do echo "== $a"; ( time $S/esb app/$a.js --outfile=out/ours/$a.js $=EXTRA ) 2>&1 | grep -E 'total|panic|error' | sed -E 's/.*(user|system)//' | cut -c1-240 | tail -3; node tools/cmp.cjs out/ours/$a.js out/esb/$a.plain.js out/esb/$a.expected 2>&1 | cut -c1-260 | head -6; done
