import http from 'node:http';
import { createReadStream, statSync, existsSync } from 'node:fs';
import { extname, join, normalize, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = dirname(fileURLToPath(import.meta.url));
const port = Number(process.env.PORT || 8000);

const mime = new Map([
  ['.html', 'text/html; charset=utf-8'], ['.htm', 'text/html; charset=utf-8'],
  ['.js', 'text/javascript; charset=utf-8'], ['.mjs', 'text/javascript; charset=utf-8'],
  ['.css', 'text/css; charset=utf-8'], ['.json', 'application/json; charset=utf-8'],
  ['.svg', 'image/svg+xml'], ['.png', 'image/png'], ['.jpg', 'image/jpeg'], ['.jpeg', 'image/jpeg'],
  ['.webp', 'image/webp'], ['.gif', 'image/gif'], ['.ico', 'image/x-icon'],
  ['.woff', 'font/woff'], ['.woff2', 'font/woff2'], ['.ttf', 'font/ttf'],
  ['.mp4', 'video/mp4'], ['.webm', 'video/webm'], ['.mov', 'video/quicktime'],
  ['.mp3', 'audio/mpeg'], ['.wav', 'audio/wav'], ['.wasm', 'application/wasm'],
  ['.bin', 'text/x-component; charset=utf-8']
]);

const csp = [
  "default-src 'self' data: blob:",
  "script-src 'self' 'unsafe-inline' 'unsafe-eval' blob:",
  "style-src 'self' 'unsafe-inline' data:",
  "img-src 'self' data: blob:",
  "media-src 'self' data: blob:",
  "font-src 'self' data:",
  "connect-src 'self'",
  "worker-src 'self' blob:",
  "frame-src 'self'",
  "object-src 'none'",
  "base-uri 'self'"
].join('; ');

function safePath(pathname) {
  let decoded;
  try { decoded = decodeURIComponent(pathname); } catch { return null; }
  const clean = normalize(decoded).replace(/^([/\\])+/, '');
  if (clean.startsWith('..') || clean.includes('\0')) return null;
  return clean;
}

function isFile(path) {
  try { return existsSync(path) && statSync(path).isFile(); } catch { return false; }
}

function resolveRequest(url) {
  const relative = safePath(url.pathname);
  if (relative === null) return null;
  const noSlash = relative.replace(/[/\\]+$/, '');

  if (url.searchParams.has('_rsc')) {
    const rsc = noSlash || 'index';
    const candidates = [
      join(root, `${rsc}__q_ab30ca0235.bin`),
      join(root, rsc, 'index__q_ab30ca0235.bin')
    ];
    for (const p of candidates) if (isFile(p)) return p;
  }

  const candidates = [];
  if (!relative) candidates.push(join(root, 'index.html'));
  if (relative) candidates.push(join(root, relative));
  if (noSlash && noSlash !== relative) candidates.push(join(root, noSlash));
  if (noSlash) candidates.push(join(root, noSlash, 'index.html'));
  if (noSlash && !extname(noSlash)) candidates.push(join(root, `${noSlash}.html`));

  for (const p of candidates) if (isFile(p)) return p;

  if (/^(?:_next|__external__|__sitecloner|images|matter|capture)(?:\/|$)/.test(relative)) return null;
  return join(root, 'index.html');
}

const server = http.createServer((req, res) => {
  const url = new URL(req.url || '/', 'http://localhost');
  const path = resolveRequest(url);

  res.setHeader('Content-Security-Policy', csp);
  res.setHeader('X-Content-Type-Options', 'nosniff');
  res.setHeader('Referrer-Policy', 'no-referrer');

  if (!path || !isFile(path)) {
    res.statusCode = 404;
    res.setHeader('Content-Type', 'text/plain; charset=utf-8');
    res.end('Not found');
    return;
  }

  const stat = statSync(path);
  let type = mime.get(extname(path).toLowerCase());
  if (!type && !extname(path)) type = 'text/html; charset=utf-8';
  res.setHeader('Content-Type', type || 'application/octet-stream');
  res.setHeader('Accept-Ranges', 'bytes');

  const range = req.headers.range;
  if (range) {
    const match = /^bytes=(\d*)-(\d*)$/.exec(range);
    if (match) {
      let start = match[1] ? Number(match[1]) : 0;
      let end = match[2] ? Number(match[2]) : stat.size - 1;
      if (!match[1] && match[2]) {
        const suffix = Number(match[2]);
        start = Math.max(0, stat.size - suffix);
        end = stat.size - 1;
      }
      if (Number.isFinite(start) && Number.isFinite(end) && start <= end && end < stat.size) {
        res.statusCode = 206;
        res.setHeader('Content-Range', `bytes ${start}-${end}/${stat.size}`);
        res.setHeader('Content-Length', end - start + 1);
        createReadStream(path, { start, end }).pipe(res);
        return;
      }
    }
    res.statusCode = 416;
    res.setHeader('Content-Range', `bytes */${stat.size}`);
    res.end();
    return;
  }

  res.setHeader('Content-Length', stat.size);
  createReadStream(path).pipe(res);
});

server.listen(port, '127.0.0.1', () => {
  console.log(`KOTA local server: http://127.0.0.1:${port}`);
});
