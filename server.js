'use strict';
/* Denkwerkstatt-Server
   Liefert public/ aus und leitet KI-Anfragen an den gewählten Anbieter weiter.
   Die API-Schlüssel bleiben auf dem Server (Umgebungsvariablen), nie im Browser.
   Keine Abhängigkeiten, Node 18 oder neuer. Start: node server.js */
const http = require('http');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const E = process.env;
const PORT = Number(E.PORT) || 8080;
const PUB = path.join(__dirname, 'public');

const P = {
  anthropic: { key: E.ANTHROPIC_API_KEY, base: E.ANTHROPIC_BASE_URL || 'https://api.anthropic.com/v1' },
  openai: { key: E.OPENAI_API_KEY, base: E.OPENAI_BASE_URL || 'https://api.openai.com/v1' },
  google: { key: E.GEMINI_API_KEY, base: E.GEMINI_BASE_URL || 'https://generativelanguage.googleapis.com/v1beta' },
  mistral: { key: E.MISTRAL_API_KEY, base: E.MISTRAL_BASE_URL || 'https://api.mistral.ai/v1' },
  infomaniak: { key: E.INFOMANIAK_API_KEY, base: E.INFOMANIAK_BASE_URL || (E.INFOMANIAK_PRODUCT_ID ? 'https://api.infomaniak.com/1/ai/' + E.INFOMANIAK_PRODUCT_ID + '/openai' : '') },
  openrouter: { key: E.OPENROUTER_API_KEY, base: E.OPENROUTER_BASE_URL || 'https://openrouter.ai/api/v1' },
  compat: { key: E.COMPAT_API_KEY || '', base: E.COMPAT_BASE_URL || '', nokey: true }
};
const ready = id => !!(P[id] && P[id].base && (P[id].key || P[id].nokey));
const PROVIDERS = Object.keys(P).filter(ready);
const DEF = {
  provider: E.LLM_PROVIDER || PROVIDERS[0] || '',
  model: E.LLM_MODEL || '',
  fast: E.LLM_FAST_MODEL || E.LLM_MODEL || ''
};
const CHOICE = E.ALLOW_MODEL_CHOICE === '1';
const PASSWORD = E.APP_PASSWORD || '';
const ORIGINS = (E.ALLOWED_ORIGINS || '').split(',').map(s => s.trim().replace(/\/+$/, '')).filter(Boolean);
const PER_MIN = Number(E.RATE_LIMIT_PER_MIN) || 20;
const MAX_TOKENS = Number(E.MAX_OUTPUT_TOKENS) || 4000;
const MAX_INPUT = Number(E.MAX_INPUT_CHARS) || 120000;

const TYPES = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png', '.ico': 'image/x-icon', '.md': 'text/markdown; charset=utf-8' };

function send(res, status, body, headers) {
  const isObj = typeof body === 'object' && !Buffer.isBuffer(body);
  res.writeHead(status, Object.assign({ 'content-type': isObj ? 'application/json; charset=utf-8' : 'text/plain; charset=utf-8', 'x-content-type-options': 'nosniff' }, headers || {}));
  res.end(isObj ? JSON.stringify(body) : body);
}
function cors(req, res) {
  const o = (req.headers.origin || '').replace(/\/+$/, '');
  if (o && (ORIGINS.includes('*') || ORIGINS.includes(o))) {
    res.setHeader('access-control-allow-origin', ORIGINS.includes('*') ? '*' : o);
    res.setHeader('vary', 'origin');
    res.setHeader('access-control-allow-headers', 'content-type, x-app-password');
    res.setHeader('access-control-allow-methods', 'GET, POST, OPTIONS');
  }
}
function same(a, b) {
  const x = crypto.createHash('sha256').update(String(a)).digest(), y = crypto.createHash('sha256').update(String(b)).digest();
  return crypto.timingSafeEqual(x, y);
}
const hits = new Map();
function limited(ip) {
  const now = Date.now(), list = (hits.get(ip) || []).filter(t => now - t < 60000);
  list.push(now); hits.set(ip, list);
  if (hits.size > 5000) hits.clear();
  return list.length > PER_MIN;
}
function readBody(req, limit) {
  return new Promise((resolve, reject) => {
    let size = 0; const chunks = [];
    req.on('data', c => { size += c.length; if (size > limit) { reject(Object.assign(new Error('Anfrage zu gross'), { status: 413 })); req.destroy(); } else chunks.push(c); });
    req.on('end', () => resolve(Buffer.concat(chunks).toString('utf8')));
    req.on('error', reject);
  });
}

