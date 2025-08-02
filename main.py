
import functions_framework
import requests
import base64
import json
import os
from google.cloud import storage

# --- Konfiguration (Aus Umgebungsvariablen) ---
# Die URL Ihres FastAPI-Backends
FASTAPI_API_URL = os.getenv("FASTAPI_API_URL", "http://35.206.123.242:8000")
# Der API-Endpunkt für die Registrierung
REGISTER_API_ENDPOINT = f"{FASTAPI_API_URL}/api/register"

# --- Initialisierung ---
storage_client = storage.Client()

# --- Cloud Function Trigger (Wird ausgelöst, wenn Datei im Bucket erstellt wird) ---
@functions_framework.cloud_event
def process_email_from_bucket(cloud_event):
    data = cloud_event.data

    bucket_name = data["bucket"]
    file_name = data["name"]

    print(f"Neue Datei '{file_name}' im Bucket '{bucket_name}' erkannt.")

    # Datei aus Cloud Storage lesen
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(file_name)

    try:
        # E-Mail-Inhalt lesen
        email_raw_content = blob.download_as_text()
        print(f"Inhalt von '{file_name}' gelesen.")

        # Hier kommt die Logik zum Parsen des E-Mail-Bodys
        # Externe E-Mail-Dienste wie SendGrid/Mailgun können den Body als JSON oder Plaintext liefern.
        # Beispiel: Wenn der Inhalt direkt der Plaintext-Body ist:
        email_body_text = email_raw_content

        # Wenn der Inhalt ein vollständiges .eml-Format ist, müsste er hier geparst werden:
        # from email.parser import BytesHeaderParser
        # from io import BytesIO
        # msg = BytesHeaderParser().parsebytes(email_raw_content.encode('utf-8'))
        # email_body_text = msg.get_payload(decode=True).decode('utf-8')
        # print("EML-Datei geparst und Body extrahiert.")

    except Exception as e:
        print(f"FEHLER beim Lesen/Parsen der E-Mail-Datei '{file_name}': {e}")
        # Die Datei in einen Fehlerordner verschieben
        error_blob = bucket.blob(f"errors/{file_name}")
        blob.rewrite(error_blob)
        blob.delete()
        return

    # Daten für die FastAPI-Anfrage vorbereiten (anpassen an Ihre Bedürfnisse)
    # Dies ist ein Beispiel. Ihre FastAPI /api/register erwartet RegisterUser-Daten.
    # Normalerweise würde hier die Gemini-Extraktion stattfinden, die diese Daten liefert.
    # Für den Moment simulieren wir eine feste Struktur oder leiten nur den Text weiter.

    # HINWEIS: Ihre FastAPI /api/register erwartet mehr Felder (full_name, email, password etc.)
    # Dies ist eine vereinfachte Demo für den Aufruf. Die tatsächlichen extrahierten Daten
    # von Gemini müssten hier eingesetzt werden.

    # Beispiel, wie der Body an Ihre FastAPI gesendet würde (angenommen, FastAPI erwartet 'email_content'):
    # Hier müsste die Logik für die Gemini-Extraktion aus den E-Mail-Texten erfolgen.
    # Ihre backend_app.py muss einen Endpunkt bereitstellen, der nur den E-Mail-Body annimmt
    # und dann Gemini aufruft, um die RegisterUser-Daten zu erstellen.

    # Nehmen wir an, FastAPI hat einen Endpunkt /api/extract_and_register_client
    # Dieser Endpunkt nimmt nur den E-Mail-Body entgegen und kümmert sich um Gemini und DB.
    # WIR WERDEN DIESEN NEUEN ENDPUNKT IN FASTAPI SPÄTER ERSTELLEN!

    payload = {"email_content": email_body_text}

    # API-Aufruf an Ihre FastAPI-Anwendung auf der VM
    try:
        response = requests.post(REGISTER_API_ENDPOINT, json=payload) # AUFRUF HIER!
        response.raise_for_status() # Löst Fehler aus, wenn Statuscode 4xx oder 5xx
        print(f"FastAPI API erfolgreich aufgerufen. Antwort: {response.json()}")

        # Erfolgreich verarbeitete E-Mail verschieben (oder löschen)
        processed_blob = bucket.blob(f"processed/{file_name}")
        blob.rewrite(processed_blob)
        blob.delete()

    except requests.exceptions.RequestException as e:
        print(f"FEHLER beim Aufruf der FastAPI API: {e}")
        # Datei in Fehlerordner verschieben
        error_blob = bucket.blob(f"errors/{file_name}")
        blob.rewrite(error_blob)
        blob.delete()

    except Exception as e:
        print(f"Unerwarteter Fehler in Cloud Function: {e}")
        error_blob = bucket.blob(f"errors/{file_name}")
        blob.rewrite(error_blob)
        blob.delete()

    return "OK"