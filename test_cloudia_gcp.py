from google.cloud import logging_v2
from google.auth.exceptions import DefaultCredentialsError

try:
    client = logging_v2.Client()
    print("✅ CloudIA ist verbunden.")
except DefaultCredentialsError as e:
    print("❌ Fehler mit den Credentials:", e)
