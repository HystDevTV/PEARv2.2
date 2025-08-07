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

# Passwort-Hashing-Kontext initialisieren
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
    """Datenmodell für die Benutzer-Registrierung."""
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
    """Registriert einen neuen Alltagsbegleiter im System."""
    # Passwort-Validierung
    if user.password != user.password_confirmation:
        raise HTTPException(status_code=400, detail="Passwörter stimmen nicht überein.")
    if len(user.password) < 8:
        raise HTTPException(status_code=400, detail="Passwort muss mindestens 8 Zeichen lang sein.")

    cursor = db.cursor()
    
    # Prüfen, ob die E-Mail bereits existiert
    cursor.execute("SELECT id FROM tbl_begleiter WHERE kontakt_email = %s", (user.email,))
    if cursor.fetchone():
        raise HTTPException(status_code=409, detail="Ein Benutzer mit dieser E-Mail-Adresse existiert bereits.")

    # Passwort hashen
    hashed_password = pwd_context.hash(user.password)

    # Benutzer in die Datenbank einfügen
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

    return {"message": "Registrierung erfolgreich!"}


@app.post("/api/extract_and_register_client", tags=["Email Automation"])
async def extract_and_register_client(payload: EmailPayload, db: mysql.connector.MySQLConnection = Depends(get_db_connection)):
    """
    Nimmt rohen E-Mail-Text entgegen, extrahiert die Kundendaten,
    validiert sie und legt bei Erfolg einen neuen Klienten in der Datenbank an.
    """
    if not payload.email_content:
        raise HTTPException(status_code=400, detail="E-Mail-Inhalt fehlt.")

    print(f"E-Mail-Inhalt für die Verarbeitung erhalten: {payload.email_content[:200]}...")

    # --- 1. Datenextraktion (simuliert) ---
    lines = payload.email_content.strip().split('\n')
    extracted_data = {}
    for line in lines:
        if ':' in line:
            key, value = line.split(':', 1)
            normalized_key = key.strip().lower().replace(' ', '_').replace('(', '').replace(')', '')
            extracted_data[normalized_key] = value.strip()

    # --- 2. Validierung ---
    required_fields = [
        'name_vollstaendig', 'kontakt_telefon', 'kontakt_email', 'adresse_strasse',
        'alter', 'adresse_hausnummer', 'adresse_plz', 'adresse_ort',
        'firmenname_klientenvermittlung', 'steuernummer_fiktiv'
    ]
    missing_fields = [field for field in required_fields if field not in extracted_data or not extracted_data[field]]

    if missing_fields:
        error_message = f"Datensatz unvollständig. Folgende Felder fehlen: {', '.join(missing_fields)}."
        print(f"VALIDIERUNGSFEHLER: {error_message}")
        raise HTTPException(status_code=422, detail=error_message)

    # --- 3. Erfolgsfall: Daten aufbereiten und in DB einfügen ---
    try:
        hashed_password = pwd_context.hash("default_klient_password_placeholder")
        rolle = "Neukunde"
        
        cursor = db.cursor()
        query = """
            INSERT INTO tbl_kunden (
                name_vollstaendig, kontakt_telefon, kontakt_email, adresse_strasse,
                adresse_hausnummer, adresse_plz, adresse_ort, alter,
                firmenname_vermittler, steuernummer_vermittler,
                passwort_hash, rolle, ist_aktiv, erstellt_am
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE, NOW())
        """
        values = (
            extracted_data['name_vollstaendig'],
            extracted_data['kontakt_telefon'],
            extracted_data['kontakt_email'],
            extracted_data['adresse_strasse'],
            extracted_data['adresse_hausnummer'],
            extracted_data['adresse_plz'],
            extracted_data['adresse_ort'],
            int(extracted_data['alter']),
            extracted_data['firmenname_klientenvermittlung'],
            extracted_data['steuernummer_fiktiv'],
            hashed_password,
            rolle
        )
        cursor.execute(query, values)
        db.commit()
        
        new_client_id = cursor.lastrowid
        print(f"Neuer Klient erfolgreich mit ID {new_client_id} in der Datenbank angelegt.")

    except Error as e:
        print(f"DATENBANKFEHLER: {e}")
        raise HTTPException(status_code=500, detail=f"Datenbankfehler beim Erstellen des Klienten: {e}")
    finally:
        cursor.close()

    # --- 4. Bestätigungs-E-Mails (simuliert) ---
    print("PROZESS ERFOLGREICH. Sende Bestätigungs-E-Mails...")

    return {
        "status": "success",
        "message": "Klient erfolgreich erstellt.",
        "client_id": new_client_id
    }