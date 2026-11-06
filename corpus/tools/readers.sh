#!/bin/zsh
# The languages' readers, compiled once as a native reader artifact, and its path printed.
# Coil compiles a source reader into every build that reads a DSL file, and keeps what each
# reading allocates until the build ends; with the artifact, a build reads the DSL files with
# precompiled code and frees each reading's memory. It is rebuilt only when the readers'
# sources, the compiler or the manifest change.
set -e
cd "$(dirname $0)/../../poc"
OUT=../corpus/out/readers
mkdir -p $OUT
# The artifact is keyed to the manifest too, all but its entry, which the build scripts change.
key=$( (cat $(command -v coil); grep -v '^entry = ' Coil.toml; find src/hl -name '*.coil' -o -name '*.syntax' -o -name '*.rules' -o -name '*.txt' | sort | xargs cat) | shasum -a 256 | cut -c1-16)
if [ -f $OUT/current-$key ]; then cat $OUT/current-$key; exit 0; fi
artifact=$(python3 ../corpus/tools/guard.py 9500 900 coil build-provider hl.readers read-any -o $OUT --meta-opt=2 | tail -1)
[ -d "$artifact" ] || { echo "readers.sh: the reader artifact did not build" >&2; exit 1; }
rm -f $OUT/current-*(N)
echo "$(cd "$artifact" && pwd)" > $OUT/current-$key
cat $OUT/current-$key
