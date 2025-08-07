# pear-backend/backend_app.py

import os
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
import mysql.connector
from mysql.connector import Error

# --- Initialisierung ---
app = FastAPI(
    title="PEAR Backend API",
    description="API für die Professionelle Einsatz-, Abrechnungs- und Ressourcenverwaltung.",
    version="0.1.0",
)

# Passwort-Hashing-Kontext initialisieren [cite: 22]
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# --- Datenbankverbindung ---
def get_db_connection():
    """Stellt eine Datenbankverbindung her und gibt sie zurück."""
    try:
        conn = mysql.connector.connect(
            host=os.getenv("DB_HOST", "127.0.0.1"),
            user=os.getenv("DB_USER", "app_user"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_NAME", "pear_app_db")
        )
        yield conn
    except Error as e:
        print(f"Schwerwiegender DB-Fehler: {e}")
        raise HTTPException(status_code=500, detail="Datenbankverbindung konnte nicht hergestellt werden.")
    finally:
        if 'conn' in locals() and conn.is_connected():
            conn.close()

# --- Pydantic-Modelle (Datenstrukturen) ---
class RegisterUser(BaseModel):
    """Datenmodell für die Benutzer-Registrierung.""" [cite: 15]
    full_name: str
    email: EmailStr
    password: str
    password_confirmation: str
    street: str
    house_number: str
    zip_code: str
    city: str
    company_name: str | None = None
    tax_number: str | None = None

class EmailPayload(BaseModel):
    """Datenmodell für den rohen E-Mail-Inhalt."""
    email_content: str

# --- API Endpunkte ---

@app.get("/", tags=["Health Check"])
async def read_root():
    """Ein einfacher Endpunkt, um zu prüfen, ob die API online ist."""
    return {"status": "ok", "message": "PEAR Backend API is running!"}


@app.post("/api/register", status_code=201, tags=["Authentication"])
async def register_user(user: RegisterUser, db: mysql.connector.MySQLConnection = Depends(get_db_connection)):
    """Registriert einen neuen Alltagsbegleiter im System.""" [cite: 16]
    # Passwort-Validierung [cite: 18]
    if user.password != user.password_confirmation:
        raise HTTPException(status_code=400, detail="Passwörter stimmen nicht überein.")
    if len(user.password) < 8:
        raise HTTPException(status_code=400, detail="Passwort muss mindestens 8 Zeichen lang sein.")

    cursor = db.cursor()
    
    # Prüfen, ob die E-Mail bereits existiert [cite: 21]
    cursor.execute("SELECT id FROM tbl_begleiter WHERE kontakt_email = %s", (user.email,))
    if cursor.fetchone():
        raise HTTPException(status_code=409, detail="Ein Benutzer mit dieser E-Mail-Adresse existiert bereits.")

    # Passwort hashen [cite: 22]
    hashed_password = pwd_context.hash(user.password)

    # Benutzer in die Datenbank einfügen [cite: 23]
    try:
        query = """
            INSERT INTO tbl_begleiter 
            (name_vollstaendig, kontakt_email, passwort_hash, adresse_strasse, adresse_hausnummer, adresse_plz, adresse_ort, firmenname, steuernummer) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        values = (
            user.full_name, user.email, hashed_password, user.street, 
            user.house_number, user.zip_code, user.city, user.company_name, user.tax_number
        )
        cursor.execute(query, values)
        db.commit()
    except Error as e:
        raise HTTPException(status_code=500, detail=f"Datenbankfehler beim Erstellen des Benutzers: {e}")
    finally:
        cursor.close()

    return {"message": "Registrierung erfolgreich!"} [cite: 24]


@app.post("/api/extract_and_register_client", tags=["Email Automation"])
async def extract_and_register_client(payload: EmailPayload, db: mysql.connector.MySQLConnection = Depends(get_db_connection)):
    """
    Nimmt rohen E-Mail-Text entgegen, ruft Gemini zur Extraktion auf
    und legt einen neuen Klienten an. (Logik wird noch implementiert)
    """
    if not payload.email_content:
        raise HTTPException(status_code=400, detail="Email content is missing")

    print(f"E-Mail-Inhalt für die Verarbeitung erhalten: {payload.email_content[:200]}...")

    # TODO: Logik für Gemini API-Aufruf zur Datenextraktion einfügen
    # extracted_data = call_gemini(payload.email_content)
    
    # TODO: Logik zum Einfügen der extrahierten Daten in die tbl_kunden
    # insert_client_into_db(extracted_data)

    return {"status": "success", "message": "Email received and is being processed."}