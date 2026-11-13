#!/bin/bash
# Instructions retired (load-independent) by each binary: `bench LIST 1`, so 2 untimed parses + 1 timed parse and one check, per file.
L=$1; shift
for b in "$@"; do /usr/bin/time -l ./out/bin/$b bench $L 1 2>&1 >/dev/null | awk -v b=$b '/instructions retired/{printf "%-22s %6.2f G instructions\n", b, $1/1e9}'; done
