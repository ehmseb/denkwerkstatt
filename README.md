# Denkwerkstatt

Lesen und Schreiben mit Denkanstössen am Rand, ohne Chat. Nach Advait Sarkars Ansatz «AI should challenge, not obey» (TEDAI Vienna 2025).

- **Lesen:** Leseziel und Linse festlegen, Landkarte statt Zusammenfassung, eigene Markierungen und Notizen, dann eigene Kernpunkte und erst danach der Abgleich mit dem Text.
- **Schreiben:** eigene Gliederung und Stichworte, Absätze nur aus den eigenen Stichworten, Varianten zur Auswahl, Denkanstösse zum Entwurf, Reflexion am Schluss.
- **Stufen:** leicht, mittel, stark (sokratisch, ohne Entwürfe).
- **Projekte:** mehrere Projekte mit je einem Lesedokument und einem eigenen Text, mit Liste, Umbenennen und Löschen. Gespeichert wird nur im Browser.
- **Dateien:** PDF mit Textebene, .docx, .txt, .md. Sie werden im Browser gelesen; an die KI gehen nur Textabschnitte, und erst wenn du eine Funktion auslöst.

## Aufbau

```
public/index.html   das ganze Werkzeug, eine einzige Datei
server.js           kleiner Server: liefert public/ aus und leitet KI-Anfragen weiter
.env.example        Vorlage für die Umgebungsvariablen des Servers
.github/workflows/pages.yml   veröffentlicht public/ auf GitHub Pages
tests/              End-to-End-Test mit simulierten KI-Antworten (python tests/e2e.py)
                    und Echttest mit echtem Modell (python tests/live_check.py)
docs/               Übergabebericht, Referenz des Skills «denkpartner», Startprompt für Claude Code
CLAUDE.md           Arbeitsregeln für Claude Code
```

## Drei Arten, die KI anzubinden

Wähle sie im Werkzeug über den Knopf **KI** oben rechts.

| Verbindung | Wo der Schlüssel liegt | Geeignet für |
|---|---|---|
| Claude in der Claude-App | nirgends, die App erledigt das | dich, wenn du die Seite in Claude öffnest |
| Eigener API-Schlüssel, direkt aus dem Browser | in deinem Browser (Sitzung oder, wenn gewählt, dauerhaft) | dich allein, auf GitHub Pages oder lokal |
| Eigener Server | als Umgebungsvariable auf dem Server | alle Anbieter, und alles, was andere Personen nutzen |

Direkt aus dem Browser funktionieren **Anthropic, OpenAI, Google Gemini und OpenRouter**. **Mistral** blockiert Browser-Anfragen, bei **Infomaniak** ist es wahrscheinlich gleich: Für diese beiden brauchst du den Server. Ein **lokales Modell** (Ollama, LM Studio) geht direkt, wenn der lokale Server Anfragen von der Seite erlaubt; bei Ollama mit der Umgebungsvariable `OLLAMA_ORIGINS`, zum Beispiel `OLLAMA_ORIGINS=https://ehmseb.github.io`.

> Gib Schülerinnen und Schülern nie eine Seite mit deinem eigenen Schlüssel im Browser. Für sie gehört der Schlüssel auf den Server, mit Passwort und Begrenzung, oder in Gymimate.

## Variante A: GitHub Pages (nur die Seite, Schlüssel im Browser)

1. Neues Repository auf GitHub anlegen und den Inhalt dieses Ordners hochladen (Branch `main`).
2. Im Repository: **Settings → Pages → Build and deployment → Source: GitHub Actions**.
3. Der Workflow veröffentlicht `public/` automatisch. Die Adresse steht danach unter Settings → Pages, etwa `https://ehmseb.github.io/denkwerkstatt/`.
4. Seite öffnen, auf **KI** klicken, «Eigener API-Schlüssel» wählen, Anbieter, Schlüssel und Modell eintragen, «Speichern und testen».

