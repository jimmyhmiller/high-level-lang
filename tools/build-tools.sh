#!/bin/zsh
# Build each entry explicitly. A failed compiler or output filter fails the script; the project
# manifest is never edited, so an interrupted build cannot leave its entry changed.
# HL_TOOLS_OUT: another directory for the binaries (the audit build's, say).
set -euo pipefail
TOOLS_ROOT=$(cd "$(dirname "$0")/.." && pwd)
TOOLS_OUTPUT="${HL_TOOLS_OUT:-$TOOLS_ROOT/out/bin}"
mkdir -p "$TOOLS_OUTPUT"
READERS=$("$TOOLS_ROOT/tools/readers.sh")
cd "$TOOLS_ROOT"
for pair in esb:compiler/boot/esb.coil jsparse:compiler/boot/jsparse.coil spec:compiler/boot/app.coil langtest:compiler/boot/langtest.coil runtime-check:compiler/boot/runtime-check.coil; do
  name=${pair%%:*}
  file=${pair#*:}
  coil build "$file" "${1:--O1}" --meta-opt=2 --reader-artifact "$READERS" -o "$TOOLS_OUTPUT/$name" 2>&1 |
    sed -E "/^wrote /d; s#$TOOLS_ROOT/##g" | cut -c1-260
done
