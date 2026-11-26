# Startprompt für Claude Code

Zum Einfügen in eine neue Claude-Code-Sitzung im Repo `ehmseb/denkwerkstatt`.

---

Du übernimmst das Projekt «Denkwerkstatt» im Repo `ehmseb/denkwerkstatt`. Es ist ein Lese- und Schreibwerkzeug, das mit Denkanstössen am Rand das eigene Denken trainiert statt es abzunehmen.

**Einstieg**
1. Falls der Pull Request «Übergabe an Claude Code» (Branch `uebergabe-claude-code`) noch nicht gemergt ist, arbeite von diesem Branch aus.
2. Lies `CLAUDE.md` und `docs/uebergabe-2026-11-26.md`. Lies dann in `public/index.html` vor allem `RULES`, `LEVEL`, `TASK`, `buildPrompt` und `callLLM`, und lies `server.js`.
3. Richte die Tests ein und führe `python tests/e2e.py` aus. Melde mir kurz, ob alles grün ist und ob dir beim Lesen etwas Wichtiges aufgefallen ist.

Arbeite danach die Aufgaben der Reihe nach ab. Nach jeder Aufgabe: kurzer Bericht an mich, ein Pull Request, dann wartest du auf mein OK.

**Aufgabe 1: Echttest mit einem echten Modell**
- Baue `tests/live_check.py`. Das Skript startet `server.js` mit Anbieter, Modell und Schlüssel aus Umgebungsvariablen, die ich in der Shell setze. Schlüssel kommen nie ins Repo. Dann öffnet es die Seite per Playwright im Server-Modus.
- Lege unter `tests/fixtures/` einen realistischen, selbst geschriebenen Text an: etwa zwei Seiten Biologie oder Chemie auf Gymnasialstufe, mit Überschriften und mindestens einer strittigen Aussage.
- Durchlaufe damit auf allen drei Stufen: Landkarte, Abgleich (mit selbst formulierten Kernpunkten, die eine Lücke enthalten), Absatz aus Stichworten, Varianten, Text prüfen, Gliederung prüfen.
- Prüfe automatisch:
  - gültiges JSON,
  - höchstens zwei Sätze je Denkanstoss,
  - Feld «schritt» vorhanden,
  - auf Stufe «stark» nur Fragen,
  - kein ß,
  - keine Gedankenstriche.
- Prüfe von Hand eine Stichprobe darauf, ob die Absatz-Entwürfe nichts erfinden, das nicht in den Stichworten steht.
- Lege das Ergebnis als `docs/tests/live-JJJJ-MM-TT.md` ab: Tabelle plus deine Einschätzung auf höchstens einer Seite. Rohantworten nicht ins Repo.
- Frag mich vor dem Lauf nach Anbieter und Modell und nenne die ungefähre Zahl der Modellaufrufe.
- Schlag danach konkrete Änderungen an `RULES`, `LEVEL` und `TASK` vor. Setz sie nach meinem OK um und lass genau einen zweiten Lauf zum Vergleich laufen.

**Aufgabe 2: Server auf Railway (nur nach meinem OK)**
- Lege ein Projekt aus diesem Repo an. Startbefehl ist `npm start`, Healthcheck `/api/config`.
- Setze nur Variablen, die keine Geheimnisse sind. Schlüssel und `APP_PASSWORD` trage ich selbst ein.
- Erzeuge eine Domain und prüfe `/api/config`.
- Lass den Echttest aus Aufgabe 1 einmal mit Mistral über diesen Server laufen und vergleiche mit Anthropic.

**Aufgabe 3: Lücken im Werkzeug** (je ein PR, jeweils mit neuen Prüfungen in `tests/e2e.py`)
- Export von Notizen und Kernpunkten aus dem Lesemodus (Markdown, kopieren und herunterladen).
- Mehrere Dokumente oder Projekte statt eines einzigen Zustands, mit Liste, Umbenennen und Löschen über eigene Dialoge.
- Textauswahl auf Touch-Geräten (Auswahlleiste bei `touchend`, testen in 390 px Breite).
- Bessere Behandlung sehr langer Dokumente, zum Beispiel die Landkarte in Teilen erstellen statt kürzen.

**Aufgabe 4: GymiMate**
Im Repo `ehmseb/ehmsebots` änderst du nichts. Entwirf ein Konzept für den Denkpartner-Schalter im Chat und den Baustein Lesen und Schreiben zuerst nur im Chat mit mir. Ins Repo kommt es nur, wenn ich «halte das fest» sage, und dann nach den Regeln in dessen `CLAUDE.md`.

**Grundsätze**
- Halte dich an `CLAUDE.md`: eine HTML-Datei ohne Build, GymiMate-Design, Schweizer Rechtschreibung, Binnen-I, keine Gedankenstriche, kein Geheimnis im Repo.
- Berichte ehrlich, was getestet ist und was nicht.
- Bei Unklarheiten frag nach, statt zu raten.
