# Verwende ein offizielles Python-Image als Basis-Image
FROM python:3.11-slim-buster

# Setze das Arbeitsverzeichnis im Container
WORKDIR /app

# Kopiere die requirements.txt in das Arbeitsverzeichnis
COPY requirements.txt .

# Installiere alle Python-Abhängigkeiten
RUN pip install --no-cache-dir -r requirements.txt

# Kopiere den Anwendungscode in das Arbeitsverzeichnis
COPY main.py .

# Exponiere den Port, auf dem die Cloud Run-Anwendung lauschen wird
ENV PORT 8080

# Starte die Anwendung, wenn der Container gestartet wird
ENTRYPOINT ["functions-framework", "--target", "process_email_from_bucket", "--port", "8080"]
