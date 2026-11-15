// A TanStack Start build served as srvx serves one: files of the client directory as they are, every
// other request to the server entry's `fetch`.
//
// usage: node tools/start-serve.mjs SERVER-ENTRY CLIENT-DIR [PORT]   (prints "listening on PORT")
import { createServer } from 'node:http';
import { readFile, stat } from 'node:fs/promises';
import { resolve, join, extname } from 'node:path';
import { pathToFileURL } from 'node:url';
import { Readable } from 'node:stream';

const entry = (await import(pathToFileURL(resolve(process.argv[2])).href)).default;
const client = resolve(process.argv[3]);
const types = { '.js': 'text/javascript', '.css': 'text/css', '.html': 'text/html', '.svg': 'image/svg+xml', '.png': 'image/png', '.ico': 'image/x-icon', '.json': 'application/json' };

const server = createServer(async (req, res) => {
  const url = new URL(req.url, 'http://localhost');
  const file = join(client, decodeURIComponent(url.pathname));
  if (file.startsWith(client + '/') && (await stat(file).then((s) => s.isFile(), () => false))) {
    res.writeHead(200, { 'content-type': types[extname(file)] ?? 'application/octet-stream' });
    res.end(await readFile(file));
    return;
  }
  const body = req.method === 'GET' || req.method === 'HEAD' ? undefined : Readable.toWeb(req);
  const request = new Request(new URL(req.url, `http://${req.headers.host}`), { method: req.method, headers: req.headers, body, duplex: 'half' });
  try {
    const response = await entry.fetch(request);
    const headers = {};
    response.headers.forEach((v, k) => { headers[k] = k in headers ? headers[k] + ', ' + v : v; });
    res.writeHead(response.status, headers);
    if (response.body) for await (const chunk of response.body) res.write(chunk);
    res.end();
  } catch (e) {
    res.writeHead(500, { 'content-type': 'text/plain' });
    res.end(String(e && e.stack || e));
  }
});
server.listen(Number(process.argv[4] ?? 0), '127.0.0.1', () => console.log('listening on ' + server.address().port));
