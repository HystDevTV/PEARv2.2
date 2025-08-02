# PEARv2

Dieses Projekt demonstriert die Verarbeitung von E-Mails mit Hilfe einer Google Cloud Function und einer FastAPI-Anwendung. Eingehende E-Mails werden aus einem Cloud Storage Bucket gelesen und an einen REST-API-Endpunkt weitergeleitet, der die Daten speichert oder weiterverarbeitet.

## Ausführen der Agenten

Um die Aufgaben der verschiedenen Agenten anzuzeigen, kann `modules/run_agents.py` ausgeführt werden:

```bash
python modules/run_agents.py
```

Das Skript erstellt das Team aus `modules/team.py` und gibt die einzelnen Rollen und Aufgaben im Terminal aus.

## Cloud Function testen oder deployen

Die Datei `main.py` enthält die Cloud Function `process_email_from_bucket`. Zum lokalen Testen kann das [Functions Framework](https://cloud.google.com/functions/docs/functions-framework) genutzt werden:

```bash
pip install -r requirements.txt
functions-framework --target process_email_from_bucket --port 8080
```

In der Cloud lässt sich die Funktion beispielsweise über Cloud Run deployen. Ein passendes Beispiel findet sich in `cloudbuild.yaml`.