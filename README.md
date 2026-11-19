# ProductCreator AI – Web-App MVP 0.3

Eine lokal im Browser laufende Streamlit-Weboberfläche für die Konfiguration von Geschenkboxen.

## Start

Python 3.10+ installieren, dann im Projektordner:

```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

Öffne die angezeigte lokale URL (üblicherweise http://localhost:8501).

## Was funktioniert

- Produktidee, Budget, Menge, Zielmarge und Gebühren eingeben
- Artikel mit Originalbild-URL, Händlerlink und Preis erfassen
- Materialkosten, Restbudget, Mindest-Bruttoverkaufspreis kalkulieren
- Originalbilder der erfassten Artikel nebeneinander anzeigen (keine erfundenen Ersatzbilder)
- Einkaufsliste als CSV und Projektdaten als JSON exportieren

## Was noch nicht funktioniert

- Automatische Webrecherche und Preisverifikation
- Automatischer Abgleich, ob die Originalbilder zu den Artikeln passen
- Fotorealistische Gesamtmontage der Geschenkbox
- Live-Verfügbarkeit, Lieferkosten oder Shopify-Publikation

## Wichtige Hinweise

Die enthaltenen Zahlen sind Platzhalter und keine verifizierten Angebote. Bilder werden nur aus eingetragenen HTTPS-URLs geladen. Nutzungsrechte für Produktbilder, MWST-Behandlung, Lieferkosten und Artikelverfügbarkeit vor Veröffentlichung prüfen. Die Preisformel ist eine vereinfachte Planungskalkulation, keine Steuerberatung.
