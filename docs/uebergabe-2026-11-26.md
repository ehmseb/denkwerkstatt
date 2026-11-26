# Übergabe Denkwerkstatt, 26.11.2026

Übergabe aus einer Claude-Chat-Sitzung an Claude Code. Enthält Zusammenfassung, Bericht, Entscheidungen und offene Aufgaben.

## Zusammenfassung

- **Ziel:** KI soll beim Lesen und Schreiben das eigene Denken trainieren statt es abzunehmen. Ausgangspunkt war Advait Sarkars TED-Vortrag «How to stop AI from killing your critical thinking» (TEDAI Vienna 2025).
- **Entstanden sind drei Dinge:**
  1. ein Claude-Skill **«denkpartner»** für den Chat (im Konto des Betreibers gespeichert, Text in `docs/denkpartner-skill.md`);
  2. die **Denkwerkstatt** (dieses Repo): Lese- und Schreibwerkzeug ohne Chat, Denkanstösse stehen am Rand des Dokuments;
  3. als Nebenprodukt eine Modellwahl im Korrektur-Widget des Betreibers (eigene Datei, nicht in diesem Repo).
- **Stand:** Funktional fertig, live auf https://ehmseb.github.io/denkwerkstatt/ und als privates Claude-Artefakt. Alle Funktionen sind mit simulierten Antworten getestet (`tests/e2e.py`, 41 Prüfungen grün). **Mit einem echten Sprachmodell lief die Denkwerkstatt noch nie.** Das ist die wichtigste offene Aufgabe.

## Bericht

### Hintergrund und Forschungsbasis

Sarkar (Microsoft Research Cambridge) beschreibt, wie Menschen durch KI zu «middle managers for our own thoughts» werden, und schlägt KI als Provokateur vor: Werkzeuge, die Gegenargumente, Alternativen und Fragen liefern, statt Ergebnisse. Sein Prototyp arbeitet ohne Chatfenster, mit Linsen, Denkanstössen im Text und einer selbst gebauten Gliederung. Drei Prinzipien: nah am Material bleiben, produktive Reibung, Metakognition stützen.

Weitere Befunde, die in die Gestaltung eingeflossen sind:
- Lee, Sarkar et al. (CHI 2025, 319 Wissensarbeitende): Mehr Vertrauen in die KI geht mit weniger kritischem Denken einher, mehr Selbstvertrauen mit mehr. Folge: Die Denkwerkstatt meldet ehrlich zurück, was gut gelungen ist («Gut erfasst», Denkanstoss-Art «Stärke»).
- Drosos, Sarkar et al. (2025, n=24): Kurze, spezifische Provokationen fördern Reflexion; generische, offensichtliche oder warnungsartige Hinweise werden ignoriert. Folge: höchstens zwei Sätze, immer ein nächster Schritt, keine Warnoptik, Verwerfen ist ausdrücklich erlaubt.
- Bastani et al. (PNAS 2025, rund 1000 GymnasiastInnen): KI ohne Leitplanken wird zur Krücke, mit Hinweisen statt Lösungen bleibt der Lerneffekt. Folge: Stufe «stark» ohne Entwürfe, nur Fragen.
- Kosmyna et al. (MIT 2025, Preprint, kleine Stichprobe): Erst selbst, dann KI führt zu besserer Erinnerung als umgekehrt. Folge: eigene Kernpunkte vor dem Abgleich, eigene Stichworte vor dem Entwurf.

Quellen: TED https://www.ted.com/talks/advait_sarkar_how_to_stop_ai_from_killing_your_critical_thinking · Sarkar https://advait.org · Microsoft Research Tools for Thought https://www.microsoft.com/en-us/research/project/tools-for-thought/ · Lee et al. https://doi.org/10.1145/3706598.3713778 · Drosos et al. https://arxiv.org/abs/2501.17247 · Bastani et al. https://doi.org/10.1073/pnas.2422633122 · Kosmyna et al. https://arxiv.org/abs/2506.08872 · Sarkar «AI Should Challenge, Not Obey» https://doi.org/10.1145/3649404

### Was die Denkwerkstatt kann

**Lesen**
- Import: PDF mit Textebene (pdf.js), .docx (mammoth), .txt, .md, eingefügter Text. Gliederung in höchstens 45 Abschnitte.
- Leseziel und Linse, dann «Landkarte»: Titel und eine Linse pro Abschnitt (je nach Stufe Hinweis oder Frage), keine Zusammenfassung, dazu wenige Denkanstösse am Rand.
- Markieren und Notieren per Auswahl, Notizen am Rand und in der Seitenleiste.
- Eigene Kernpunkte, erst danach Abgleich mit dem Text: «Gut erfasst», Lücken und andere Lesarten am Rand der betreffenden Abschnitte, eine Reflexionsfrage.

**Schreiben**
- Auftrag (Titel, Wirkung, Publikum, Kernaussage), Gliederung mit eigenen Stichworten pro Abschnitt.
- «Absatz aus meinen Stichworten» (fehlt etwas, setzt die KI [Klammern] statt zu erfinden), «Varianten» (drei Fassungen, auch für markierte Stellen), «Text prüfen» und «Gliederung prüfen», auf Wunsch automatisch beim Schreiben (höchstens alle 90 s).
- Material aus dem Lesen per Klick in die Stichworte.
- Abschluss: Zählung der aufgegriffenen und verworfenen Denkanstösse, Anteil übernommener KI-Wörter, drei Reflexionsfragen, Export als Markdown.

