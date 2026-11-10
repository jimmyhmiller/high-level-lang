#!/usr/bin/env python3
"""Build the Workbench acceptance app from its declarative spec and optionally serve it."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
ROOT = Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--spec', default=str(ROOT / 'out/bin/spec'))
parser.add_argument('--serve', action='store_true')
parser.add_argument('--port', type=int, default=8000)
args = parser.parse_args()
subprocess.run([str(Path(args.spec).resolve()), '../examples/workbench.bundler'], cwd=ROOT / 'tests', check=True)
shutil.copyfile(ROOT / 'examples/workbench.html', ROOT / 'out/workbench/public/index.html')
(ROOT / 'out/workbench/package.json').write_text('{"type":"module"}\n')
print('Built out/workbench; run python3 tools/workbench.py --serve', flush=True)
if args.serve:
    env = {**os.environ, 'PORT': str(args.port)}
    subprocess.run(['node', '--enable-source-maps', 'out/workbench/server.mjs'], cwd=ROOT, env=env, check=True)
