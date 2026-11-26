#!/usr/bin/env python3
"""Echttest der Denkwerkstatt mit einem echten Sprachmodell.

Startet server.js mit Anbieter, Modell und Schlüssel aus Umgebungsvariablen, öffnet die Seite
per Playwright im Server-Modus und durchläuft auf jeder Stufe alle KI-Funktionen mit dem Text
aus tests/fixtures/. Jede Antwort wird automatisch gegen die Regeln geprüft.

Umgebungsvariablen (Schlüssel nie ins Repo):
  LIVE_PROVIDER     anthropic (Vorgabe), mistral, openai, google, infomaniak, openrouter, compat
  LIVE_MODEL        Hauptmodell, Vorgabe für anthropic: claude-sonnet-5-5
  LIVE_FAST_MODEL   Schnellmodell (Varianten), Vorgabe für anthropic: claude-haiku-5-5
  <ANBIETER>_API_KEY, zum Beispiel ANTHROPIC_API_KEY oder MISTRAL_API_KEY
  LIVE_SERVER_URL   optional: bestehenden Server nutzen (z. B. Railway) statt server.js zu starten
  LIVE_APP_PASSWORD Zugangspasswort für LIVE_SERVER_URL
  LIVE_LEVELS       Vorgabe: leicht,mittel,stark
  LIVE_OUT          Ordner für Rohantworten, Vorgabe tests/.live (nicht im Repo)

Start:  python tests/live_check.py
Exit-Code: 0 alle Prüfungen bestanden, 1 Regelverstösse, 2 Lauf abgebrochen.
"""
import asyncio, json, os, re, socket, subprocess, sys, time
from datetime import date
from pathlib import Path
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / 'tests' / 'fixtures'
LIB = ROOT / 'tests' / 'node_modules'
DOC = FIX / 'wald-und-klima.md'
INP = json.loads((FIX / 'live-eingaben.json').read_text(encoding='utf-8'))
PORT = 8790

PROVIDER = os.environ.get('LIVE_PROVIDER', 'anthropic')
DEFAULTS = {'anthropic': ('claude-sonnet-5-5', 'claude-haiku-5-5'), 'mistral': ('mistral-large-latest', 'mistral-small-latest')}
MODEL = os.environ.get('LIVE_MODEL') or DEFAULTS.get(PROVIDER, ('', ''))[0]
FAST = os.environ.get('LIVE_FAST_MODEL') or DEFAULTS.get(PROVIDER, ('', ''))[1] or MODEL
KEYVAR = {'anthropic': 'ANTHROPIC_API_KEY', 'openai': 'OPENAI_API_KEY', 'google': 'GEMINI_API_KEY', 'mistral': 'MISTRAL_API_KEY',
          'infomaniak': 'INFOMANIAK_API_KEY', 'openrouter': 'OPENROUTER_API_KEY', 'compat': 'COMPAT_API_KEY'}
REMOTE = os.environ.get('LIVE_SERVER_URL', '').rstrip('/')
LEVELS = [s.strip() for s in os.environ.get('LIVE_LEVELS', 'leicht,mittel,stark').split(',') if s.strip()]
OUT = Path(os.environ.get('LIVE_OUT') or ROOT / 'tests' / '.live')
TIMEOUT = 240000

# ---------- Prüfungen ----------
ABBR = re.compile(r'\b(z|d|u|v|s|vgl|bzw|ca|evtl|usw|etc|Nr|Abs|Kap|inkl|sog|bspw|resp|Mio|Mrd|Jh|Dr|Prof|St)\.', re.I)

def sentences(t):
    t = ABBR.sub(lambda m: m.group(0)[:-1] + '\u2024', str(t))      # Abkürzungspunkte schützen
    t = re.sub(r'(\d)\.(\d)', '\\1\u2024\\2', t)                    # 1.5
    t = re.sub(r'(\d)\.\s', '\\1\u2024 ', t)                        # Ordinalzahlen: 3. Klasse
    parts = [p.strip() for p in re.split(r'(?<=[.!?])\s+(?=[«"„A-ZÄÖÜ0-9\[])', t.strip()) if p.strip()]
    return parts

