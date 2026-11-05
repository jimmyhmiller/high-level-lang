#!/bin/zsh
# Build the command-line bundler and the parser driver, each its own entry.
S=/private/tmp/claude-501/-Users-jimmyhmiller-Documents-Code-projects-high-level-lang/42c609f3-96d2-4d12-b20e-26987dd12610/scratchpad
cd ~/Documents/Code/projects/high-level-lang/poc
cp Coil.toml $S/Coil.tools.bak
for pair in esb:src/tools/esb.coil jsparse:src/tools/jsparse.coil; do
  name=${pair%%:*}; file=${pair#*:}
  sed -i '' "s#^entry = .*#entry = \"$file\"#" Coil.toml
  coil build ${1:--O1} -o $S/$name 2>&1 | grep -v '^wrote' | sed -E "s#$PWD/##g" | cut -c1-260
done
cp $S/Coil.tools.bak Coil.toml
cp $S/esb $S/esb3
