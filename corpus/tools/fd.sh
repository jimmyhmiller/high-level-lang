#!/bin/zsh
# Show the first normalized difference for each line "orig | ... | printed" on stdin.
cd "$(dirname $0)/.."
while IFS='|' read -r f m o; do f=${f// /}; o=${o// /}; [[ $f == pass/* ]] && f=vendor/test262-parser-tests/$f; echo "--- ${f##*/}"; node tools/firstdiff.cjs "$f" "$o" 2>&1 | head -3 | cut -c1-140; done
