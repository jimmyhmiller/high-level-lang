import lldb, sys, collections
# usage: python3 trace.py BINARY FUNCTION NTH ARGS... (run with PYTHONPATH=$(lldb -P), /usr/bin/python3)
# Single-steps the NTH call of FUNCTION and counts instructions per function; the call sequence goes to trace.py.seq.
# Slow (~25 steps/s): use a tiny input, e.g. a file of four short statements, and NTH=3.
STOP = set(('bundle.js.parse-working','bundle.js.rep-Stmt','bundle.js.p-Block','bundle.js.p-Program-alt0'))
binp, func, nth = sys.argv[1], sys.argv[2], int(sys.argv[3]); args = sys.argv[4:]
dbg = lldb.SBDebugger.Create(); dbg.SetAsync(False)
t = dbg.CreateTarget(binp)
bp = t.BreakpointCreateByName(func)
p = t.LaunchSimple(args, None, '.')
th = None
for i in range(nth):
    if i: p.Continue()
th = [x for x in p.threads if x.GetStopReason() == lldb.eStopReasonBreakpoint][0]
p.SetSelectedThread(th)
bp.SetEnabled(False)
fr = th.GetFrameAtIndex(0); sp0 = fr.GetSP(); depth0 = th.GetNumFrames()
counts = collections.Counter(); seq=[]
n = 0
while True:
    f = th.GetFrameAtIndex(0)
    name = f.GetSymbol().GetName() or f.GetFunctionName() or '?'
    counts[name] += 1; n += 1
    if not seq or seq[-1][0] != name: seq.append([name,1])
    else: seq[-1][1]+=1
    th.StepInstruction(False)
    if n > 50 and name in STOP: break
    if n > 30000: break
print('TOTAL', n)
for k, v in counts.most_common(60): print(f'{v:6} {k}')
open(sys.argv[0] + '.seq', 'w').write('\n'.join(f'{c:5} {n}' for n,c in seq))
