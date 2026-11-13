#!/bin/bash
# Cycles and instructions (min of 3 runs) of `bench LIST 3` for each binary.
L=$1; shift
for b in "$@"; do for i in 1 2 3; do /usr/bin/time -l ./out/bin/$b bench $L 3 2>&1 >/dev/null | awk '/instructions retired/{i=$1}/cycles elapsed/{c=$1}END{print c, i}'; done | sort -n | head -1 | awk -v b=$b '{printf "%-14s %6.2f G cycles %6.2f G instructions  IPC %.2f\n", b, $1/1e9, $2/1e9, $2/$1}'; done
