#!/bin/zsh
# usage: profile.sh ESB APP [TOP]: sample a long in-process run, print self time by function.
S="$(cd "$(dirname $0)/.." && pwd)/out/bin"; mkdir -p $S/mt
ESB=${1:A}
cd "$(dirname $0)/../tests"
$ESB apps/$2.js --minify --repeat=${4:-40} --outfile=$S/mt/p.js > /dev/null &
pid=$!
sleep 0.2
sample $pid 3 1 -mayDie -file $S/prof.txt > /dev/null 2>&1
kill $pid 2>/dev/null
python3 - <<PY
t=open("$S/prof.txt").read()
i=t.find("Sort by top of stack")
rows=[l.split() for l in t[i:].split("\n")[1:90] if "(in " in l]
rows=[r for r in rows if "__ulock_wait" not in r[0]]
total=sum(int(r[-1]) for r in rows)
print("samples",total)
for r in rows[:${3:-18}]:
    print(f"{int(r[-1])*100/total:5.1f}%  {r[0][:62]}")
PY
