#!/bin/zsh
# Compare our --minify with esbuild's on every app: sizes, gzip, and behaviour.
S="$(cd "$(dirname $0)/.." && pwd)/out/bin"; mkdir -p $S/mt
cd "$(dirname $0)/.."
apps=($@); (( $#apps )) || apps=(named all cjs)
for a in $apps; do s=$( { /usr/bin/time -p $S/esb app/$a.js --minify --outfile=out/ours/$a.min.js >/dev/null; } 2>&1 | awk '/real/{print $2}'); d=$(node out/ours/$a.min.js 2>&1 | diff - out/esb/$a.expected | wc -l | tr -d ' '); printf '%-6s ours=%7s esbuild=%7s (%+.1f%%)  gz ours=%6s esbuild=%6s  stdout-diff=%s  %ss\n' $a $(wc -c < out/ours/$a.min.js) $(wc -c < out/esb/$a.min.js) $(( ($(wc -c < out/ours/$a.min.js) - $(wc -c < out/esb/$a.min.js)) * 100.0 / $(wc -c < out/esb/$a.min.js) )) $(gzip -c out/ours/$a.min.js | wc -c) $(gzip -c out/esb/$a.min.js | wc -c) $d $s; done
