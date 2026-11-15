// TanStack Start's server in development, as esb runs it (tanstack.start): the browser's files and
// the project's public/ served as they are, every other request answered by the server build's
// `fetch`. The build is imported again whenever esb has written a new one (SERVER-DIR/build holds
// its number, written after its other files), so each request is answered by the latest build.
// It ends when esb does.
//
// usage: node host.mjs SERVER-DIR CLIENT-DIR PUBLIC-DIR PORT
import { createServer } from 'node:http';
import { readFile, stat } from 'node:fs/promises';
import { join, extname } from 'node:path';
import { pathToFileURL } from 'node:url';
import { Readable } from 'node:stream';

const [serverDir, clientDir, publicDir, port] = process.argv.slice(2);
const types = {
  '.js': 'text/javascript', '.mjs': 'text/javascript', '.css': 'text/css', '.html': 'text/html', '.json': 'application/json',
  '.svg': 'image/svg+xml', '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.gif': 'image/gif',
  '.webp': 'image/webp', '.ico': 'image/x-icon', '.txt': 'text/plain', '.woff': 'font/woff', '.woff2': 'font/woff2',
};

let loaded = { build: null, entry: null };
async function entry() {
  const build = (await readFile(join(serverDir, 'build'), 'utf8')).trim();
  if (build !== loaded.build) {
    const mod = await import(pathToFileURL(join(serverDir, 'server.js')).href + '?build=' + build);
    loaded = { build, entry: mod.default };
  }
  return loaded.entry;
}

async function file(dir, pathname) {
  const f = join(dir, decodeURIComponent(pathname));
  return f.startsWith(dir + '/') && (await stat(f).then((s) => s.isFile(), () => false)) ? f : null;
}

const server = createServer(async (req, res) => {
  const url = new URL(req.url, 'http://localhost');
  const found = (await file(clientDir, url.pathname)) ?? (await file(publicDir, url.pathname));
  if (found) {
    res.writeHead(200, { 'content-type': types[extname(found)] ?? 'application/octet-stream', 'cache-control': 'no-cache' });
    res.end(await readFile(found));
    return;
  }
  try {
    const handler = await entry();
    const body = req.method === 'GET' || req.method === 'HEAD' ? undefined : Readable.toWeb(req);
    const request = new Request(new URL(req.url, `http://${req.headers.host}`), { method: req.method, headers: req.headers, body, duplex: 'half' });
    const response = await handler.fetch(request);
    const headers = {};
    response.headers.forEach((v, k) => { headers[k] = k in headers ? headers[k] + ', ' + v : v; });
    res.writeHead(response.status, headers);
    if (response.body) for await (const chunk of response.body) res.write(chunk);
    res.end();
  } catch (e) {
    console.error('[tanstack-start] SSR error:', e);
    if (!res.headersSent) res.writeHead(500, { 'content-type': 'text/plain' });
    res.end(String((e && e.stack) || e));
  }
});
server.listen(Number(port), () => console.log('[tanstack-start] listening on http://localhost:' + server.address().port));

// esb started this process; when esb ends, so does it.
const parent = process.ppid;
setInterval(() => { if (process.ppid !== parent) process.exit(0); }, 500);
