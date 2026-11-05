#!/bin/zsh
# Round-trip every corpus list through esbuild. usage: rt.sh PARSER SCRATCH
P=$1; S=$2; cd "$(dirname $0)/.."
for set in pass es lo; do rm -rf out/rt-$set; mkdir -p out/rt-$set; $P printall $S/$set.list out/rt-$set; printf '%s: ' $set; node tools/roundtrip.mjs $S/$set.list out/rt-$set --show ${3:-6} 2>&1 | sed 's#vendor/test262-parser-tests/##' | cut -c1-170; done
