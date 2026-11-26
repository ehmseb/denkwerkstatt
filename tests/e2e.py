#!/usr/bin/env python3
"""End-to-End-Test der Denkwerkstatt ohne echte KI.

Prüft alle drei Verbindungsarten mit simulierten Antworten:
  A  Claude-Modus (window.claude wird nachgebildet), Datei-Import, Lesen, Schreiben, Darstellung
  B  Server-Modus über server.js mit Passwort und Modellwahl
  C  Direktmodus mit eigenem Schlüssel gegen einen OpenAI-kompatiblen Mock
  D  Textauswahl auf Touch-Geräten bei 390 px

Vorbereitung (einmalig):
  cd tests && npm install
  pip install playwright python-docx && python -m playwright install chromium
Start:  python tests/e2e.py      (Exit-Code 0 = alles grün)
"""
import asyncio, json, os, socket, subprocess, sys, tempfile, time, urllib.request, urllib.error
from pathlib import Path
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent.parent
LIB = ROOT / 'tests' / 'node_modules'
PAGE = (ROOT / 'public' / 'index.html').as_uri()
MOCK_PORT, SRV_PORT = 9999, 8787
FAILS = []

def check(name, cond, info=''):
    print(('  ok      ' if cond else '  FEHLER  ') + name + ('' if cond or not info else f'  [{info}]'))
    if not cond:
        FAILS.append(name)

STUB = r"""
window.__calls = [];
window.claude = { use: async (n) => {
  if (n === 'downloads') return { save: async (o) => { window.__dl = o; } };
  if (n !== 'sample') return null;
  return async (prompt) => {
    window.__calls.push(prompt);
    const d = JSON.parse(prompt.match(/DATEN:\n\n([\s\S]*)$/)[1]); let r;
    if (prompt.includes('Landkarte')) r = { abschnitte: d.abschnitte.map(a => ({ id: a.id, titel: 'Titel ' + a.id, linse: 'Linse für ' + a.id })), anstoesse: [{ id: d.abschnitte[0].id, art: 'Frage', text: 'Was meinst du <b>dazu</b>?', schritt: 'Notiere es.' }, { id: 'xx', art: 'Spannung', text: 'Global', schritt: '' }] };
    else if (prompt.includes('Kernpunkte formuliert')) r = { getroffen: ['Punkt A'], luecken: [{ id: (d.abschnitte[1] || d.abschnitte[0]).id, text: 'Lücke hier', schritt: 'Lies nach' }], lesarten: [], frage: 'Wie sicher bist du?' };
    else if (prompt.includes('Formuliere den Abschnitt')) r = { text: 'Entwurfstext aus Stichworten.', offen: 'Beispiel fehlt.' };
    else if (prompt.includes('drei deutlich verschiedene')) r = { varianten: [{ label: 'knapper', text: 'V1' }, { label: 'anschaulich', text: 'V2' }, { label: 'sachlich', text: 'V3' }] };
    else if (prompt.includes('kritische Kollegin')) r = { anstoesse: [{ id: d.abschnitte[0].id, art: 'Gegenargument', text: 'Gegen', schritt: 'S' }] };
    else r = { anstoesse: [{ id: 'gesamt', art: 'Lücke', text: 'Schluss fehlt', schritt: 'Ergänze' }] };
    return { text: '```json\n' + JSON.stringify(r) + '\n```' };
  };
} };
"""