def prompts(task, j):
    """Liefert alle Denkanstösse einer Antwort als Liste von dicts mit text und schritt."""
    if not isinstance(j, dict): return []
    if task == 'abgleich': return [x for k in ('luecken', 'lesarten') for x in (j.get(k) or []) if isinstance(x, dict)]
    if task in ('karte', 'pruefen', 'gliederung'): return [x for x in (j.get('anstoesse') or []) if isinstance(x, dict)]
    return []

def all_strings(o):
    if isinstance(o, str): yield o
    elif isinstance(o, dict):
        for v in o.values(): yield from all_strings(v)
    elif isinstance(o, list):
        for v in o: yield from all_strings(v)

DASH = re.compile(r'[\u2013\u2014]|\s-\s')

def evaluate(task, level, raw):
    r = {'json': False, 'json_tolerant': False, 'n': 0, 'saetze': None, 'schritt': None, 'fragen': None, 'sz': None, 'striche': None, 'details': []}
    j = None
    try: j = json.loads(raw); r['json'] = True
    except Exception:
        s = re.sub(r'^\s*```(?:json)?\s*|```\s*$', '', raw.strip())
        a, b = s.find('{'), s.rfind('}')
        try: j = json.loads(s[a:b + 1]) if a >= 0 and b > a else None
        except Exception: j = None
    r['json_tolerant'] = j is not None
    if j is None:
        r['details'].append('kein JSON lesbar'); return r, None
    ps = prompts(task, j); r['n'] = len(ps)
    if ps:
        long = [p.get('text', '') for p in ps if len(sentences(p.get('text', ''))) > 2]
        r['saetze'] = not long
        r['details'] += [f'mehr als zwei Sätze: {t}' for t in long]
        miss = [p.get('text', '') for p in ps if not str(p.get('schritt', '')).strip()]
        r['schritt'] = not miss
        r['details'] += [f'ohne schritt: {t}' for t in miss]
    if level == 'stark':
        qs = [p.get('text', '') for p in ps]
        if task == 'karte': qs += [a.get('linse', '') for a in (j.get('abschnitte') or []) if isinstance(a, dict)]
        if task == 'abgleich' and j.get('frage'): qs.append(j['frage'])
        if qs:
            bad = [q for q in qs if not all(s.endswith('?') for s in sentences(q))]
            r['fragen'] = not bad
            r['details'] += [f'keine reine Frage: {q}' for q in bad]
    strs = list(all_strings(j))
    sz = [s for s in strs if 'ß' in s]
    r['sz'] = not sz; r['details'] += [f'ß: {s[:80]}' for s in sz]
    st = [s for s in strs if DASH.search(s)]
    r['striche'] = not st; r['details'] += [f'Gedankenstrich: {DASH.search(s).group(0)!r} in {s[:100]}' for s in st]
    return r, j

# ---------- Ablauf ----------
def wait_port(port, t=15):
    end = time.time() + t
    while time.time() < end:
        with socket.socket() as s:
            if s.connect_ex(('127.0.0.1', port)) == 0: return
        time.sleep(0.2)
    raise RuntimeError(f'Port {port} antwortet nicht')

def server_env():
    env = {k: v for k, v in os.environ.items() if not re.match(r'^(ANTHROPIC|OPENAI|GEMINI|MISTRAL|INFOMANIAK|OPENROUTER|COMPAT|LLM)_', k)}
    env.update(PORT=str(PORT), LLM_PROVIDER=PROVIDER, LLM_MODEL=MODEL, LLM_FAST_MODEL=FAST, RATE_LIMIT_PER_MIN='500', APP_PASSWORD='')
    key = os.environ.get(KEYVAR[PROVIDER], '')
    if key: env[KEYVAR[PROVIDER]] = key
    for k in (PROVIDER.upper() + '_BASE_URL', 'INFOMANIAK_PRODUCT_ID'):
        if os.environ.get('LIVE_' + k): env[k] = os.environ['LIVE_' + k]
    return env

