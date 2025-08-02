from fastapi import FastAPI
from google.cloud import logging_v2
from google.auth.exceptions import DefaultCredentialsError
from fastapi.responses import JSONResponse

app = FastAPI()

@app.get("/cloudia/test-gcp")
def test_cloudia_gcp():
    try:
        client = logging_v2.Client()
        return {"status": "success", "message": "✅ CloudIA ist verbunden."}
    except DefaultCredentialsError as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": f"❌ Fehler mit den Credentials: {e}"})