Eigene Domain: unter Settings → Pages eine Subdomain eintragen (z. B. `denkwerkstatt.ehmseb.de`) und beim Domain-Anbieter einen CNAME-Eintrag auf `ehmseb.github.io` setzen.

## Variante B: Railway (Seite und Server, Schlüssel auf dem Server)

1. Repository wie oben auf GitHub anlegen.
2. In Railway: **New Project → Deploy from GitHub repo** und das Repository wählen. Railway erkennt Node.js und startet `npm start`.
3. Unter **Variables** mindestens setzen (siehe `.env.example`):
   - `APP_PASSWORD` (unbedingt)
   - `LLM_PROVIDER`, zum Beispiel `mistral` oder `infomaniak`
   - `LLM_MODEL` und optional `LLM_FAST_MODEL`
   - den passenden Schlüssel, zum Beispiel `MISTRAL_API_KEY`, oder `INFOMANIAK_API_KEY` und `INFOMANIAK_PRODUCT_ID`
4. Unter **Settings → Networking → Generate Domain** eine Adresse erzeugen, oder eine eigene Domain verbinden.
5. Seite öffnen. Sie findet den Server selbst; beim ersten KI-Aufruf trägst du unter **KI** das Zugangspasswort ein.

Beide kombinieren: Seite auf GitHub Pages, Server auf Railway. Dann auf Railway `ALLOWED_ORIGINS=https://ehmseb.github.io` setzen und im Werkzeug unter **KI → Eigener Server** die Railway-Adresse eintragen.

### Umgebungsvariablen

| Variable | Bedeutung |
|---|---|
| `APP_PASSWORD` | Zugangspasswort für KI-Anfragen |
| `LLM_PROVIDER` | `anthropic`, `openai`, `google`, `mistral`, `infomaniak`, `openrouter` oder `compat` |
| `LLM_MODEL` | Hauptmodell (Landkarte, Abgleich, Entwürfe, Prüfen) |
| `LLM_FAST_MODEL` | schnelles Modell (Varianten, automatische Denkanstösse); leer = Hauptmodell |
| `*_API_KEY` | Schlüssel pro Anbieter |
| `INFOMANIAK_PRODUCT_ID` | Produkt-ID des KI-Produkts im Infomaniak-Manager |
| `COMPAT_BASE_URL` | eigener OpenAI-kompatibler Server, z. B. `http://mein-ollama:11434/v1` |
| `ALLOW_MODEL_CHOICE` | `1` erlaubt die Wahl von Anbieter und Modell im Browser |
| `ALLOWED_ORIGINS` | andere Websites, die den Server nutzen dürfen |
| `RATE_LIMIT_PER_MIN` | Anfragen pro Minute und Adresse (Vorgabe 20) |
| `MAX_OUTPUT_TOKENS` | Obergrenze der Antwortlänge (Vorgabe 4000) |

## Lokal starten

```
node --env-file=.env server.js
```

Dann `http://localhost:8080` öffnen. Ohne Server geht auch einfach `public/index.html` per Doppelklick (Verbindung «Eigener API-Schlüssel»).

## Einbau in eine andere Website (z. B. Gymimate)

Vor dem Script der Seite setzen:

```html
<script>
window.DENKWERKSTATT = {
  endpoint: "/api/denkwerkstatt",  // eigener Endpunkt, erhält POST {task, system, user, fast}, gibt {text} zurück
  stufe: "mittel",                  // Stufe festlegen und Auswahl ausblenden
  modi: ["lesen"],                  // nur einen Modus zeigen
  speicher: "baustein-42",          // eigener Speicherplatz im Browser
  kontext: "Die Person ist Schülerin oder Schüler an einem Schweizer Gymnasium."
};
</script>
```

Mit `endpoint` ist die KI-Wahl im Werkzeug ausgeblendet; die Website entscheidet über Anbieter und Modell.