def make_fixtures(d: Path):
    (d / 't.txt').write_text('Erster Absatz einer Textdatei,\nder über zwei Zeilen geht.\n\nZweiter Absatz.\n', encoding='utf-8')
    (d / 't.md').write_text('# Titel\n\nEin **fetter** Absatz mit [Link](https://x.ch) und Text.\n\n- Punkt eins\n- Punkt zwei\n\n## Zweiter Teil\n\nNoch ein Absatz.\n', encoding='utf-8')
    stream = 'BT /F1 14 Tf 72 760 Td (Einleitung) Tj 0 -40 Td (Erster Absatz im PDF mit etwas Text.) Tj 0 -40 Td (Zweiter Absatz im PDF.) Tj ET'
    objs = ['<< /Type /Catalog /Pages 2 0 R >>', '<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
            '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>',
            f'<< /Length {len(stream)} >>\nstream\n{stream}\nendstream', '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>']
    pdf, offs = '%PDF-1.4\n', []
    for i, o in enumerate(objs):
        offs.append(len(pdf)); pdf += f'{i + 1} 0 obj\n{o}\nendobj\n'
    x = len(pdf)
    pdf += f'xref\n0 {len(objs) + 1}\n0000000000 65535 f \n' + ''.join(f'{o:010d} 00000 n \n' for o in offs) + f'trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{x}\n%%EOF'
    (d / 't.pdf').write_bytes(pdf.encode('latin-1'))
    try:
        import docx
        doc = docx.Document(); doc.add_heading('Zellatmung', 1); doc.add_paragraph('Absatz im Word-Dokument.'); doc.add_paragraph('Punkt', style='List Bullet'); doc.save(d / 't.docx')
    except ImportError:
        print('  (python-docx fehlt, Word-Import wird übersprungen)')

async def new_ctx(browser, stub=False):
    ctx = await browser.new_context(viewport={'width': 1280, 'height': 900}, accept_downloads=True)
    async def route(r):
        u = r.request.url
        if 'pdfjs-dist' in u: await r.fulfill(path=LIB / 'pdfjs-dist' / 'build' / u.split('/')[-1], content_type='text/javascript')
        elif 'mammoth' in u: await r.fulfill(path=LIB / 'mammoth' / 'mammoth.browser.min.js', content_type='text/javascript')
        elif 'fonts.g' in u: await r.abort()
        else: await r.continue_()
    await ctx.route('**/*', route)
    if stub: await ctx.add_init_script(STUB)
    return ctx

def watch(pg):
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    return errs

