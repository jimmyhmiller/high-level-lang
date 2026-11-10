#!/usr/bin/env python3
"""Build the paired React demo, write its server model, and optionally serve it locally."""
import argparse
import functools
import http.server
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--serve", action="store_true")
parser.add_argument("--port", type=int, default=8000)
args = parser.parse_args()
subprocess.run([str(ROOT / "out/bin/spec"), "../examples/client-server.bundler"], cwd=ROOT / "tests", check=True)
output = ROOT / "out/client-server"
public = output / "public"
model = subprocess.check_output(
    ["node", "-e", "process.stdout.write(JSON.stringify(require('./server.cjs').page()))"], cwd=output
)
(public / "model.json").write_bytes(model)
shutil.copyfile(ROOT / "examples/client-server.html", public / "index.html")
print(f"Demo built at {output}", flush=True)
if args.serve:
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(public))
    with http.server.ThreadingHTTPServer(("127.0.0.1", args.port), handler) as server:
        print(f"http://127.0.0.1:{server.server_port}", flush=True)
        server.serve_forever()
