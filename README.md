# 💸 Financial Planer

Trage deine Ausgaben per **Screenshot** ein: Die App liest den **Betrag** und den
**Empfänger** aus dem Bild, zeigt eine **Karte** — und du **ziehst sie per Swipe**
in deine selbst angelegten **Kategorie-Boxen**. Am Ende exportierst du alles als
**Excel** oder **Markdown**.

## Prinzip

> **Die KI/OCR liest nur — das Script rechnet.**

- Aus dem Screenshot wird **nur der Text gelesen** (Betrag + Empfänger). Keine
  Kategorisierung, keine „intelligente" Zuordnung.
- **Du** sortierst per Hand durch Swipen in deine Boxen.
- Alle **Summen** berechnet ein deterministisches Python-Script (ganzzahlige
  Cent-Arithmetik, kein Fließkomma, kein LLM).
- **Alles läuft lokal.** Keine Cloud, keine externen Aufrufe, deine Finanzdaten
  verlassen deinen Rechner nie.

## Architektur

```
Screenshot → OCR liest Betrag+Empfänger → Karte
                                            │  (du ziehst sie in eine Box)
                                            ▼
                                   SQLite (data/finance.db)
                                            │
                                deterministisches Rechen-Script
                                            │
                                     Excel / Markdown
```

| Teil | Datei | Aufgabe |
| --- | --- | --- |
| Extraktion (austauschbar) | `backend/ocr.py` | Betrag + Empfänger aus dem Bild lesen |
| Geld-Parsing | `backend/amount.py` | Text ↔ ganzzahlige Cents |
| Speicher | `backend/db.py` | SQLite, die einzige Wahrheit |
| Rechnen | `backend/calc.py` | Summen pro Kategorie (deterministisch) |
| Export | `backend/export.py` | `.xlsx` / `.md` |
| API + Server | `backend/app.py` | FastAPI, lokal |
| Oberfläche | `frontend/` | Swipe-UI (Desktop + Handy) |

## Installation

1. **Python-Pakete:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Tesseract-OCR** (systemweit, für die automatische Erkennung):
   - macOS: `brew install tesseract tesseract-lang`
   - Ubuntu/Debian: `sudo apt install tesseract-ocr tesseract-ocr-deu`
   - Windows: Installer von <https://github.com/UB-Mannheim/tesseract/wiki>

   > Ohne Tesseract läuft die App trotzdem — Betrag und Empfänger trägst du dann
   > einfach selbst auf der Karte ein.

## Starten

```bash
uvicorn backend.app:app --reload
```

Dann im Browser: <http://localhost:8000>

**Auf dem Handy** (gleiches WLAN): Server mit
`uvicorn backend.app:app --host 0.0.0.0` starten und
`http://<PC-IP>:8000` am Handy öffnen.

## Bedienung

1. **Kategorie-Boxen anlegen** (z. B. Lebensmittel, Miete, Freizeit).
2. **Screenshots hochladen** — pro Screenshot erscheint eine Karte mit Betrag +
   Empfänger (beides direkt auf der Karte korrigierbar).
3. **Karte in eine Box ziehen** (Maus oder Finger).
4. **Exportieren** über die Buttons oben rechts.

## Tests

```bash
pytest
```

Die Tests decken die Geld-Arithmetik und die Summenbildung ab — also genau den
Teil, der **nicht** von KI kommen soll.