async def test_claude(browser, fx: Path):
    print('A  Claude-Modus')
    ctx = await new_ctx(browser, stub=True); pg = await ctx.new_page(); errs = watch(pg)
    await pg.goto(PAGE); await pg.wait_for_timeout(1500)
    check('KI-Anzeige zeigt Claude', 'Claude' in await pg.text_content('#ai'))
    for w in (1280, 720, 400):
        await pg.set_viewport_size({'width': w, 'height': 900})
        check(f'kein seitliches Scrollen bei {w}px', await pg.evaluate('document.documentElement.scrollWidth') <= w)
    await pg.set_viewport_size({'width': 1280, 'height': 900})
    # Schreiben mit Beispielinhalt
    await pg.click('.seg [data-v=schreiben]')
    await pg.locator('[data-part] [data-act=draft]').nth(1).click(); await pg.wait_for_timeout(300)
    check('Absatz aus Stichworten', await pg.evaluate("document.querySelectorAll('textarea.prose')[1].value") == 'Entwurfstext aus Stichworten.')
    await pg.locator('[data-part] [data-act=variants]').nth(0).click(); await pg.wait_for_timeout(300)
    check('drei Varianten', await pg.locator('.note.var').count() == 3)
    await pg.locator('[data-act=usevar]').nth(1).click(); await pg.wait_for_timeout(200)
    check('Variante übernommen', await pg.evaluate("document.querySelectorAll('textarea.prose')[0].value") == 'V2')
    await pg.click('[data-act=review]'); await pg.wait_for_timeout(300)
    check('Text prüfen liefert Denkanstösse', await pg.locator('.note.prov').count() >= 1)
    await pg.click('[data-act=outline]'); await pg.wait_for_timeout(300)
    check('Gliederung prüfen, Anstoss zum Ganzen', 'Schluss fehlt' in await pg.text_content('#globalprov'))
    await pg.click('#dlbtn'); await pg.wait_for_timeout(200)
    check('Download als .md', (await pg.evaluate('window.__dl && window.__dl.filename') or '').endswith('.md'))
    # Import
    await pg.click('.seg [data-v=lesen]')
    for f in ('t.txt', 't.md', 't.pdf', 't.docx'):
        if not (fx / f).exists(): continue
        await pg.set_input_files('#file', str(fx / f)); await pg.wait_for_timeout(1200)
        n = await pg.locator('.sec[data-sec]').count()
        check(f'Import {f}', n >= 1 and 'geladen' in (await pg.text_content('#msg') or ''), f'{n} Abschnitte')
        if f == 't.pdf':
            check('PDF-Text gelesen', 'Erster Absatz im PDF' in await pg.inner_text('#doc'))
    # Lesen
    await pg.fill('#purpose', 'Ich will verstehen, wie das geht'); await pg.click('[data-act=map]'); await pg.wait_for_timeout(400)
    check('Landkarte mit Linsen', await pg.locator('.lens').count() >= 1)
    check('KI-Text wird nicht als HTML eingefügt', '&lt;b&gt;dazu' in await pg.inner_html('#app'))
    await pg.evaluate("()=>{const t=document.querySelector('.txt p').firstChild;const r=document.createRange();r.setStart(t,0);r.setEnd(t,8);const s=getSelection();s.removeAllRanges();s.addRange(r);}")
    await pg.wait_for_timeout(400)
    check('Markier-Leiste erscheint bei Auswahl', await pg.is_visible('#selbar'))
    await pg.click('[data-act=selmark]'); await pg.wait_for_timeout(200)
    check('Markierung gesetzt', await pg.locator('mark').count() >= 1)
    await pg.fill('#kern', ' '.join(['wort'] * 30)); await pg.click('[data-act=compare]'); await pg.wait_for_timeout(400)
    check('Abgleich zeigt Gut erfasst', 'Gut erfasst' in await pg.text_content('[data-margin=fazit]'))
    await pg.locator('[data-act=take]').first.click(); await pg.fill('#dlgta', 'meine Notiz'); await pg.click('#dlgok'); await pg.wait_for_timeout(200)
    check('Aufgreifen erzeugt Notiz', await pg.locator('.note.mine').count() >= 2)
    await pg.locator('[data-act=drop]').first.click(); await pg.click('#dlgok'); await pg.wait_for_timeout(200)
    check('Verwerfen markiert Anstoss', await pg.locator('.note.done').count() >= 2)
    await pg.click('[data-act=level][data-v=stark]'); await pg.click('.seg [data-v=schreiben]')
    check('Stufe stark: keine Entwürfe', await pg.locator('[data-act=draft]').count() == 0)
    check('keine Skriptfehler', not errs, '; '.join(errs))
    await ctx.close()

SELECT = "()=>{const w=document.createTreeWalker(document.querySelector('#doc'),NodeFilter.SHOW_TEXT,{acceptNode:n=>n.parentElement.closest('.txt')&&!n.parentElement.closest('mark')&&n.length>=25?1:3});const t=w.nextNode();const r=document.createRange();r.setStart(t,0);r.setEnd(t,20);const s=getSelection();s.removeAllRanges();s.addRange(r);t.parentElement.dispatchEvent(new TouchEvent('touchend',{bubbles:true}));}"

