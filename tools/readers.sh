#!/bin/zsh
# The languages' readers, compiled once as a native reader artifact, and its path printed.
# Coil compiles a source reader into every build that reads a DSL file, and keeps what each
# reading allocates until the build ends; with the artifact, a build reads the DSL files with
# precompiled code and frees each reading's memory. It is rebuilt only when the readers'
# sources, the compiler or the manifest change.
set -euo pipefail
cd "$(dirname $0)/.."
OUT=out/readers
mkdir -p $OUT
# The artifact is keyed to the manifest too, all but its entry, which the build scripts change.
key=$( (cat "$(command -v coil)"; grep -v '^entry = ' Coil.toml; find compiler/hl src/languages -name '*.coil' -o -name '*.syntax' -o -name '*.rules' -o -name '*.txt' | sort | xargs cat) | shasum -a 256 | cut -c1-16)
# The cached path must still be there: the output directory may have moved.
if [ -f $OUT/current-$key ] && [ -d "$(cat $OUT/current-$key)" ]; then cat $OUT/current-$key; exit 0; fi
reader_log=$(mktemp "$OUT/build.XXXXXX")
trap 'rm -f "$reader_log"' EXIT
if python3 tools/guard.py 9500 900 coil build-provider hl.readers read-any -o "$OUT" --meta-opt=2 > "$reader_log"; then
  artifact=$(tail -1 "$reader_log")
else
  reader_status=$?
  cat "$reader_log" >&2
  exit "$reader_status"
fi
[ -d "$artifact" ] || { echo "readers.sh: the reader artifact did not build" >&2; exit 1; }
rm -f $OUT/current-*(N)
echo "$(cd "$artifact" && pwd)" > $OUT/current-$key
cat $OUT/current-$key