async function upstream(url, headers, body) {
  const r = await fetch(url, { method: 'POST', headers: Object.assign({ 'content-type': 'application/json' }, headers), body: JSON.stringify(body), signal: AbortSignal.timeout(180000) });
  const t = await r.text();
  if (!r.ok) {
    let m = t; try { const j = JSON.parse(t); m = (j.error && (j.error.message || j.error)) || j.message || j.detail || t; } catch (_) {}
    const e = new Error(String(typeof m === 'string' ? m : JSON.stringify(m)).slice(0, 300)); e.status = r.status; throw e;
  }
  return JSON.parse(t);
}
async function callModel(id, model, system, user) {
  const p = P[id], base = p.base.replace(/\/+$/, '');
  if (id === 'anthropic') {
    const j = await upstream(base + '/messages', { 'x-api-key': p.key, 'anthropic-version': '2023-06-01' }, { model, max_tokens: MAX_TOKENS, system, messages: [{ role: 'user', content: user }] });
    return (j.content || []).filter(c => c.type === 'text').map(c => c.text).join('');
  }
  if (id === 'google') {
    const j = await upstream(base + '/models/' + encodeURIComponent(model.replace(/^models\//, '')) + ':generateContent', { 'x-goog-api-key': p.key },
      { systemInstruction: { parts: [{ text: system }] }, contents: [{ role: 'user', parts: [{ text: user }] }], generationConfig: { responseMimeType: 'application/json', maxOutputTokens: MAX_TOKENS } });
    const c = (j.candidates || [])[0];
    return ((c && c.content && c.content.parts) || []).map(x => x.text || '').join('');
  }
  const h = p.key ? { authorization: 'Bearer ' + p.key } : {};
  const body = { model, messages: [{ role: 'system', content: system }, { role: 'user', content: user }], response_format: { type: 'json_object' } };
  let j;
  try { j = await upstream(base + '/chat/completions', h, body); }
  catch (e) { if (e.status !== 400 && e.status !== 422) throw e; delete body.response_format; j = await upstream(base + '/chat/completions', h, body); }
  const c = (j.choices || [])[0];
  return (c && c.message && c.message.content) || '';
}

async function handleLLM(req, res) {
  if (PASSWORD && !same(req.headers['x-app-password'] || '', PASSWORD)) return send(res, 401, { error: 'Zugangspasswort fehlt oder ist falsch.' });
  const ip = String(req.headers['x-forwarded-for'] || req.socket.remoteAddress || '').split(',')[0].trim();
  if (limited(ip)) return send(res, 429, { error: 'Zu viele Anfragen. Bitte einen Moment warten.' });
  let b;
  try { b = JSON.parse(await readBody(req, MAX_INPUT * 4 + 10000)); } catch (e) { return send(res, e.status || 400, { error: e.status ? e.message : 'Ungültige Anfrage.' }); }
  const system = String(b.system || ''), user = String(b.user || '');
  if (!user || system.length + user.length > MAX_INPUT) return send(res, 400, { error: 'Anfrage leer oder zu lang.' });
  let provider = DEF.provider, model = b.fast ? DEF.fast : DEF.model;
  if (CHOICE && b.provider) {
    if (!ready(b.provider)) return send(res, 400, { error: 'Dieser Anbieter ist auf dem Server nicht eingerichtet.' });
    provider = b.provider; if (b.model) model = String(b.model);
    else if (provider !== DEF.provider) return send(res, 400, { error: 'Bitte ein Modell für diesen Anbieter angeben.' });
  }
  if (!ready(provider) || !model) return send(res, 500, { error: 'Auf dem Server sind Anbieter oder Modell nicht eingerichtet (LLM_PROVIDER, LLM_MODEL).' });
  try {
    const text = await callModel(provider, model, system, user);
    send(res, 200, { text });
  } catch (e) {
    console.error('[llm]', provider, model, e.status || '', e.message);
    send(res, 502, { error: 'Anbieter-Fehler' + (e.status ? ' ' + e.status : '') + ': ' + e.message });
  }
}

function serveStatic(req, res) {
  let p = decodeURIComponent(new URL(req.url, 'http://x').pathname);
  if (p.endsWith('/')) p += 'index.html';
  const file = path.normalize(path.join(PUB, p));
  if (!file.startsWith(PUB + path.sep)) return send(res, 403, 'Verboten');
  fs.readFile(file, (err, data) => {
    if (err) return send(res, 404, 'Nicht gefunden');
    send(res, 200, data, { 'content-type': TYPES[path.extname(file)] || 'application/octet-stream', 'cache-control': 'no-cache' });
  });
}

http.createServer(async (req, res) => {
  try {
    const url = new URL(req.url, 'http://x').pathname;
    if (url.startsWith('/api/')) {
      cors(req, res);
      if (req.method === 'OPTIONS') { res.writeHead(204); return res.end(); }
      if (url === '/api/config' && req.method === 'GET') {
        return send(res, 200, { denkwerkstatt: 1, provider: DEF.provider, model: DEF.model, fast: DEF.fast, providers: CHOICE ? PROVIDERS : [], choice: CHOICE, password: !!PASSWORD });
      }
      if (url === '/api/llm' && req.method === 'POST') return await handleLLM(req, res);
      return send(res, 404, { error: 'Unbekannter Endpunkt.' });
    }
    if (req.method !== 'GET' && req.method !== 'HEAD') return send(res, 405, 'Methode nicht erlaubt');
    serveStatic(req, res);
  } catch (e) {
    console.error(e);
    if (!res.headersSent) send(res, 500, { error: 'Serverfehler.' });
  }
}).listen(PORT, () => {
  console.log('Denkwerkstatt läuft auf Port ' + PORT);
  console.log('Anbieter mit Schlüssel: ' + (PROVIDERS.join(', ') || 'keiner') + '. Vorgabe: ' + (DEF.provider || '-') + ' / ' + (DEF.model || 'kein Modell gesetzt'));
  if (!PASSWORD) console.warn('Hinweis: APP_PASSWORD ist nicht gesetzt. Wer die Adresse kennt, kann auf deine Kosten Anfragen stellen.');
});