async def test_touch(browser):
    print('D  Touch, 390 px')
    ctx = await browser.new_context(viewport={'width': 390, 'height': 844}, has_touch=True, is_mobile=True, device_scale_factor=1)
    await ctx.add_init_script(STUB); await ctx.route('**/fonts.g*/**', lambda r: r.abort())
    pg = await ctx.new_page(); errs = watch(pg)
    await pg.goto(PAGE); await pg.wait_for_timeout(1200)
    check('kein seitliches Scrollen bei 390px', await pg.evaluate('document.documentElement.scrollWidth') <= 390)
    marks = await pg.locator('mark').count()
    await pg.evaluate(SELECT); await pg.wait_for_timeout(400)
    check('Auswahlleiste nach touchend', await pg.is_visible('#selbar'))
    box = await pg.locator('#selbar').bounding_box(); hb = await pg.locator('[data-act=selmark]').bounding_box()
    check('Auswahlleiste im Bild, Knöpfe mindestens 44 px hoch', box and box['x'] >= 0 and box['x'] + box['width'] <= 390 and box['y'] + box['height'] <= 844 and hb['height'] >= 44, str(box))
    # Der Browser hebt die Auswahl beim Tippen auf die Leiste auf: Leiste bleibt mit der gemerkten Stelle
    await pg.locator('[data-act=selmark]').dispatch_event('pointerdown')
    await pg.evaluate('getSelection().removeAllRanges()'); await pg.wait_for_timeout(400)
    check('Leiste bleibt, wenn die Auswahl beim Tippen verschwindet', await pg.is_visible('#selbar'))
    await pg.tap('[data-act=selmark]'); await pg.wait_for_timeout(300)
    check('Markieren per Tippen', await pg.locator('mark').count() > marks and not await pg.is_visible('#selbar'))
    await pg.evaluate(SELECT); await pg.wait_for_timeout(400)
    await pg.locator('.dochead').dispatch_event('pointerdown')
    await pg.evaluate('getSelection().removeAllRanges()'); await pg.wait_for_timeout(400)
    check('Tippen daneben schliesst die Leiste', not await pg.is_visible('#selbar'))
    await pg.evaluate(SELECT); await pg.wait_for_timeout(400)
    await pg.locator('[data-act=selnote]').dispatch_event('pointerdown'); await pg.evaluate('getSelection().removeAllRanges()')
    await pg.tap('[data-act=selnote]'); await pg.fill('#dlgta', 'Notiz vom Handy'); await pg.tap('#dlgok'); await pg.wait_for_timeout(300)
    check('Notiz per Tippen', 'Notiz vom Handy' in await pg.inner_text('#app'))
    check('keine Skriptfehler', not errs, '; '.join(errs))
    await ctx.close()

def http(path, data=None, headers=None):
    req = urllib.request.Request(f'http://localhost:{SRV_PORT}{path}', data=json.dumps(data).encode() if data else None, headers=headers or {}, method='POST' if data else 'GET')
    try:
        with urllib.request.urlopen(req, timeout=10) as r: return r.status, r.read().decode()
    except urllib.error.HTTPError as e: return e.code, e.read().decode()

async def test_server(browser):
    print('B  Server-Modus')
    st, body = http('/api/config'); cfg = json.loads(body)
    check('/api/config', st == 200 and cfg.get('denkwerkstatt') == 1 and cfg.get('password') is True)
    check('ohne Passwort abgelehnt', http('/api/llm', {'system': 's', 'user': 'x'})[0] == 401)
    st, body = http('/api/llm', {'system': 's', 'user': 'x', 'fast': True}, {'x-app-password': 'geheim'})
    check('mit Passwort beantwortet', st == 200 and json.loads(body).get('text'))
    check('fremder Anbieter abgelehnt', http('/api/llm', {'system': 's', 'user': 'x', 'provider': 'mistral', 'model': 'm'}, {'x-app-password': 'geheim'})[0] == 400)
    ctx = await new_ctx(browser); pg = await ctx.new_page(); errs = watch(pg)
    await pg.goto(f'http://localhost:{SRV_PORT}/'); await pg.wait_for_timeout(1500)
    check('Seite erkennt Server', 'Server' in await pg.text_content('#ai'))
    await pg.click('[data-act=map]'); await pg.wait_for_timeout(800)
    check('fehlendes Passwort öffnet Einstellungen', await pg.is_visible('#kidlg'))
    await pg.fill('#ki-pw', 'geheim'); await pg.click('#ki-test'); await pg.wait_for_timeout(800)
    check('Verbindungstest grün', 'funktioniert' in await pg.text_content('#ki-status'))
    await pg.click('#ki-save'); await pg.click('[data-act=map]'); await pg.wait_for_timeout(800)
    check('Landkarte über Server', await pg.locator('.lens').count() >= 1)
    await pg.click('#ai'); await pg.wait_for_timeout(500)
    check('Modellwahl auf dem Server sichtbar', await pg.is_visible('#ki-sprov'))
    await pg.select_option('#ki-sprov', 'anthropic'); await pg.fill('#ki-smodel', 'claude-sonnet-5-5'); await pg.click('#ki-save'); await pg.wait_for_timeout(300)
    await pg.click('.seg [data-v=schreiben]'); await pg.click('[data-act=review]'); await pg.wait_for_timeout(800)
    check('Prüfen über gewählten Anbieter', await pg.locator('.note.prov').count() >= 1)
    check('keine Skriptfehler', not errs, '; '.join(errs))
    await ctx.close()

