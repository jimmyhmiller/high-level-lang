#!/bin/zsh
# Build the command-line bundler and the parser driver, each its own entry.
S="$(cd "$(dirname $0)/.." && pwd)/out/bin"; mkdir -p $S/mt
READERS=$("$(dirname $0)/readers.sh") || exit 1
cd "$(dirname $0)/.."
cp Coil.toml $S/Coil.tools.bak
for pair in esb:compiler/boot/esb.coil jsparse:compiler/boot/jsparse.coil spec:compiler/boot/app.coil langtest:compiler/boot/langtest.coil; do
  name=${pair%%:*}; file=${pair#*:}
  # -i.sed-bak: an in-place edit both BSD and GNU sed take.
  sed -i.sed-bak "s#^entry = .*#entry = \"$file\"#" Coil.toml && rm -f Coil.toml.sed-bak
  coil build ${1:--O1} --meta-opt=2 --reader-artifact $READERS -o $S/$name 2>&1 | grep -v '^wrote' | sed -E "s#$PWD/##g" | cut -c1-260
done
cp $S/Coil.tools.bak Coil.toml
