#!/bin/zsh
# usage: prof.sh BINARY ARGS...: sample a run, print self-time by function.
S=/private/tmp/claude-501/-Users-jimmyhmiller-Documents-Code-projects-high-level-lang/42c609f3-96d2-4d12-b20e-26987dd12610/scratchpad
B=$1; shift
n=${B:t}
sample $n 3 1 -wait -mayDie -file $S/prof.txt >/dev/null 2>&1 &
pid=$!
sleep 0.3
for i in 1 2 3 4 5 6 7 8; do $B "$@" >/dev/null 2>&1; done
wait $pid
python3 - <<PY
import re
t=open("$S/prof.txt").read()
i=t.find("Sort by top of stack")
rows=[l.split() for l in t[i:].split("\n")[1:60] if "(in " in l]
for r in rows[:${TOP:-22}]:
    print(f"{r[-1]:>6}  {r[0][:60]}")
PY