async def test_direct(browser):
    print('C  Direktmodus')
    ctx = await new_ctx(browser); pg = await ctx.new_page(); errs = watch(pg)
    await pg.goto(PAGE); await pg.wait_for_timeout(1500)
    await pg.click('[data-act=map]'); await pg.wait_for_timeout(500)
    check('ohne Einstellungen öffnet sich der Dialog', await pg.is_visible('#kidlg'))
    await pg.select_option('#ki-prov', 'compat'); await pg.fill('#ki-base', f'http://localhost:{MOCK_PORT}/v1')
    await pg.click('#ki-list'); await pg.wait_for_timeout(600)
    check('Modelle abrufen', '2 Modelle' in await pg.text_content('#ki-status'))
    await pg.fill('#ki-model', 'modell-a'); await pg.click('#ki-test'); await pg.wait_for_timeout(800)
    check('Verbindungstest grün', 'funktioniert' in await pg.text_content('#ki-status'))
    await pg.click('#ki-save'); await pg.click('[data-act=map]'); await pg.wait_for_timeout(800)
    check('Landkarte direkt', await pg.locator('.lens').count() >= 1)
    await pg.click('#ai'); await pg.fill('#ki-base', 'http://localhost:9/v1'); await pg.click('#ki-test'); await pg.wait_for_timeout(800)
    check('verständliche Meldung bei falscher Adresse', 'Keine Verbindung' in await pg.text_content('#ki-status'))
    check('keine Skriptfehler', not errs, '; '.join(errs))
    await ctx.close()

def wait_port(port, t=10):
    end = time.time() + t
    while time.time() < end:
        with socket.socket() as s:
            if s.connect_ex(('127.0.0.1', port)) == 0: return
        time.sleep(0.2)
    raise RuntimeError(f'Port {port} antwortet nicht')

async def main():
    if not (LIB / 'pdfjs-dist').exists():
        sys.exit('Bitte zuerst im Ordner tests "npm install" ausführen.')
    env = dict(os.environ, MOCK_PORT=str(MOCK_PORT), PORT=str(SRV_PORT), APP_PASSWORD='geheim', LLM_PROVIDER='compat', LLM_MODEL='modell-a', LLM_FAST_MODEL='modell-b',
               COMPAT_BASE_URL=f'http://localhost:{MOCK_PORT}/v1', ANTHROPIC_API_KEY='sk-test', ANTHROPIC_BASE_URL=f'http://localhost:{MOCK_PORT}/v1', ALLOW_MODEL_CHOICE='1', RATE_LIMIT_PER_MIN='200')
    procs = [subprocess.Popen(['node', str(ROOT / 'tests' / 'mock_upstream.js')], env=env, stderr=subprocess.DEVNULL),
             subprocess.Popen(['node', str(ROOT / 'server.js')], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)]
    try:
        wait_port(MOCK_PORT); wait_port(SRV_PORT)
        with tempfile.TemporaryDirectory() as td:
            fx = Path(td); make_fixtures(fx)
            async with async_playwright() as p:
                kw = {'args': ['--no-sandbox']}
                if os.environ.get('CHROME_PATH'): kw['executable_path'] = os.environ['CHROME_PATH']
                browser = await p.chromium.launch(**kw)
                await test_claude(browser, fx); await test_server(browser); await test_direct(browser); await test_touch(browser)
                await browser.close()
    finally:
        for pr in procs: pr.terminate()
    print(f'\n{len(FAILS)} Fehler' if FAILS else '\nAlles grün.')
    sys.exit(1 if FAILS else 0)

asyncio.run(main())
