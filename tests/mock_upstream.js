// Simulierter KI-Anbieter für die Tests: OpenAI-kompatibel (/v1/chat/completions, /v1/models)
// und Anthropic (/v1/messages). Antwortet je nach Aufgabe mit passendem JSON.
const http = require('http');
const PORT = Number(process.env.MOCK_PORT) || 9999;
function answer(user) {
  const m = String(user).match(/DATEN:\n\n([\s\S]*)$/);
  if (!m) return { ok: true };
  const d = JSON.parse(m[1]);
  if (user.includes('Landkarte')) return { abschnitte: d.abschnitte.map(a => ({ id: a.id, titel: 'Titel ' + a.id, linse: 'Linse ' + a.id })), anstoesse: [{ id: d.abschnitte[0].id, art: 'Frage', text: 'Server-Anstoss', schritt: 'Tu was' }] };
  if (user.includes('kritische Kollegin')) return { anstoesse: [{ id: d.abschnitte[0].id, art: 'Lücke', text: 'Prüfanstoss', schritt: 'S' }] };
  return { ok: true };
}
http.createServer((req, res) => {
  let b = '';
  req.on('data', c => { b += c; });
  req.on('end', () => {
    res.setHeader('access-control-allow-origin', '*');
    res.setHeader('access-control-allow-headers', '*');
    if (req.method === 'OPTIONS') { res.writeHead(204); return res.end(); }
    if (req.url.split('?')[0].endsWith('/models')) return res.end(JSON.stringify({ data: [{ id: 'modell-a' }, { id: 'modell-b' }] }));
    let j = {};
    try { j = JSON.parse(b || '{}'); } catch (e) {}
    console.error('UPSTREAM', req.url, j.model);
    if (req.url.endsWith('/messages')) return res.end(JSON.stringify({ content: [{ type: 'text', text: JSON.stringify(answer(j.messages[0].content)) }] }));
    const u = (j.messages || []).find(x => x.role === 'user') || { content: '' };
    res.end(JSON.stringify({ choices: [{ message: { content: JSON.stringify(answer(u.content)) } }] }));
  });
}).listen(PORT, () => console.error('Mock-Anbieter auf Port ' + PORT));