async def new_page(browser):
    ctx = await browser.new_context(viewport={'width': 1280, 'height': 900})
    async def route(r):
        u = r.request.url
        if 'pdfjs-dist' in u and (LIB / 'pdfjs-dist').exists(): await r.fulfill(path=LIB / 'pdfjs-dist' / 'build' / u.split('/')[-1], content_type='text/javascript')
        elif 'mammoth' in u and (LIB / 'mammoth').exists(): await r.fulfill(path=LIB / 'mammoth' / 'mammoth.browser.min.js', content_type='text/javascript')
        elif 'fonts.g' in u: await r.abort()
        else: await r.continue_()
    await ctx.route('**/*', route)
    pw = os.environ.get('LIVE_APP_PASSWORD', '')
    if pw: await ctx.add_init_script(f"try{{sessionStorage.setItem('dw-key-server', {json.dumps(pw)})}}catch(e){{}}")
    return ctx, await ctx.new_page()

RESULTS = []

async def step(pg, level, name, action):
    """Löst eine Funktion aus und hält Anfrage und Antwort von /api/llm fest."""
    t0 = time.time()
    try:
        async with pg.expect_response(lambda r: r.url.endswith('/api/llm'), timeout=TIMEOUT) as info:
            await action()
        resp = await info.value
        req = json.loads(resp.request.post_data or '{}')
        body = await resp.json()
        await pg.wait_for_timeout(400)
        uimsg = (await pg.text_content('#msg') or '').strip()
    except Exception as e:
        uimsg = (await pg.text_content('#msg') or '').strip()
        RESULTS.append({'level': level, 'name': name, 'task': '', 'error': f'keine Antwort: {e.__class__.__name__}; Meldung: {uimsg}'})
        print(f'  FEHLER  {level:6} {name}: keine Antwort ({uimsg})'); return
    dt = time.time() - t0
    if resp.status != 200:
        RESULTS.append({'level': level, 'name': name, 'task': req.get('task', ''), 'error': f'HTTP {resp.status}: {body.get("error", "")}', 'sek': dt})
        print(f'  FEHLER  {level:6} {name}: HTTP {resp.status} {body.get("error", "")}'); return
    raw = body.get('text', '')
    ev, j = evaluate(req.get('task', ''), level, raw)
    RESULTS.append({'level': level, 'name': name, 'task': req.get('task', ''), 'fast': req.get('fast', False), 'sek': round(dt, 1), 'eval': ev,
                    'raw': raw, 'parsed': j, 'ui': uimsg, 'user': req.get('user', '')})
    ok = all(v is not False for k, v in ev.items() if k not in ('n', 'details', 'json'))
    print(f'  {"ok    " if ok else "REGEL "}  {level:6} {name:22} {dt:5.1f} s  {ev["n"]} Anstösse' + ('' if ev['json'] else '  (JSON nur tolerant lesbar)' if ev['json_tolerant'] else '  (kein JSON)'))
    for d in ev['details']: print('            ' + d[:160])

async def run_level(browser, base, level):
    print(f'Stufe {level}')
    ctx, pg = await new_page(browser)
    errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.goto(base + '/'); await pg.wait_for_timeout(1500)
    await pg.click(f'[data-act=level][data-v={level}]')
    await pg.click('.tools [data-act=reset]'); await pg.wait_for_timeout(300)
    await pg.set_input_files('#file', str(DOC)); await pg.wait_for_timeout(1200)
    L = INP['lesen']
    await pg.fill('#purpose', L['leseziel']); await pg.fill('#lens', L['linse'])
    await step(pg, level, 'Landkarte', lambda: pg.click('[data-act=map]'))
    await pg.fill('#kern', L['kernpunkte'])
    await step(pg, level, 'Abgleich', lambda: pg.click('[data-act=compare]'))
    # Schreiben
    W = INP['schreiben']
    await pg.click('.seg [data-v=schreiben]'); await pg.wait_for_timeout(300)
    while await pg.locator('[data-part]').count() < len(W['parts']):
        await pg.click('[data-act=addpart]'); await pg.wait_for_timeout(150)
    await pg.fill('#wt', W['titel']); await pg.fill('#wz', W['ziel']); await pg.fill('#wp', W['publikum']); await pg.fill('#wk', W['kern'])
    for i, p in enumerate(W['parts']):
        part = pg.locator('[data-part]').nth(i)
        await part.locator('input.h').fill(p['h']); await part.locator('textarea.stich').fill(p['stich']); await part.locator('textarea.prose').fill(p['text'])
    if level != 'stark':
        await step(pg, level, 'Absatz (Abschnitt 2)', lambda: pg.locator('[data-part]').nth(1).locator('[data-act=draft]').click())
        await step(pg, level, 'Absatz (Abschnitt 3)', lambda: pg.locator('[data-part]').nth(2).locator('[data-act=draft]').click())
    await step(pg, level, 'Varianten', lambda: pg.locator('[data-part]').nth(0).locator('[data-act=variants]').click())
    await step(pg, level, 'Text prüfen', lambda: pg.click('[data-act=review]'))
    await step(pg, level, 'Gliederung prüfen', lambda: pg.click('[data-act=outline]'))
    if errs: print('  Skriptfehler: ' + '; '.join(errs))
    await ctx.close()

