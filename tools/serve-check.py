#!/usr/bin/env python3
"""Check that the shared HTTP runtime serves events at its caller's chosen path."""
import http.client
import json
from pathlib import Path
import subprocess
import time

import guard


ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / "out" / "serve-check"
WORK.mkdir(parents=True, exist_ok=True)
(WORK / "port.txt").unlink(missing_ok=True)
(WORK / "asset.txt").write_text("static asset\n")
(WORK / "Coil.toml").write_text(
    '[package]\nname = "serve-check"\nentry = "main.coil"\n'
    f'source-roots = [{json.dumps(str(ROOT / "compiler"))}]\n'
)
(WORK / "main.coil").write_text('''(module serve-check)
(import "hl.rt" :as rt)
(import "coil.time" :use [sleep Duration])

(defn main [(argc i32) (argv (ptr (ptr i8)))] (-> i64)
  (let [port (rt/serve! 0 "." "fallback page" "/events/custom")]
    (rt/write-output "port.txt" (rt/num-text port))
    (while true
      (when (> (rt/listeners) 0) (rt/broadcast! "tick" "custom route"))
      (sleep (Duration :sec 0 :nsec 10000000)))
    0))
''')
code, stdout, stderr, _, _ = guard.run(
    ["coil", "build", "-O1", "-o", "server"], 9500, 300, quiet=True, cwd=WORK
)
if code:
    raise SystemExit(stdout + stderr)

server = subprocess.Popen([str(WORK / "server")], cwd=WORK)
connections = []
try:
    deadline = time.monotonic() + 10
    while True:
        try:
            port = int((WORK / "port.txt").read_text())
            break
        except (FileNotFoundError, ValueError):
            pass
        if server.poll() is not None or time.monotonic() >= deadline:
            raise RuntimeError("server did not publish its port")
        time.sleep(0.01)

    def get(path):
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        connections.append(connection)
        connection.request("GET", path)
        return connection.getresponse()

    response = get("/")
    assert response.status == 200 and response.read() == b"fallback page"
    print("ok   fallback page")
    response = get("/asset.txt")
    assert response.status == 200 and response.read() == b"static asset\n"
    print("ok   static file")
    response = get("/hmr")
    assert response.status == 200 and response.getheader("Content-Type").startswith("text/html") and response.read() == b"fallback page"
    print("ok   /hmr is not reserved by the runtime: a path of no file and no extension is a page of the app")
    response = get("/missing.js")
    assert response.status == 404
    response.read()
    print("ok   a file that is not there is not found")
    response = get("/events/custom?client=probe")
    assert response.status == 200
    assert response.getheader("Content-Type") == "text/event-stream"
    lines = [response.readline() for _ in range(5)]
    assert lines == [b": hello\n", b"\n", b"event: tick\n", b"data: custom route\n", b"\n"], lines
    print("ok   custom event path receives broadcasts, including with a query string")
finally:
    for connection in connections:
        connection.close()
    server.terminate()
    try:
        server.wait(timeout=5)
    except subprocess.TimeoutExpired:
        server.kill()
        server.wait()
