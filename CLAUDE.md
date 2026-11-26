# Arbeitsregeln für dieses Repository

Die Denkwerkstatt ist ein Lese- und Schreibwerkzeug mit Denkanstössen am Rand, ohne Chat. Sie soll das eigene Denken trainieren, statt es abzunehmen (nach Advait Sarkar, «AI should challenge, not obey»). Hintergrund, Stand und offene Aufgaben: `docs/uebergabe-2026-11-26.md`.

## Aufbau

- `public/index.html`: das ganze Werkzeug in **einer** Datei (HTML, CSS, JavaScript), ohne Build-Schritt.
- `server.js`: kleiner Node-Server ohne Abhängigkeiten. Liefert `public/` aus und leitet KI-Anfragen weiter (`/api/config`, `/api/llm`). Schlüssel nur aus Umgebungsvariablen.
- `tests/e2e.py`: End-to-End-Test aller drei Verbindungsarten mit simulierten Antworten. `tests/mock_upstream.js`: simulierter Anbieter.
- `tests/live_check.py`: Echttest mit einem echten Modell und dem Text aus `tests/fixtures/`. Läuft lokal mit Schlüssel aus der Shell oder über den Workflow `.github/workflows/live-check.yml` (nur von Hand, Schlüssel als Repository-Secret). Rohantworten nie ins Repo.
- `.github/workflows/pages.yml`: veröffentlicht `public/` bei jedem Push auf `main` nach https://ehmseb.github.io/denkwerkstatt/.

## Feste Vorgaben

- **Eine Datei bleibt eine Datei.** `public/index.html` muss auch als Claude-Artefakt laufen. Dort sind nur Skripte von cdnjs, jsdelivr und unpkg erlaubt, keine Anfragen an fremde Server und keine Browser-Dialoge (`alert`, `confirm`, `prompt`). Dialoge sind eigene `<dialog>`-Elemente.
- **KI-Antworten sind Text, nie HTML.** Alles aus Modell, Datei oder Speicher geht durch `esc()` oder `textContent`.
- **Drei Verbindungsarten** bleiben erhalten: Claude (Artefakt-Fähigkeit `sample`), eigener Schlüssel direkt aus dem Browser, eigener Server. `window.DENKWERKSTATT` (endpoint, stufe, modi, speicher, kontext) ist die Schnittstelle für den späteren Einbau in GymiMate.
- **Design nach GymiMate** (`ehmseb/ehmsebots`, Ordner `/design`): IBM Plex Sans, Grössen 24/20/16/14/13, Gewicht 600 statt 700; Farben Canvas `#f7f6f0`, Surface `#fff`, Ink `#17211b`, Muted `#52605a`, Line `#dfe6e1`, Brand `#176b4a` als einziger Akzent, Mint `#e7f4ed` sparsam, Selection `#bfe3d0` für Markierungen; Radien 4/6/8 px, Schatten nur für Dialoge und schwebende Leisten; keine Cards ohne eigenständiges Objekt, keine Emojis, kein Dunkelmodus.
- **Sprache in sichtbaren Texten:** Schweizer Rechtschreibung (ss statt ß), Gendern mit Binnen-I («SchülerInnen»), keine Gedankenstriche, kurze klare Sätze.
- **Didaktik:** Die KI liefert Denkanstösse, keine fertigen Lösungen. Regeln dafür stehen in `RULES`, `LEVEL` und `TASK` in `public/index.html` und in `docs/denkpartner-skill.md`. Änderungen daran mit echten Modellantworten prüfen, nicht nur mit dem Mock.

## Ablauf

- Nicht direkt auf `main` arbeiten: Branch, Commit, Pull Request. Ein Thema pro PR.
- Vor jedem PR: `python tests/e2e.py` muss grün sein. Neue Funktionen bekommen dort eigene Prüfungen.
- **Keine Schlüssel oder Passwörter ins Repo**, auch nicht in Tests, Berichte oder Logs. Echte Schlüssel nur über Umgebungsvariablen.
- Vor allem, was Geld kostet oder nach aussen wirkt (Deployments, Railway-Projekte, grössere Läufe mit echten Modellen), den Betreiber fragen.
- Das Repo `ehmseb/ehmsebots` (GymiMate) hat eigene, strengere Regeln in seiner `CLAUDE.md`. Dort nichts ändern ohne ausdrücklichen Auftrag.

## Tests ausführen

```
cd tests && npm install && cd ..
pip install playwright python-docx && python -m playwright install chromium
python tests/e2e.py
```