def mark(v): return '' if v is None else ('ja' if v else '**nein**')

def table():
    rows = ['| Stufe | Funktion | Sek. | JSON | Anstösse | ≤ 2 Sätze | «schritt» | nur Fragen | kein ß | keine Striche |', '|---|---|---|---|---|---|---|---|---|---|']
    for r in RESULTS:
        if 'error' in r:
            rows.append(f"| {r['level']} | {r['name']} | | **Fehler** | | | | | | |"); continue
        e = r['eval']
        js = 'ja' if e['json'] else ('tolerant' if e['json_tolerant'] else '**nein**')
        rows.append(f"| {r['level']} | {r['name']} | {r['sek']} | {js} | {e['n']} | {mark(e['saetze'])} | {mark(e['schritt'])} | {mark(e['fragen'])} | {mark(e['sz'])} | {mark(e['striche'])} |")
    return '\n'.join(rows)

async def main():
    if not MODEL: sys.exit('LIVE_MODEL fehlt.')
    if not REMOTE and PROVIDER != 'compat' and not os.environ.get(KEYVAR[PROVIDER]):
        sys.exit(f'{KEYVAR[PROVIDER]} fehlt. Den Schlüssel in der Shell setzen, nie ins Repo schreiben.')
    proc = None
    if REMOTE: base = REMOTE
    else:
        proc = subprocess.Popen(['node', str(ROOT / 'server.js')], env=server_env(), stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        wait_port(PORT); base = f'http://localhost:{PORT}'
    print(f'Echttest: {PROVIDER} / {MODEL} (schnell: {FAST}) über {base}')
    try:
        async with async_playwright() as p:
            kw = {'args': ['--no-sandbox']}
            if os.environ.get('CHROME_PATH'): kw['executable_path'] = os.environ['CHROME_PATH']
            browser = await p.chromium.launch(**kw)
            for lv in LEVELS: await run_level(browser, base, lv)
            await browser.close()
    finally:
        if proc:
            proc.terminate()
            err = proc.stderr.read() if proc.stderr else ''
            if err.strip(): print('Server-Log:\n' + err.strip()[:2000])
    OUT.mkdir(parents=True, exist_ok=True)
    stamp = f'{date.today().isoformat()}-{PROVIDER}-{time.strftime("%H%M%S")}'
    meta = {'provider': PROVIDER, 'model': MODEL, 'fast': FAST, 'server': base, 'datum': date.today().isoformat()}
    (OUT / f'{stamp}.json').write_text(json.dumps({'meta': meta, 'results': RESULTS}, ensure_ascii=False, indent=1), encoding='utf-8')
    (OUT / f'{stamp}-tabelle.md').write_text(table() + '\n', encoding='utf-8')
    print('\n' + table())
    print(f'\nRohantworten: {OUT / (stamp + ".json")}')
    if any('error' in r for r in RESULTS): sys.exit(2)
    bad = [r for r in RESULTS if any(v is False for k, v in r['eval'].items() if k not in ('n', 'details', 'json'))]
    print(f'{len(bad)} von {len(RESULTS)} Antworten mit Regelverstoss.' if bad else 'Alle Antworten regelkonform.')
    sys.exit(1 if bad else 0)

asyncio.run(main())
