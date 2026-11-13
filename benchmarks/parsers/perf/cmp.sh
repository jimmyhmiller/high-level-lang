#!/bin/bash
# Interleaved; totals over the list of each binary's best parse and best check (ms).
L=$1; R=$2; shift 2
for i in $(seq 1 $R); do for b in "$@"; do ./out/bin/$b bench $L 3 | awk -v b=$b '{print b, $2, $4, $6}'; done; done | python3 -c "
import sys,collections
best=collections.defaultdict(lambda: 10**12); chk=collections.defaultdict(lambda: 10**12)
for l in sys.stdin:
    b,f,t,c=l.split(); best[(b,f)]=min(best[(b,f)],int(t)); chk[(b,f)]=min(chk[(b,f)],int(c))
bins=list(dict.fromkeys(k[0] for k in best)); files=list(dict.fromkeys(k[1] for k in best))
for b in bins:
    p=sum(best[(b,f)] for f in files)/1000; c=sum(chk[(b,f)] for f in files)/1000
    ts=[f for f in files if 'typescript.js' in f][0]
    print(f'{b:16} parse {p:7.1f} ms  check {c:6.1f} ms  both {p+c:7.1f} ms   typescript.js parse {best[(b,ts)]/1000:.1f} check {chk[(b,ts)]/1000:.1f}')
"