**Allgemein**
- Stufen leicht, mittel, stark. Jeder Denkanstoss lässt sich aufgreifen oder (begründet) verwerfen.
- Zustand nur im Browser (localStorage), Beispielinhalt beim ersten Öffnen.
- KI-Verbindung über den Knopf «KI»:
  - Claude (wenn als Claude-Artefakt geöffnet),
  - eigener Schlüssel direkt aus dem Browser: Anthropic, OpenAI, Gemini, OpenRouter, lokal/OpenAI-kompatibel (Ollama, LM Studio); Mistral und Infomaniak sind auswählbar, blockieren aber Browser-Anfragen,
  - eigener Server (`server.js`), auf Wunsch mit Anbieter- und Modellwahl.
  - Haupt- und Schnellmodell, «Modelle abrufen», «Speichern und testen».
- Design nach dem GymiMate-Designsystem (siehe `CLAUDE.md`).

### Server (`server.js`)

Node 18+, keine Abhängigkeiten. Endpunkte `GET /api/config` und `POST /api/llm` (`{task, system, user, fast, provider?, model?}` → `{text}`). Schutz: `APP_PASSWORD` (Header `x-app-password`, zeitkonstanter Vergleich), Rate-Limit pro IP, Grössenlimits, CORS nur für `ALLOWED_ORIGINS`, Pfadprüfung beim Ausliefern. Alle Variablen in `.env.example` und `README.md`. **Noch nicht auf Railway deployt.**

### Getestet und nicht getestet

- Getestet (`tests/e2e.py`, simulierte Antworten): alle Funktionen in allen drei Verbindungsarten, Import aller Formate, Escaping von KI-Text, kein seitliches Scrollen bei 400, 720 und 1280 px, Server-Schutz.
- Live geprüft: GitHub-Pages-Seite lädt mit IBM Plex Sans, PDF- und Word-Bibliothek.
- **Nicht getestet:** Antworten echter Modelle (Qualität der Denkanstösse, Zuverlässigkeit des JSON-Formats, besonders bei Mistral), Textauswahl per Finger auf dem Handy, Railway.

### Entscheidungen

- Repo öffentlich, weil GitHub Pages im Gratis-Konto nur so läuft. Im Code stehen keine Geheimnisse.
- Eine HTML-Datei ohne Build, damit sie gleichzeitig auf Pages, auf Railway, als Claude-Artefakt und später in GymiMate läuft.
- Design nach GymiMate statt eigenem Stil, damit der spätere Einbau keine Umgestaltung braucht. Kein Dunkelmodus, weil GymiMate keinen hat.
- Der Schlüssel im Browser ist nur für den Betreiber selbst gedacht. Für SchülerInnen gehört er auf einen Server.

## Offene Aufgaben (nach Priorität)

1. **Echttest mit einem richtigen Modell.** Einen realistischen Unterrichtstext durch alle Funktionen und alle drei Stufen schicken, Antworten gegen die Regeln prüfen: höchstens zwei Sätze, spezifisch statt allgemein, Feld «schritt» vorhanden, auf «stark» nur Fragen, gültiges JSON, ss statt ß, keine Gedankenstriche, keine erfundenen Fakten im Absatz-Entwurf. Danach `RULES`, `LEVEL` und `TASK` in `public/index.html` gezielt nachschärfen. Zuerst Anthropic, danach Mistral (dafür braucht es den Server).
2. **Railway.** Projekt aus diesem Repo anlegen, Variablen setzen (Schlüssel und Passwort trägt der Betreiber selbst ein), Domain erzeugen, prüfen.
3. **Lücken im Werkzeug:** Export der Notizen und Kernpunkte aus dem Lesemodus; mehrere Dokumente oder Projekte statt einem einzigen Zustand; Textauswahl auf Touch-Geräten; Umgang mit sehr langen Dokumenten (heute ab 60'000 Zeichen gekürzt); gescannte PDFs und Links nur mit Server.
4. **Einbau in GymiMate** (Repo `ehmseb/ehmsebots`, dort gelten dessen Regeln): zuerst ein Konzept unter `docs/konzepte/`, nur auf ausdrücklichen Wunsch. Themen: Denkpartner-Schalter im Chat (Systemprompt-Zusatz, Stufe 2 mit Testprogramm), eigener Baustein Lesen und Schreiben über `window.DENKWERKSTATT.endpoint`, Datenschutz (Texte von SchülerInnen über Infomaniak gemäss DPA).
5. **Wirkung prüfen:** kleiner Versuch mit einer Klasse, Auswertung der Zählungen und Reflexionsantworten.

## Wo was liegt

- Live: https://ehmseb.github.io/denkwerkstatt/
- Repo: https://github.com/ehmseb/denkwerkstatt
- Claude-Artefakt (privat, Claude-Modus): https://claude.ai/artifact/KrN9E33WxzXhUv4ETQ72Pu. Wird nicht automatisch aus dem Repo aktualisiert.
- Skill «denkpartner»: im Claude-Konto des Betreibers, Text in `docs/denkpartner-skill.md`.
